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
from app.assistant.rendering import WITHHELD_NOTICE
from app.assistant.selection import SelectedClaim
from app.assistant.tools import expose_groups
from app.retrieval.types import SearchFilters
from tests.assistant.test_contracts import assertions_for, passage
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
                    assertions=assertions_for(p.text),
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


def test_guided_judge_sees_evidence_shown_for_each_gap_target():
    # Live answer: "no Apple 2024 supplier wording" was judged warranted although
    # the writer had been shown Apple 2024 supplier-risk quotes.
    from app.assistant.outputs import EvidenceGap, GroundedAnswer
    from app.grounding.judge import judge_prompt

    d = deps()
    question = "Compare Apple and NVIDIA supplier risks. Assess urgency."
    apple = passage("Global supply chains can be highly concentrated.").model_copy(
        update={"corpus_year": 2024}
    )
    hidden = passage("Apple suppliers face industrial accidents.").model_copy(
        update={"corpus_year": 2024}
    )
    nvidia = passage("NVIDIA relies on foundries.").model_copy(
        update={"ticker": "NVDA", "corpus_year": 2024}
    )
    for p in (apple, hidden, nvidia):
        d.registry.evidence_id(p, p.text)
    d.registry.comparison_evidence_ids = ["E1", "E3"]
    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="AAPL", corpus_years=[2024]),
                reason="missing_evidence",
            ),
            EvidenceGap(
                request_quote="Assess urgency.",
                reason="missing_evidence",
                missing_detail="Trend unverified.",
            ),
        ],
    )
    d.registry.request_spans = request_spans(question)
    gaps = json.loads(judge_prompt(question, answer, d.registry))["proposed_answer"][
        "gaps"
    ]
    assert gaps[0]["displayed_target_evidence"] == {
        "quotes": [{"exact_quote": apple.text, "corpus_year": 2024}],
        "omitted": 0,
    }
    assert "displayed_target_evidence" not in gaps[1]
    # Ordinary (non-guided) judging keeps its existing payload.
    d.registry.request_spans = {}
    gaps = json.loads(judge_prompt(question, answer, d.registry))["proposed_answer"][
        "gaps"
    ]
    assert "displayed_target_evidence" not in gaps[0]


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


def test_comparison_writer_selects_only_evidence_shown_in_its_frozen_prompt():
    from pydantic import create_model

    from app.assistant.comparison_citations import (
        ComparisonFact,
        ComparisonInterpretation,
        prepare_comparison_citations,
        resolve_comparison_claim,
    )
    from app.assistant.comparisons import prepare_comparison
    from app.assistant.outputs import Contract
    from app.retrieval.types import (
        ComparisonResult,
        ComparisonTargetResult,
        RetrievalResult,
        RetrievalUsage,
    )

    d = deps()
    d.question = "Compare Apple and NVIDIA supplier risks."
    earlier = passage("Apple sells products online.")
    shared = passage("Apple relies on outsourcing partners.")
    nvidia = passage("NVIDIA relies on foundry partners.").model_copy(
        update={"ticker": "NVDA"}
    )
    # A planner search before the handoff exposes E1 (unused) and E2 (reused below).
    expose_groups(d, [("Search", [earlier, shared])])

    class Retriever:
        async def compare(self, query, *, targets):
            return ComparisonResult(
                targets=[
                    ComparisonTargetResult(
                        target=t,
                        result=RetrievalResult(
                            passages=[shared] if t.ticker == "AAPL" else [nvidia]
                        ),
                    )
                    for t in targets
                ],
                usage=RetrievalUsage(),
            )

    d.retriever = Retriever()
    targets = [SearchFilters(ticker=t) for t in ("AAPL", "NVDA")]
    ready = asyncio.run(
        prepare_comparison(SimpleNamespace(deps=d), "supplier risks", targets)
    )
    assert "[E1]" not in ready.evidence
    assert d.registry.comparison_evidence_ids == ["E2", "E3"]

    schema = create_model(
        "Submission",
        __base__=Contract,
        claims=(list[ComparisonFact | ComparisonInterpretation], ...),
    ).model_json_schema()
    prepare_comparison_citations(schema, d)
    choices = {
        key
        for definition in schema["$defs"].values()
        for key in definition.get("enum", [])
        if isinstance(key, str)
    }
    assert choices == {"E2", "E3"}

    def interpretation(apple_ids):
        return ComparisonInterpretation(
            text="Apple and NVIDIA rely on manufacturing partners.",
            evidence_by_company={"AAPL": apple_ids, "NVDA": ["E3"]},
        )

    assert resolve_comparison_claim(interpretation(["E2"]), d).evidence_ids == [
        "E2",
        "E3",
    ]
    with pytest.raises(ModelRetry):
        resolve_comparison_claim(interpretation(["E1"]), d)
    with pytest.raises(ModelRetry, match="Unknown evidence IDs"):
        final_comparison_answer(
            SimpleNamespace(deps=d),
            [ComparisonFact(text=earlier.text, evidence_ids=["E1"])],
            [],
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


def withholding_deps():
    from tests.assistant.test_comparison_citations import citation_deps

    d = citation_deps()
    d.settings = d.settings.model_copy(
        update={
            "assistant_grounding_repairs": 1,
            "assistant_max_claims": 20,
            "assistant_claim_refs": 5,
            "openai_agent_request_limit": 20,
        }
    )
    # As prepare_comparison does, so judge payloads carry shown target evidence.
    d.registry.request_spans = request_spans(d.question)
    return d


def verdicts(*supported, gaps=()):
    from app.grounding.judge import GapDecision, SupportDecision, SupportReport

    return SupportReport(
        decisions=[
            SupportDecision(
                claim_index=i,
                supported=ok,
                assertions=assertions_for("We depend on suppliers."),
                reason="supported" if ok else "unsupported_interpretation",
                evidence_assessment="Fixture verdict.",
            )
            for i, ok in enumerate(supported)
        ],
        gap_decisions=[
            GapDecision(
                gap_index=i,
                request_id=request_id,
                warranted=warranted,
                evidence_assessment="Fixture gap verdict.",
            )
            for i, (warranted, request_id) in enumerate(gaps)
        ],
    )


def run_withholding(d, draft, judge, *, planner=None):
    from app.assistant.comparisons import ComparisonReady
    from app.chat.orchestrator import run_grounded
    from tests.assistant.test_orchestrator import Agent as StubAgent

    return asyncio.run(
        run_grounded(
            d.question,
            [],
            d,
            planner or StubAgent([ComparisonReady(evidence="[Source fixture]")]),
            judge,
            comparison_writer=StubAgent([draft, draft]),
        )
    )


def withheld_reports(d):
    return [r for r in d.validation_reports if r.get("stage") == "withheld"]


@pytest.mark.parametrize("failure", ["structural", "grounding", "grounding_uncovers"])
def test_final_guided_attempt_withholds_failed_claims_but_keeps_coverage(failure):
    from app.assistant.comparisons import ComparisonReady
    from app.assistant.outputs import AnswerClaim, GroundedAnswer
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    refs = d.registry.evidence_refs
    interpretation = (
        "Apple repeats supplier dependence in its 2023 filing."
        if failure == "structural"
        else "Apple repeats supplier dependence across filings."
    )
    draft = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(text="Apple depends on suppliers.", evidence=[refs["E1"]]),
            AnswerClaim(
                text=interpretation,
                kind="interpretation",
                evidence=[refs["E1"], refs["E2"]],
            ),
            AnswerClaim(text="NVIDIA depends on suppliers.", evidence=[refs["E6"]]),
        ],
    )
    if failure == "structural":
        # Attempt 0 fails structurally (uncited 2023) and never reaches the judge.
        judge = StubAgent([verdicts(True, True)])
    elif failure == "grounding":
        judge = StubAgent([verdicts(True, False, True)] * 2)
    else:
        # Withholding NVIDIA's only claim would publish an unjudged coverage gap.
        judge = StubAgent([verdicts(True, True, False)] * 2)
    writer = StubAgent([draft, draft])

    def run():
        return asyncio.run(
            run_grounded(
                d.question,
                [],
                d,
                StubAgent([ComparisonReady(evidence="[Source fixture]")]),
                judge,
                comparison_writer=writer,
            )
        )

    if failure == "grounding_uncovers":
        with pytest.raises(GroundingRejected):
            run()
        assert not [r for r in d.validation_reports if r.get("stage") == "withheld"]
        return
    result = run()
    assert [claim.text for claim in result.answer.claims] == [
        "Apple depends on suppliers.",
        "NVIDIA depends on suppliers.",
    ]
    assert result.answer.status == "answered"
    assert result.reply.text.endswith(WITHHELD_NOTICE)
    (report,) = [r for r in d.validation_reports if r.get("stage") == "withheld"]
    assert report == {
        "stage": "withheld",
        "source": failure,
        "attempt": 1,
        "claims": [1],
        "gaps": [],
    }
    assert len(judge.calls) == (1 if failure == "structural" else 2)


@pytest.mark.parametrize("all_invalid", [False, True])
def test_final_guided_submission_withholds_invalid_claims_on_the_wire(all_invalid):
    import httpx
    from openai import AsyncOpenAI

    from app.assistant.comparisons import ComparisonReady, build_comparison_writer
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from tests.assistant.test_comparison_citations import completion
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    # Live draft: an Apple-only group carried a claim about both companies.
    both = {
        "text": "Both companies describe supplier dependence.",
        "kind": "interpretation",
        "evidence_by_company": {"AAPL": ["E1"]},
    }
    facts = [
        {
            "text": text,
            "kind": "fact",
            "evidence_ids": [key],
            "calculation_id": None,
        }
        for text, key in [
            ("Apple depends on suppliers.", "E1"),
            ("NVIDIA depends on suppliers.", "E6"),
        ]
    ]
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        claims = [both] if all_invalid else [facts[0], both, facts[1]]
        return completion({"claims": claims, "gaps": []}, len(requests))

    judge = StubAgent([verdicts(True, True)])

    async def check():
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(
                api_key="offline-test", max_retries=0, http_client=http
            ) as client,
        ):
            return await run_grounded(
                d.question,
                [],
                d,
                StubAgent([ComparisonReady(evidence="[Source fixture]")]),
                judge,
                comparison_writer=build_comparison_writer(d.settings, client),
            )

    if all_invalid:
        with pytest.raises(GroundingRejected):
            asyncio.run(check())
        assert len(judge.calls) == 0
    else:
        result = asyncio.run(check())
        assert [claim.text for claim in result.answer.claims] == [
            "Apple depends on suppliers.",
            "NVIDIA depends on suppliers.",
        ]
        # Only the final submission withholds; the first one went to repair.
        assert [r for r in d.validation_reports if r.get("stage") == "withheld"] == [
            {"stage": "withheld", "source": "submission", "claims": [1]}
        ]
        assert len(judge.calls) == 1
    assert len(requests) == 2


def facts_draft(d, *extra_claims, gaps=()):
    from app.assistant.outputs import AnswerClaim, GroundedAnswer

    refs = d.registry.evidence_refs
    claims = [
        AnswerClaim(text="Apple depends on suppliers.", evidence=[refs["E1"]]),
        *extra_claims,
    ]
    return GroundedAnswer(
        status="partial" if gaps else "answered", claims=claims, gaps=list(gaps)
    )


def test_final_attempt_withholds_an_unwarranted_model_gap_without_a_notice():
    from app.assistant.outputs import AnswerClaim, EvidenceGap
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    gap = EvidenceGap(
        request_quote=d.question,
        reason="missing_evidence",
        missing_detail="Supplier risk wording is not established.",
    )
    nvidia = AnswerClaim(
        text="NVIDIA depends on suppliers.", evidence=[d.registry.evidence_refs["E6"]]
    )
    judge = StubAgent([verdicts(True, True, gaps=[(False, "R1")])] * 2)
    result = run_withholding(d, facts_draft(d, nvidia, gaps=[gap]), judge)
    assert result.answer.status == "answered" and not result.answer.gaps
    assert WITHHELD_NOTICE not in result.reply.text
    assert withheld_reports(d) == [
        {
            "stage": "withheld",
            "source": "grounding",
            "attempt": 1,
            "claims": [],
            "gaps": [0],
        }
    ]


@pytest.mark.parametrize("warranted", [True, False])
def test_structural_withholding_sends_the_new_coverage_gap_to_the_judge(warranted):
    from app.assistant.outputs import AnswerClaim
    from app.chat.orchestrator import GroundingRejected
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    # NVIDIA's only claim states an uncited year, so withholding uncovers NVDA.
    nvidia = AnswerClaim(
        text="NVIDIA depends on suppliers in 2023.",
        evidence=[d.registry.evidence_refs["E6"]],
    )
    judge = StubAgent([verdicts(True, gaps=[(warranted, None)])])
    if not warranted:
        with pytest.raises(GroundingRejected):
            run_withholding(d, facts_draft(d, nvidia), judge)
        assert not withheld_reports(d)
    else:
        result = run_withholding(d, facts_draft(d, nvidia), judge)
        assert result.answer.status == "partial"
        (gap,) = result.answer.gaps
        assert gap.target.ticker == "NVDA" and gap.request_quote is None
        assert result.reply.text.endswith(WITHHELD_NOTICE)
    assert len(judge.calls) == 1


def test_grounding_withholding_refuses_to_leave_a_target_with_only_a_narrow_gap():
    from app.assistant.outputs import AnswerClaim, EvidenceGap
    from app.chat.orchestrator import GroundingRejected
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    nvidia = AnswerClaim(
        text="NVIDIA depends on suppliers.", evidence=[d.registry.evidence_refs["E6"]]
    )
    narrow = EvidenceGap(
        target=SearchFilters(ticker="NVDA"),
        request_quote=d.question,
        reason="missing_evidence",
        missing_detail="Supplier concentration percentages are not established.",
    )
    judge = StubAgent([verdicts(True, False, gaps=[(True, "R1")])] * 2)
    with pytest.raises(GroundingRejected):
        run_withholding(d, facts_draft(d, nvidia, gaps=[narrow]), judge)
    assert not withheld_reports(d)


@pytest.mark.parametrize("case", ["answer_level_error", "every_claim_fails"])
def test_final_attempt_fails_closed_when_withholding_cannot_isolate_failures(case):
    from app.assistant.outputs import AnswerClaim, GroundedAnswer
    from app.chat.orchestrator import GroundingRejected
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    refs = d.registry.evidence_refs
    bad = AnswerClaim(text="Apple depends on suppliers in 2023.", evidence=[refs["E1"]])
    if case == "answer_level_error":
        # "Claim limit exceeded" has no claim index, so nothing can be isolated.
        d.settings = d.settings.model_copy(update={"assistant_max_claims": 1})
        draft = facts_draft(d, bad)
    else:
        draft = GroundedAnswer(status="answered", claims=[bad])
    judge = StubAgent([])
    with pytest.raises(GroundingRejected):
        run_withholding(d, draft, judge)
    assert not withheld_reports(d) and not judge.calls


def test_financial_context_fallback_survives_structural_withholding():
    from app.assistant.outputs import AnswerClaim
    from app.grounding.validator import structural_errors
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    revenue = passage("Revenue was USD 100 million.").model_copy(
        update={"ticker": "NVDA"}
    )
    key = d.registry.evidence_id(revenue, revenue.text)
    figure = AnswerClaim(
        text="NVIDIA revenue was USD 100 million.",
        evidence=[d.registry.evidence_refs[key]],
    )
    draft = facts_draft(d, figure)
    errors = structural_errors(draft, d.registry, searches=1)
    assert errors and all(e.startswith("claim 1: financial") for e in errors)
    # The judge rejects the coverage gap that withholding the figure creates.
    judge = StubAgent([verdicts(True, gaps=[(False, None)])])
    result = run_withholding(d, draft, judge)
    assert result.answer.status == "insufficient_evidence"
    assert {gap.reason for gap in result.answer.gaps} == {"ambiguous_figures"}
    assert not withheld_reports(d)


def test_non_guided_answers_never_withhold_claims():
    from app.assistant.outputs import AnswerClaim
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from tests.assistant.test_orchestrator import Agent as StubAgent

    d = withholding_deps()
    d.registry.comparison_targets = []
    d.registry.request_spans = {}
    nvidia = AnswerClaim(
        text="NVIDIA depends on suppliers.", evidence=[d.registry.evidence_refs["E6"]]
    )
    draft = facts_draft(d, nvidia)
    judge = StubAgent([verdicts(True, False)] * 2)
    with pytest.raises(GroundingRejected):
        asyncio.run(run_grounded(d.question, [], d, StubAgent([draft, draft]), judge))
    assert not withheld_reports(d) and not d.prune_unverified
