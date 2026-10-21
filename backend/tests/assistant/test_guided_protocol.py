import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.assistant.agent import build_agent
from app.assistant.facts import prepare_facts
from app.assistant.tools import calculate
from app.chat.orchestrator import run_grounded
from app.grounding.judge import SupportDecision, SupportReport
from app.retrieval.types import RetrievalResult
from tests.assistant.test_numeric_facts import prepared_context
from tests.assistant.test_orchestrator import Agent


@pytest.mark.parametrize("verified", [False, True])
def test_calculator_output_rejects_unverified_or_reordered_fact_ids(verified):
    from types import SimpleNamespace
    from uuid import uuid4

    from pydantic_ai import ModelRetry

    d, _, p = prepared_context()

    async def attempt():
        if verified:
            ready = await prepare_facts(d, p.text)
            first, second = ready.second_fact_id, ready.first_fact_id
        else:
            first, second = uuid4(), uuid4()
        with pytest.raises(ModelRetry, match="ordered fact IDs"):
            await calculate(SimpleNamespace(deps=d), first, second)

    asyncio.run(attempt())
    assert d.registry.calculations == {}


@pytest.mark.parametrize("stale_year", [None, 2025])
def test_guided_provider_steps_retrieve_verify_calculate_and_render_without_network(
    stale_year,
):
    d, _, p = prepared_context()
    for key, value in {
        "openai_chat_model": "gpt-4o-mini",
        "assistant_output_tokens": 3000,
        "assistant_output_retries": 1,
        "assistant_max_claims": 20,
        "assistant_claim_refs": 5,
    }.items():
        setattr(d.settings, key, value)
    requests = []

    async def search(*args, **kwargs):
        assert kwargs["filters"] is None or kwargs["filters"].corpus_years is None
        return RetrievalResult(passages=[p])

    d.retriever = type("Retriever", (), {"search": staticmethod(search)})()

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            assert all(t["function"]["name"] != "calculate" for t in body["tools"])
            name, args = (
                "prepare_calculation",
                {
                    "query": d.question,
                    "filters": {"ticker": "MSFT", "corpus_years": [stale_year]}
                    if stale_year
                    else None,
                },
            )
        elif len(requests) == 2:
            assert all(t["function"]["name"] != "final_result" for t in body["tools"])
            name = "calculate"
            first, second = next(iter(d.registry.calculation_pairs))
            args = {"first_fact_id": str(first), "second_fact_id": str(second)}
            tool = next(
                t["function"]
                for t in body["tools"]
                if t["function"]["name"] == "calculate"
            )
            assert tool["strict"] is True
            properties = tool["parameters"]["properties"]
            assert tool["parameters"]["additionalProperties"] is False
            assert set(tool["parameters"]["required"]) == set(properties)
            assert set(properties) == {"first_fact_id", "second_fact_id"}
            assert properties["first_fact_id"]["enum"] == [str(first)]
            assert properties["second_fact_id"]["enum"] == [str(second)]
        else:
            raise AssertionError("No model submission should be needed after calculate")
        assert body["tool_choice"] == {"type": "function", "function": {"name": name}}
        return httpx.Response(
            200,
            json={
                "id": "guided-probe",
                "created": 0,
                "model": "gpt-4o-mini",
                "object": "chat.completion",
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

    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        evidence_assessment="Fixture verdict.",
                        claim_index=i,
                        supported=True,
                        reason="supported",
                    )
                    for i in range(n)
                ]
            )
            for n in (2, 1)
        ]
    )

    async def check():
        d.fact_judge = judge
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            return await run_grounded(
                d.question,
                [
                    {
                        "role": "user",
                        "content": "Describe Azure in the 2025 MSFT filing.",
                    }
                ],
                d,
                build_agent(d.settings, client),
                judge,
            )

    result = asyncio.run(check())
    assert result.answer.status == "answered" and "65.56 %" in result.reply.text
    assert len(requests) == 2 and len(judge.calls) == 1
    assert d.tool_calls == 2 and d.completed_retrievals == 1
    citations = [
        part["data"] for part in result.reply.parts if part["type"] == "data-citation"
    ]
    assert len(citations) == 3
    assert {c["chunk_id"] for c in citations} == {str(p.chunk_id)}
    assert result.diagnostics["calculation_count"] == 1
    assert result.diagnostics["numeric_attempts"][0]["filter_adjusted"] is bool(
        stale_year
    )
