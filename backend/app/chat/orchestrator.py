import asyncio
import json
import re
from dataclasses import dataclass
from time import monotonic
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import build_agent
from app.assistant.comparisons import ComparisonReady, build_comparison_writer
from app.assistant.deps import BudgetExceeded, DocumentAgentDeps, TurnRegistry
from app.assistant.facts import build_fact_extractor, build_input_judge
from app.assistant.failure_diagnostics import (
    http_failure_diagnostics,
    output_retry_feedback,
    structural_failure_summary,
    unexpected_response_diagnostics,
)
from app.assistant.model_settings import ModelOutputLimitExceeded
from app.assistant.outputs import AnswerClaim, EvidenceGap, GroundedAnswer
from app.assistant.rendering import AcceptedReply, render_answer
from app.assistant.selection import matches_target, with_coverage
from app.config import settings
from app.grounding.claim_context import financial_context_only
from app.grounding.judge import build_judge, judge_answer, support_errors
from app.grounding.validator import structural_errors
from app.retrieval.retriever import DocumentRetriever

logger = structlog.get_logger()


class GroundingRejected(ValueError):
    pass


class AssistantFailure(RuntimeError):
    def __init__(self, category: str, diagnostics: dict):
        super().__init__("The assistant could not complete this turn")
        self.category = category
        self.diagnostics = diagnostics


def diagnostics(deps: DocumentAgentDeps, started: float) -> dict:
    def usage(value):
        return {
            "requests": value.requests,
            "input_tokens": value.input_tokens,
            "output_tokens": value.output_tokens,
        }

    return {
        "generator": usage(deps.generator_usage),
        "grounding": usage(deps.judge_usage),
        "retrieval": deps.retrieval_usage,
        "numeric_attempts": deps.numeric_attempts,
        "tool_calls": deps.tool_calls,
        "calculation_count": len(deps.registry.calculations),
        "validation": deps.validation_reports,
        "tool_notes": deps.tool_notes,
        "calculations": [
            c.model_dump(mode="json") for c in deps.registry.calculations.values()
        ],
        "elapsed_seconds": round(monotonic() - started, 2),
    }


@dataclass
class GroundedRun:
    answer: GroundedAnswer
    reply: AcceptedReply
    diagnostics: dict


ITEM_ERROR = re.compile(r"^(claim|gap) (\d+): ")
# Deterministic, so declining investment advice never depends on the model.
INVESTMENT_ADVICE = re.compile(
    r"\b(?:should|would|could|do)\s+(?:i|we|you)\s+(?:buy|sell|short|invest|hold)\b"
    r"|\bbuy\s+or\s+sell\b|\b(?:good|bad|smart|safe)\s+(?:investment|buy)\b"
    r"|\b(?:price\s+target|stock\s+picks?|undervalued|overvalued|worth\s+buying)\b",
    re.IGNORECASE,
)


def covered_targets(registry: TurnRegistry, claims: list[AnswerClaim]) -> set[int]:
    cited = [registry.passages[ref.chunk_id] for c in claims for ref in c.evidence]
    return {
        i
        for i, target in enumerate(registry.comparison_targets)
        if any(matches_target(p, target) for p in cited)
    }


def drop_unwarranted_gaps(
    answer: GroundedAnswer, errors: list[str], deps: DocumentAgentDeps
) -> tuple[GroundedAnswer, list[str]]:
    """On the final attempt, drop gaps the judge found unwarranted when every claim passed.

    Live drafts kept adding a gap rebutting the question's premise ("does the
    filing say nothing about AI?") after supported claims had answered it.
    Removing an unwarranted limitation adds no content; claim failures and
    other errors still fail closed.
    """
    gaps = set()
    for error in errors:
        match = ITEM_ERROR.match(error)
        if not match or match[1] != "gap" or "unwarranted" not in error:
            return answer, errors
        gaps.add(int(match[2]))
    if not answer.claims:
        return answer, errors
    kept = [g for i, g in enumerate(answer.gaps) if i not in gaps]
    pruned = answer.model_copy(
        update={"gaps": kept, "status": answer.status if kept else "answered"}
    )
    deps.validation_reports.append({"stage": "dropped_gaps", "gaps": sorted(gaps)})
    return pruned, structural_errors(
        pruned,
        deps.registry,
        searches=deps.completed_retrievals,
        max_claims=deps.settings.assistant_max_claims,
        max_refs=deps.settings.assistant_claim_refs,
    )


def withhold_failed(
    answer: GroundedAnswer,
    errors: list[str],
    deps: DocumentAgentDeps,
    *,
    source: str,
    attempt: int,
) -> tuple[GroundedAnswer, list[str]]:
    """On the final guided attempt, drop failed claims instead of the whole answer.

    This is usually after the single repair; a comparison first planned on the
    final attempt is pruned on its only draft. Remaining claims keep every
    check; a target left without claims gets the server's always-true coverage
    line. Answer-level errors and errors on server-owned gaps still fail closed.
    """
    claims, gaps = set(), set()
    for error in errors:
        match = ITEM_ERROR.match(error)
        if not match:
            return answer, errors
        index = int(match[2])
        if match[1] == "claim":
            claims.add(index)
        elif answer.gaps[index].request_quote is not None:
            gaps.add(index)
        else:
            return answer, errors
    kept_claims = [claim for i, claim in enumerate(answer.claims) if i not in claims]
    if not kept_claims:
        # Withholding trims a failed answer; it never turns one into "no evidence".
        return answer, errors
    kept_gaps = [gap for i, gap in enumerate(answer.gaps) if i not in gaps]
    if source == "grounding":
        lost = covered_targets(deps.registry, answer.claims) - covered_targets(
            deps.registry, kept_claims
        )
        targets = deps.registry.comparison_targets
        if any(gap.target == targets[i] for i in lost for gap in kept_gaps):
            # A narrow model gap judged alongside the lost claims could read as
            # if the rest of that target were established.
            return answer, errors
    pruned = with_coverage(deps.registry, kept_claims, kept_gaps)
    deps.withheld.append(
        {
            "stage": "withheld",
            "source": source,
            "attempt": attempt,
            "claims": sorted(claims),
            "gaps": sorted(gaps),
        }
    )
    return pruned, structural_errors(
        pruned,
        deps.registry,
        searches=deps.completed_retrievals,
        max_claims=deps.settings.assistant_max_claims,
        max_refs=deps.settings.assistant_claim_refs,
    )


async def run_grounded(
    question: str,
    history: list[dict],
    deps: DocumentAgentDeps,
    agent,
    judge,
    *,
    comparison_writer=None,
) -> GroundedRun:
    deps.question = question
    if deps.fact_judge is None:
        deps.fact_judge = judge
    usage = deps.generator_usage
    judge_usage = deps.judge_usage
    prompt = json.dumps(
        {"server_history_context_not_evidence": history, "question": question}
    )
    messages = None
    reports = deps.validation_reports
    started = monotonic()
    guided_comparison = False
    structural = []
    for attempt in range(deps.settings.assistant_grounding_repairs + 1):
        final = attempt == deps.settings.assistant_grounding_repairs
        if deps.progress:
            await deps.progress("repairing" if attempt else "analyzing")
        deps.prune_unverified = guided_comparison and final
        try:
            with capture_run_messages() as captured:
                result = await agent.run(
                    prompt,
                    deps=deps,
                    message_history=messages,
                    usage=usage,
                    usage_limits=UsageLimits(
                        request_limit=min(
                            deps.settings.openai_agent_request_limit,
                            usage.requests + 1
                            if guided_comparison
                            else deps.settings.openai_agent_request_limit,
                        )
                    ),
                )
            if isinstance(result.output, ComparisonReady):
                if comparison_writer is None:
                    raise RuntimeError(
                        "Comparison writer is required for comparison plans"
                    )
                guided_comparison = True
                deps.prune_unverified = final
                agent = comparison_writer
                prompt = json.dumps(
                    {
                        "question": question,
                        "request_spans": deps.registry.request_spans,
                        "comparison_evidence": result.output.evidence,
                    }
                )
                messages = None
                with capture_run_messages() as captured:
                    result = await agent.run(
                        prompt,
                        deps=deps,
                        usage=usage,
                        usage_limits=UsageLimits(
                            request_limit=min(
                                deps.settings.openai_agent_request_limit,
                                usage.requests + 1,
                            )
                        ),
                    )
        except UnexpectedModelBehavior as error:
            if not guided_comparison:
                raise
            reports.append(
                {
                    "stage": "comparison_output",
                    "attempt": attempt,
                    **unexpected_response_diagnostics(error),
                }
            )
            if attempt == deps.settings.assistant_grounding_repairs:
                raise GroundingRejected(
                    "Comparison submission could not be validated"
                ) from None
            messages = captured
            prompt = (
                "Repair the invalid comparison submission using the same evidence and displayed E/R IDs. "
                "No further retrieval or additional repair is available. Output-validation feedback: "
                + output_retry_feedback(error)
            )
            continue
        answer = result.output
        errors = structural_errors(
            answer,
            deps.registry,
            searches=deps.completed_retrievals,
            max_claims=deps.settings.assistant_max_claims,
            max_refs=deps.settings.assistant_claim_refs,
        )
        reports.append(
            {
                "stage": "structural",
                "attempt": attempt,
                "claim_kinds": [c.kind for c in answer.claims],
                "errors": errors,
            }
        )
        structural = errors
        if errors and guided_comparison and final:
            answer, errors = withhold_failed(
                answer, errors, deps, source="structural", attempt=attempt
            )
        if not errors and (answer.claims or guided_comparison and answer.gaps):
            if deps.progress:
                await deps.progress("verifying")
            checked = await judge_answer(
                question,
                answer,
                deps.registry,
                judge,
                usage=judge_usage,
                usage_limits=UsageLimits(
                    request_limit=deps.settings.assistant_grounding_repairs
                    + 1
                    + deps.fact_checks
                ),
            )
            errors = support_errors(checked, len(answer.claims), len(answer.gaps))
            reports.append(checked.model_dump())
            if errors and guided_comparison and final:
                answer, errors = withhold_failed(
                    answer, errors, deps, source="grounding", attempt=attempt
                )
            elif errors and final:
                answer, errors = drop_unwarranted_gaps(answer, errors, deps)
        if not errors:
            reports.extend(deps.withheld)
            return GroundedRun(
                answer,
                render_answer(
                    answer,
                    deps.registry,
                    withheld=sum(len(report["claims"]) for report in deps.withheld),
                    advice=bool(INVESTMENT_ADVICE.search(question)),
                ),
                diagnostics(deps, started),
            )
        messages = result.all_messages()
        prompt = (
            "Repair this draft using the same evidence and remaining budget. Safe validation failures: "
            + json.dumps(errors)
        )
        if guided_comparison:
            prompt += "\nUse the already-displayed evidence and R request IDs. Correct or omit unsupported claims and unrequested gaps; no additional retrieval is available."
        else:
            prompt += "\nSelect evidence_ids from these already-observed sources. Split compound claims into small supported facts, or omit unsupported claims and report gaps: "
            prompt += json.dumps(
                [
                    {
                        "evidence_id": key,
                        **ref.model_dump(mode="json"),
                        "ticker": deps.registry.passages[ref.chunk_id].ticker,
                        "corpus_year": deps.registry.passages[ref.chunk_id].corpus_year,
                        "document_id": str(
                            deps.registry.passages[ref.chunk_id].document_id
                        ),
                    }
                    for key, ref in deps.registry.evidence_refs.items()
                ]
            )
    # Withholding may have replaced financial-context errors with judge errors;
    # the pre-withholding structural result keeps that fallback available.
    if deps.registry.comparison_targets and (
        financial_context_only(errors) or financial_context_only(structural)
    ):
        # No draft claims survive this fallback; it reports verification failure,
        # not an assertion that the filings lack the requested information.
        answer = GroundedAnswer(
            status="insufficient_evidence",
            gaps=[
                EvidenceGap(target=target, reason="ambiguous_figures")
                for target in deps.registry.comparison_targets
            ],
        )
        reports.append(
            {"stage": "financial_context_fallback", "target_count": len(answer.gaps)}
        )
        return GroundedRun(
            answer,
            render_answer(
                answer,
                deps.registry,
                advice=bool(INVESTMENT_ADVICE.search(question)),
            ),
            diagnostics(deps, started),
        )
    raise GroundingRejected("The answer could not be verified against its sources")


async def generate_reply(
    question: str, history: list[dict], user_id: UUID, thread_id: UUID, progress=None
) -> GroundedRun:
    started = monotonic()
    deps = None
    category = "cancelled"
    failure_type = None
    model_failure = None
    try:
        async with (
            asyncio.timeout(settings.assistant_deadline_seconds),
            AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                max_retries=0,
                timeout=60,
            ) as client,
            DocumentRetriever(
                settings, client=client.with_options(max_retries=1, timeout=30)
            ) as retriever,
        ):
            deps = DocumentAgentDeps(
                user_id, thread_id, retriever, settings, progress=progress
            )
            deps.fact_extractor = build_fact_extractor(settings, client)
            deps.fact_judge = build_input_judge(settings, client)
            result = await run_grounded(
                question,
                history,
                deps,
                build_agent(settings, client),
                build_judge(settings, client),
                comparison_writer=build_comparison_writer(settings, client),
            )
            category = "accepted"
            return result
    except Exception as error:  # noqa: BLE001 -- sanitize the provider boundary
        category = (
            "model_output_limit"
            if isinstance(error, ModelOutputLimitExceeded)
            else "grounding"
            if isinstance(error, GroundingRejected)
            else "budget"
            if isinstance(error, (UsageLimitExceeded, BudgetExceeded))
            else "timeout"
            if isinstance(error, TimeoutError)
            else "service"
        )
        details = diagnostics(deps, started) if deps else {}
        failure_type = type(error).__name__
        details["failure_type"] = failure_type
        if isinstance(error, ModelOutputLimitExceeded):
            model_failure = error.diagnostics()
            details["model_failure"] = model_failure
        elif isinstance(error, UnexpectedModelBehavior):
            model_failure = unexpected_response_diagnostics(error)
            details["model_failure"] = model_failure
        elif isinstance(error, ModelHTTPError):
            model_failure = http_failure_diagnostics(error)
            details["model_failure"] = model_failure
        raise AssistantFailure(category, details) from None
    finally:
        if deps is not None:
            logger.info(
                "assistant_turn_finished",
                user_id=str(user_id),
                thread_id=str(thread_id),
                model=settings.openai_chat_model,
                grounding_model=settings.openai_grounding_model,
                category=category,
                failure_type=failure_type,
                model_failure=model_failure,
                generator=diagnostics(deps, started)["generator"],
                grounding=diagnostics(deps, started)["grounding"],
                tool_calls=deps.tool_calls,
                numeric_attempts=deps.numeric_attempts,
                calculation_count=len(deps.registry.calculations),
                structural_validation=structural_failure_summary(
                    deps.validation_reports
                ),
                withheld=[
                    report
                    for report in deps.validation_reports
                    if report.get("stage") == "withheld"
                ],
                # Indices only: judge assessments may quote model or source text.
                judge_rejections=[
                    {
                        "claims": [
                            d["claim_index"]
                            for d in report["decisions"]
                            if not d["supported"]
                        ],
                        "gaps": [
                            d["gap_index"]
                            for d in report["gap_decisions"]
                            if not d["warranted"]
                        ],
                    }
                    for report in deps.validation_reports
                    if "decisions" in report and "stage" not in report
                ],
                financial_context_fallback=any(
                    report.get("stage") == "financial_context_fallback"
                    for report in deps.validation_reports
                ),
                elapsed_seconds=round(monotonic() - started, 2),
            )
