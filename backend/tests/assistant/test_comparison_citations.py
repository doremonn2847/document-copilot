"""Exercise company-scoped selection through the real writer/repair boundary."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.assistant.comparisons import ComparisonReady, build_comparison_writer
from app.assistant.selection import SelectedClaim
from app.chat.orchestrator import GroundingRejected, run_grounded
from app.config import settings
from app.grounding.judge import SupportDecision, SupportReport
from app.retrieval.types import SearchFilters
from tests.assistant.test_contracts import passage
from tests.assistant.test_orchestrator import Agent as StubAgent
from tests.assistant.test_tools import deps


def citation_deps():
    d = deps()
    d.settings = settings.model_copy(
        update={
            "openai_chat_model": "gpt-4o-mini",
            "assistant_reasoning_effort": "minimal",
        }
    )
    d.question = "Compare Apple and NVIDIA supplier risks."
    d.completed_retrievals = 1
    d.registry.comparison_targets = [
        SearchFilters(ticker=ticker) for ticker in ("AAPL", "NVDA")
    ]
    for ticker, year in [("AAPL", y) for y in range(2021, 2026)] + [("NVDA", 2025)]:
        p = passage("We depend on suppliers.").model_copy(
            update={"ticker": ticker, "corpus_year": year}
        )
        d.registry.evidence_id(p, p.text)
    return d


def completion(args, index):
    return httpx.Response(
        200,
        json={
            "id": f"grouped-{index}",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": f"claim-{index}",
                                "type": "function",
                                "function": {
                                    "name": "final_result",
                                    "arguments": json.dumps(args),
                                },
                            }
                        ],
                    },
                }
            ],
        },
    )


@pytest.mark.parametrize(
    "repeated_bad,judge_support", [(False, True), (True, True), (False, False)]
)
def test_writer_requires_company_groups_and_repairs_captured_flat_selection(
    repeated_bad, judge_support
):
    d = citation_deps()
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        schema = body["tools"][0]["function"]["parameters"]
        groups = schema["$defs"]["ComparisonInterpretation"]["properties"][
            "evidence_by_company"
        ]
        for allocation in groups["anyOf"]:
            assert set(allocation["required"]) == {"AAPL", "NVDA"}
            assert allocation["additionalProperties"] is False
            assert (
                sum(item["maxItems"] for item in allocation["properties"].values()) == 5
            )
            for ticker, ids in {
                "AAPL": [f"E{i}" for i in range(1, 6)],
                "NVDA": ["E6"],
            }.items():
                branch = allocation["properties"][ticker]
                assert branch["minItems"] == 1
                definition = schema["$defs"][branch["items"]["$ref"].split("/")[-1]]
                assert definition["enum"] == ids
        if len(requests) == 1 or repeated_bad:
            # The exact failure pattern from both live drafts: five Apple IDs.
            claim = SelectedClaim(
                text="Apple and NVIDIA describe supplier dependence.",
                kind="interpretation",
                evidence_ids=[f"E{i}" for i in range(1, 6)],
            ).model_dump(mode="json")
        else:
            history = json.dumps(body["messages"])
            assert "evidence_by_company" in history
            assert "original comparison evidence" in history
            claim = {
                "text": "Apple and NVIDIA describe supplier dependence.",
                "kind": "interpretation",
                "evidence_by_company": {"AAPL": ["E1"], "NVDA": ["E6"]},
            }
        return completion({"claims": [claim], "gaps": []}, len(requests))

    judge = StubAgent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=0,
                        supported=judge_support,
                        reason="supported"
                        if judge_support
                        else "unsupported_interpretation",
                        evidence_assessment="Mock verdict.",
                    )
                ]
            )
        ]
    )

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
                StubAgent([ComparisonReady(evidence="original comparison evidence")]),
                judge,
                comparison_writer=build_comparison_writer(d.settings, client),
            )

    if repeated_bad or not judge_support:
        with pytest.raises(GroundingRejected):
            asyncio.run(check())
        assert len(judge.calls) == (0 if repeated_bad else 1)
    else:
        result = asyncio.run(check())
        refs = result.answer.claims[0].evidence
        assert {d.registry.passages[r.chunk_id].ticker for r in refs} == {
            "AAPL",
            "NVDA",
        }
        assert len(judge.calls) == 1
    assert len(requests) == 2
    assert d.generator_usage.requests == 2


@pytest.mark.parametrize(
    "groups",
    [
        {"AAPL": ["E1"]},
        {"AAPL": ["E1"], "NVDA": ["E2"]},
        {"AAPL": ["E1"], "NVDA": ["E999"]},
        {"AAPL": ["E1"], "NVDA": ["E6"], "MSFT": ["E1"]},
        {"AAPL": [f"E{i}" for i in range(1, 6)], "NVDA": ["E6"]},
    ],
)
def test_group_resolution_rejects_missing_foreign_unknown_extra_and_over_budget_sources(
    groups,
):
    from pydantic_ai import ModelRetry

    from app.assistant.comparison_citations import (
        ComparisonInterpretation,
        resolve_comparison_claim,
    )

    d = citation_deps()
    claim = ComparisonInterpretation(
        text="Apple and NVIDIA describe dependence.", evidence_by_company=groups
    )
    before = dict(d.registry.evidence_refs)
    with pytest.raises(ModelRetry):
        resolve_comparison_claim(claim, d)
    assert d.registry.evidence_refs == before
    assert claim.evidence_by_company == groups


def test_group_resolution_preserves_only_selected_quotes_and_five_reference_total():
    from types import SimpleNamespace

    from app.assistant.comparison_citations import (
        ComparisonInterpretation,
        resolve_comparison_claim,
    )
    from app.assistant.comparisons import final_comparison_answer

    d = citation_deps()
    claim = ComparisonInterpretation(
        text="Apple and NVIDIA describe dependence.",
        evidence_by_company={"NVDA": ["E6"], "AAPL": ["E1", "E2", "E3", "E4"]},
    )
    selected = resolve_comparison_claim(claim, d)
    assert selected.evidence_ids == ["E1", "E2", "E3", "E4", "E6"]
    answer = final_comparison_answer(SimpleNamespace(deps=d), [claim], [])
    assert list(answer.claims[0].evidence) == [
        d.registry.evidence_refs[k] for k in selected.evidence_ids
    ]
    assert not answer.gaps


@pytest.mark.parametrize("empty_corpus", [False, True])
def test_missing_company_hides_interpretations_and_keeps_fact_or_gap_path(empty_corpus):
    d = citation_deps()
    d.registry.evidence_refs = (
        {}
        if empty_corpus
        else {key: ref for key, ref in d.registry.evidence_refs.items() if key != "E6"}
    )
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        schema = body["tools"][0]["function"]["parameters"]
        assert "ComparisonInterpretation" not in schema["$defs"]
        assert schema["properties"]["claims"]["items"] == {
            "$ref": "#/$defs/ComparisonFact"
        }
        if empty_corpus:
            assert schema["properties"]["claims"]["maxItems"] == 0
        return completion({"claims": [], "gaps": []}, 1)

    async def check():
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(
                api_key="offline-test", max_retries=0, http_client=http
            ) as client,
        ):
            return await build_comparison_writer(d.settings, client).run(
                d.question, deps=d
            )

    result = asyncio.run(check())
    assert not result.output.claims
    assert {g.target.ticker for g in result.output.gaps} == {"AAPL", "NVDA"}
    assert len(requests) == 1


def test_single_company_multi_year_interpretation_uses_one_required_group():
    from app.assistant.comparison_citations import (
        ComparisonInterpretation,
        resolve_comparison_claim,
    )

    d = citation_deps()
    d.registry.comparison_targets = [
        SearchFilters(ticker="AAPL", corpus_years=[2021, 2025])
    ]
    claim = ComparisonInterpretation(
        text="Apple describes supplier dependence in both selected periods.",
        evidence_by_company={"AAPL": ["E1", "E5"]},
    )
    assert resolve_comparison_claim(claim, d).evidence_ids == ["E1", "E5"]


def test_company_enums_share_definitions_at_the_existing_span_budget():
    from pydantic import create_model

    from app.assistant.comparison_citations import (
        ComparisonFact,
        ComparisonInterpretation,
        prepare_comparison_citations,
    )
    from app.assistant.deps import MAX_EVIDENCE_SPANS
    from app.assistant.outputs import Contract

    d = citation_deps()
    d.registry.evidence_refs.clear()
    tickers = ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]
    d.registry.comparison_targets = [SearchFilters(ticker=t) for t in tickers]
    for ticker in tickers:
        spans = [f"Observed source {i}." for i in range(MAX_EVIDENCE_SPANS // 5)]
        p = passage(" ".join(spans)).model_copy(update={"ticker": ticker})
        for span in spans:
            d.registry.evidence_id(p, span)
    submission = create_model(
        "Submission",
        __base__=Contract,
        claims=(list[ComparisonFact | ComparisonInterpretation], ...),
    )
    schema = submission.model_json_schema()
    prepare_comparison_citations(schema, d)
    evidence_choices = [
        key
        for definition in schema["$defs"].values()
        for key in definition.get("enum", [])
        if isinstance(key, str) and key.startswith("E")
    ]
    assert len(evidence_choices) == len(set(evidence_choices)) == MAX_EVIDENCE_SPANS


@pytest.mark.parametrize("company_count", [1, 2, 3, 4, 5])
def test_wire_schema_enforces_five_total_references_without_losing_valid_allocations(
    company_count,
):
    from itertools import product

    from pydantic import create_model

    from app.assistant.comparison_citations import (
        ComparisonFact,
        ComparisonInterpretation,
        prepare_comparison_citations,
    )
    from app.assistant.outputs import Contract

    d = citation_deps()
    tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL"][:company_count]
    d.registry.comparison_targets = [SearchFilters(ticker=t) for t in tickers]
    for ticker in tickers[2:]:
        p = passage().model_copy(update={"ticker": ticker})
        d.registry.evidence_id(p, p.text)
    submission = create_model(
        "Submission",
        __base__=Contract,
        claims=(list[ComparisonFact | ComparisonInterpretation], ...),
    )
    schema = submission.model_json_schema()
    prepare_comparison_citations(schema, d)
    groups = schema["$defs"]["ComparisonInterpretation"]["properties"][
        "evidence_by_company"
    ]
    branches = groups.get("anyOf", [groups])
    for counts in product(range(6), repeat=company_count):
        allowed = any(
            all(
                branch["properties"][ticker]["minItems"]
                <= count
                <= branch["properties"][ticker]["maxItems"]
                for ticker, count in zip(tickers, counts)
            )
            for branch in branches
        )
        assert allowed == (min(counts) >= 1 and sum(counts) <= 5), counts
