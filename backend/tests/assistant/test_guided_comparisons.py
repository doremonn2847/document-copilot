import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from app.assistant.comparisons import (
    ComparisonGap,
    final_comparison_answer,
    request_spans,
)
from app.assistant.selection import SelectedClaim
from app.assistant.tools import expose_groups
from app.retrieval.types import SearchFilters
from tests.assistant.test_contracts import passage
from tests.assistant.test_tools import deps


def test_request_spans_are_bounded_exact_user_text_not_model_quotes():
    question = (
        "Compare Apple’s and NVIDIA’s risks for 2021–2025.\nAssess increased urgency."
    )
    spans = request_spans(question)
    assert spans == {
        "R1": "Compare Apple’s and NVIDIA’s risks for 2021–2025.",
        "R2": "Assess increased urgency.",
    }
    long = request_spans("word " * 4000)
    assert all(0 < len(text) <= 1000 for text in long.values())
    assert all(text in "word " * 4000 for text in long.values())


def test_comparison_gap_resolves_server_quote_and_keeps_empty_targets():
    d = deps()
    d.question = "Compare Apple and NVIDIA. Assess increased urgency."
    d.registry.request_spans = request_spans(d.question)
    d.registry.comparison_targets = [
        SearchFilters(ticker="AAPL", corpus_years=[2025]),
        SearchFilters(ticker="NVDA", corpus_years=[2025]),
    ]
    p = passage("We rely on outsourcing partners.").model_copy(
        update={"corpus_year": 2025}
    )
    expose_groups(d, [("Apple", [p])])
    result = final_comparison_answer(
        SimpleNamespace(deps=d),
        [SelectedClaim(text=p.text, evidence_ids=["E1"])],
        [
            ComparisonGap(
                request_id="R2",
                target=None,
                reason="missing_evidence",
                missing_detail="The retrieved wording does not establish an urgency trend.",
            )
        ],
    )
    assert result.gaps[0].request_quote == "Assess increased urgency."
    assert result.gaps[1].target.ticker == "NVDA"
    assert result.gaps[1].request_quote is None
    with pytest.raises(ModelRetry, match="request ID"):
        final_comparison_answer(
            SimpleNamespace(deps=d),
            [],
            [
                ComparisonGap(
                    request_id="R999",
                    target=None,
                    reason="missing_evidence",
                    missing_detail="Trend unverified.",
                )
            ],
        )


def test_comparison_submission_cannot_accept_model_copied_request_quote():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ComparisonGap(
            request_id="R1",
            request_quote="An invented request",
            target=None,
            reason="missing_evidence",
            missing_detail="Trend unverified.",
        )


@pytest.mark.parametrize(
    "first_failure",
    [
        None,
        "submission",
        "grounding",
        "both_bad",
        "submission_then_grounding",
        "invalid_plan",
    ],
)
def test_guided_wire_path_is_tool_free_and_shares_one_repair(first_failure):
    import httpx
    from openai import AsyncOpenAI

    from app.assistant.agent import build_agent
    from app.assistant.comparisons import build_comparison_writer
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from app.grounding.judge import GapDecision, SupportDecision, SupportReport
    from app.retrieval.types import (
        ComparisonResult,
        ComparisonTargetResult,
        RetrievalResult,
        RetrievalUsage,
    )
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = deps()
    for name, value in {
        "openai_chat_model": "gpt-4o-mini",
        "assistant_output_tokens": 3000,
        "assistant_output_retries": 1,
        "assistant_grounding_repairs": 1,
        "assistant_max_claims": 20,
        "assistant_claim_refs": 5,
        "openai_agent_request_limit": 20,
    }.items():
        setattr(d.settings, name, value)
    question = "Compare Apple and NVIDIA in 2025. Assess increased urgency."
    p = passage("We depend on outsourcing partners.").model_copy(
        update={"corpus_year": 2025}
    )
    targets = [
        SearchFilters(ticker=ticker, corpus_years=[2025]) for ticker in ("AAPL", "NVDA")
    ]
    retrievals = []

    class Retriever:
        async def compare(self, query, *, targets):
            retrievals.append(targets)
            return ComparisonResult(
                targets=[
                    ComparisonTargetResult(
                        target=target,
                        result=RetrievalResult(
                            passages=[p] if target.ticker == "AAPL" else []
                        ),
                    )
                    for target in targets
                ],
                usage=RetrievalUsage(),
            )

    d.retriever = Retriever()
    requests = []
    writer_requests = []

    def response(request):
        body = json.loads(request.content)
        requests.append(body)
        tools = {t["function"]["name"]: t["function"] for t in body["tools"]}
        if not retrievals:
            name = "compare_filings"
            args = {"query": question, "targets": [t.model_dump() for t in targets]}
            assert tools[name]["parameters"]["properties"]["targets"]["minItems"] == 1
            assert tools[name]["parameters"]["properties"]["targets"]["maxItems"] == 25
            if first_failure == "invalid_plan" and len(requests) == 1:
                args["targets"] = []
        else:
            assert set(tools) == {"final_result"}
            schema = tools["final_result"]["parameters"]
            assert schema["$defs"]["ComparisonGap"]["properties"]["request_id"][
                "enum"
            ] == ["R1", "R2"]
            assert "request_quote" not in schema["$defs"]["ComparisonGap"]["properties"]
            writer_requests.append(body)
            if first_failure == "submission" and len(writer_requests) == 2:
                history_text = json.dumps(body["messages"])
                assert p.text in history_text
                assert "Unknown evidence IDs" in history_text
            bad = first_failure in (
                "submission",
                "both_bad",
                "submission_then_grounding",
            ) and (len(writer_requests) == 1 or first_failure == "both_bad")
            name = "final_result"
            args = {
                "claims": [
                    {
                        "text": p.text,
                        "kind": "fact",
                        "evidence_ids": ["E999" if bad else "E1"],
                        "calculation_id": None,
                    }
                ],
                "gaps": [
                    {
                        "request_id": "R2",
                        "target": None,
                        "reason": "missing_evidence",
                        "missing_detail": "The retrieved wording does not establish an urgency trend.",
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": f"guided-{len(requests)}",
                "created": 0,
                "object": "chat.completion",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": f"call-{len(requests)}",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": json.dumps(args),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    def verdict(supported):
        return SupportReport(
            decisions=[
                SupportDecision(
                    claim_index=0,
                    supported=supported,
                    reason="supported" if supported else "unsupported_fact",
                    evidence_assessment="Fixture support decision.",
                )
            ],
            gap_decisions=[
                GapDecision(
                    gap_index=0,
                    request_id="R2",
                    warranted=True,
                    evidence_assessment="Trend remains unverified.",
                ),
                GapDecision(
                    gap_index=1,
                    warranted=True,
                    evidence_assessment="Requested target has no cited facts.",
                ),
            ],
        )

    judge = StubAgent(
        [verdict(False)]
        if first_failure == "submission_then_grounding"
        else [verdict(False), verdict(True)]
        if first_failure == "grounding"
        else [verdict(True)]
    )

    async def check():
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(response)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            return await run_grounded(
                question,
                [],
                d,
                build_agent(d.settings, client),
                judge,
                comparison_writer=build_comparison_writer(d.settings, client),
            )

    if first_failure in ("both_bad", "submission_then_grounding"):
        with pytest.raises(GroundingRejected):
            asyncio.run(check())
        assert len(judge.calls) == (
            1 if first_failure == "submission_then_grounding" else 0
        )
    else:
        result = asyncio.run(check())
        assert result.answer.gaps[0].request_quote == "Assess increased urgency."
        assert result.answer.gaps[1].target.ticker == "NVDA"
        assert len(judge.calls) == (2 if first_failure == "grounding" else 1)
    assert len(retrievals) == 1
    assert len(writer_requests) == (1 if first_failure in (None, "invalid_plan") else 2)
    assert d.generator_usage.requests == len(requests)
    assert d.tool_calls == 1


@pytest.mark.parametrize(
    "request_id,warranted", [("R2", True), ("R1", False), (None, False)]
)
def test_guided_judge_checks_request_id_without_quote_echo(request_id, warranted):
    from app.assistant.outputs import EvidenceGap, GroundedAnswer
    from app.grounding.judge import (
        GapDecision,
        SupportReport,
        judge_answer,
        judge_prompt,
    )
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = deps()
    question = "Compare Apple and NVIDIA. Assess increased urgency."
    d.registry.request_spans = request_spans(question)
    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                request_quote="Assess increased urgency.",
                reason="missing_evidence",
                missing_detail="Trend unverified.",
            )
        ],
    )
    judge = StubAgent(
        [
            SupportReport(
                decisions=[],
                gap_decisions=[
                    GapDecision(
                        gap_index=0,
                        request_id=request_id,
                        warranted=True,
                        evidence_assessment="Fixture verdict.",
                    )
                ],
            )
        ]
    )
    report = asyncio.run(judge_answer(question, answer, d.registry, judge))
    assert report.gap_decisions[0].warranted is warranted
    payload = json.loads(judge_prompt(question, answer, d.registry))
    assert payload["actual_user_request"]["spans"]["R2"] == "Assess increased urgency."
    assert payload["proposed_answer"]["gaps"][0]["request_id"] == "R2"


def test_twenty_five_empty_targets_keep_coverage_and_requested_aspect_gap():
    d = deps()
    d.question = "Compare all targets. Assess urgency."
    d.registry.request_spans = request_spans(d.question)
    d.registry.comparison_targets = [
        SearchFilters(ticker=ticker, corpus_years=[year])
        for ticker in ("AAPL", "NVDA", "MSFT", "AMZN", "GOOGL")
        for year in range(2021, 2026)
    ]
    result = final_comparison_answer(
        SimpleNamespace(deps=d),
        [],
        [
            ComparisonGap(
                request_id="R2",
                target=None,
                reason="missing_evidence",
                missing_detail="Urgency trend unverified.",
            )
        ],
    )
    assert len(result.gaps) == 26
    assert {gap.target.model_dump_json() for gap in result.gaps if gap.target} == {
        target.model_dump_json() for target in d.registry.comparison_targets
    }


def test_request_span_catalog_is_bounded_even_for_many_tiny_sentences():
    question = "a. " * 5000
    spans = request_spans(question)
    assert len(spans) <= 40
    assert all(text in question for text in spans.values())


@pytest.mark.parametrize("budget", ["tools", "searches"])
def test_comparison_plan_output_is_hidden_when_budget_is_exhausted(budget):
    from pydantic_ai.tools import ToolDefinition

    from app.assistant.agent import EvidenceChoices

    d = deps()
    if budget == "tools":
        d.tool_calls = d.settings.assistant_tool_calls
    else:
        d.searches = d.settings.assistant_search_calls
    tool = ToolDefinition(
        name="compare_filings", parameters_json_schema={"type": "object"}
    )
    assert (
        asyncio.run(
            EvidenceChoices().prepare_output_tools(SimpleNamespace(deps=d), [tool])
        )
        == []
    )


def test_invalid_expanded_comparison_plan_executes_no_retrieval():
    from app.assistant.comparisons import prepare_comparison

    d = deps()
    target = SearchFilters(
        ticker="AAPL", corpus_years=list(range(2000, 2025)), fiscal_years=[2021, 2022]
    )
    with pytest.raises(ModelRetry, match="25"):
        asyncio.run(prepare_comparison(SimpleNamespace(deps=d), "Compare", [target]))
    assert d.tool_calls == d.searches == 0


def test_gap_only_comparison_cannot_bypass_semantic_judging():
    from app.assistant.comparisons import ComparisonReady
    from app.assistant.outputs import EvidenceGap, GroundedAnswer
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from app.grounding.judge import GapDecision, SupportReport
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = deps()
    for name, value in {
        "openai_agent_request_limit": 20,
        "assistant_grounding_repairs": 1,
        "assistant_max_claims": 20,
        "assistant_claim_refs": 5,
    }.items():
        setattr(d.settings, name, value)
    question = "Compare Apple. Assess urgency."
    d.registry.request_spans = request_spans(question)
    d.completed_retrievals = 1
    draft = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                request_quote="Assess urgency.",
                reason="missing_evidence",
                missing_detail="An unrequested verification requirement.",
            )
        ],
    )
    verdict = SupportReport(
        decisions=[],
        gap_decisions=[
            GapDecision(
                gap_index=0,
                request_id="R2",
                warranted=False,
                evidence_assessment="The limitation does not match the user's request.",
            )
        ],
    )
    planner = StubAgent([ComparisonReady(evidence="[Source fixture]")])
    writer = StubAgent([draft, draft])
    judge = StubAgent([verdict, verdict])
    with pytest.raises(GroundingRejected):
        asyncio.run(
            run_grounded(question, [], d, planner, judge, comparison_writer=writer)
        )
    assert len(planner.calls) == 1
    assert len(writer.calls) == len(judge.calls) == 2


@pytest.mark.parametrize("omit_key", [False, True])
def test_guided_judge_wire_requires_one_verdict_per_server_owned_key(omit_key):
    import httpx
    from openai import AsyncOpenAI

    from app.assistant.outputs import (
        AnswerClaim,
        EvidenceGap,
        EvidenceRef,
        GroundedAnswer,
    )
    from app.grounding.judge import build_judge, judge_answer

    d = deps()
    question = "Compare Apple and NVIDIA. Assess urgency."
    d.registry.request_spans = request_spans(question)
    p = passage("We depend on suppliers.")
    d.registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="partial",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
        gaps=[
            EvidenceGap(
                reason="missing_evidence",
                request_quote="Assess urgency.",
                missing_detail="Trend unverified.",
            ),
            EvidenceGap(target=SearchFilters(ticker="NVDA"), reason="missing_evidence"),
        ],
    )
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        schema = body["tools"][0]["function"]["parameters"]
        report_schema = schema
        assert set(report_schema["properties"]) == {"C0", "G0", "G1"}
        assert set(report_schema["required"]) == {"C0", "G0", "G1"}
        assert report_schema["additionalProperties"] is False
        assert "claim_index" not in schema["$defs"]["ClaimVerdict"]["properties"]
        assert "gap_index" not in schema["$defs"]["GapVerdict"]["properties"]
        output = {
            "C0": {
                "evidence_assessment": "Quoted supplier reliance.",
                "supported": True,
                "reason": "supported",
            },
            "G0": {
                "request_id": "R2",
                "request_quote": None,
                "warranted": True,
                "evidence_assessment": "Trend remains unverified.",
            },
            "G1": {
                "request_id": None,
                "request_quote": None,
                "warranted": True,
                "evidence_assessment": "No cited facts for NVIDIA.",
            },
        }
        if omit_key:
            del output["G1"]
        return httpx.Response(
            200,
            json={
                "id": "fixed-verdict-keys",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "verdict",
                                    "type": "function",
                                    "function": {
                                        "name": "final_result",
                                        "arguments": json.dumps(output),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    async def check():
        config = SimpleNamespace(
            openai_grounding_model="gpt-4.1-mini",
            grounding_output_tokens=2000,
            assistant_reasoning_effort="none",
        )
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            report = await judge_answer(
                question, answer, d.registry, build_judge(config, client)
            )
            assert [decision.claim_index for decision in report.decisions] == [0]
            assert [decision.gap_index for decision in report.gap_decisions] == [0, 1]

    if omit_key:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        with pytest.raises(UnexpectedModelBehavior):
            asyncio.run(check())
    else:
        asyncio.run(check())
    assert len(requests) == 1
