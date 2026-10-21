"""Exercise the facts-only comparison writer through the real writer/repair boundary."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.assistant.comparisons import ComparisonReady, build_comparison_writer
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


FACTS = [
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


@pytest.mark.parametrize(
    "repeated_bad,judge_support", [(False, True), (True, True), (False, False)]
)
def test_writer_offers_only_displayed_facts_and_repairs_an_interpretation(
    repeated_bad, judge_support
):
    d = citation_deps()
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        schema = body["tools"][0]["function"]["parameters"]
        assert "ComparisonInterpretation" not in schema["$defs"]
        assert schema["properties"]["claims"]["items"] == {
            "$ref": "#/$defs/ComparisonFact"
        }
        ids = schema["$defs"]["ComparisonFact"]["properties"]["evidence_ids"]
        assert ids["items"]["enum"] == [f"E{i}" for i in range(1, 7)]
        if len(requests) == 1 or repeated_bad:
            # The live failure shape: a cross-filing trend written as a claim.
            claims = [
                {
                    "text": "Apple and NVIDIA supplier wording shifts over time.",
                    "kind": "interpretation",
                    "evidence_ids": ["E1", "E6"],
                    "calculation_id": None,
                }
            ]
        else:
            claims = FACTS
        return completion({"claims": claims, "gaps": []}, len(requests))

    judge = StubAgent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=i,
                        supported=judge_support,
                        reason="supported" if judge_support else "unsupported_fact",
                        evidence_assessment="Mock verdict.",
                    )
                    for i in range(2)
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
        assert [claim.kind for claim in result.answer.claims] == ["fact", "fact"]
        assert len(judge.calls) == 1
    assert len(requests) == 2
    assert d.generator_usage.requests == 2


@pytest.mark.parametrize("empty_corpus", [False, True])
def test_writer_cites_only_observed_evidence_or_reports_gaps(empty_corpus):
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
        fact = schema["$defs"]["ComparisonFact"]["properties"]
        if empty_corpus:
            assert schema["properties"]["claims"]["maxItems"] == 0
        else:
            assert fact["evidence_ids"]["items"]["enum"] == [
                f"E{i}" for i in range(1, 6)
            ]
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


def test_fact_choices_fit_the_existing_span_budget():
    from pydantic import create_model

    from app.assistant.comparison_citations import (
        ComparisonFact,
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
    schema = create_model(
        "Submission", __base__=Contract, claims=(list[ComparisonFact], ...)
    ).model_json_schema()
    prepare_comparison_citations(schema, d)
    enum = schema["$defs"]["ComparisonFact"]["properties"]["evidence_ids"]["items"][
        "enum"
    ]
    assert len(enum) == len(set(enum)) == MAX_EVIDENCE_SPANS


@pytest.mark.parametrize("company_count", [1, 2, 3, 5, 6])
def test_writer_wire_schema_needs_no_strict_mode_rewrite(company_count):
    from copy import deepcopy

    from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer

    d = citation_deps()
    tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META"][:company_count]
    d.registry.comparison_targets = [SearchFilters(ticker=t) for t in tickers]
    for ticker in tickers[2:]:
        p = passage().model_copy(update={"ticker": ticker})
        d.registry.evidence_id(p, p.text)
    tools = []

    def respond(request):
        tools.extend(json.loads(request.content)["tools"])
        return completion({"claims": [], "gaps": []}, 1)

    async def check():
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(
                api_key="offline-test", max_retries=0, http_client=http
            ) as client,
        ):
            await build_comparison_writer(d.settings, client).run(d.question, deps=d)

    asyncio.run(check())
    (function,) = [tool["function"] for tool in tools]
    schema = function["parameters"]
    assert function["strict"] is True
    assert schema["type"] == "object" and "anyOf" not in schema
    # Enum fragments are added after pydantic-ai's strict-mode rewrite, so the
    # schema actually sent must already be a fixed point of it.
    assert OpenAIJsonSchemaTransformer(deepcopy(schema), strict=True).walk() == schema
    assert "ComparisonInterpretation" not in schema["$defs"]
