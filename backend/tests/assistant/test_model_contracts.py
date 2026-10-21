import asyncio
import json
from types import SimpleNamespace

import httpx
from openai import AsyncOpenAI

from app.assistant.agent import build_agent
from app.assistant.facts import build_fact_extractor
from app.grounding.judge import build_judge


def test_judge_wire_separates_assistant_draft_from_actual_user_request():
    from app.assistant.deps import TurnRegistry
    from app.assistant.outputs import (
        AnswerClaim,
        EvidenceGap,
        EvidenceRef,
        GroundedAnswer,
    )
    from app.grounding.judge import judge_answer
    from tests.assistant.test_contracts import passage

    question = "What does Microsoft's 2025 filing say Azure provides?"
    p = passage("Azure provides compute.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
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
                request_quote="Azure provides",
                missing_detail="An explicit fiscal-period heading",
            )
        ],
    )
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "role-fixture",
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
                                        "arguments": json.dumps(
                                            {
                                                # Fixed verdict keys: indices are the backend's.
                                                "C0": {
                                                    "supported": True,
                                                    "reason": "supported",
                                                    "evidence_assessment": "Supported.",
                                                },
                                                "G0": {
                                                    "request_id": None,
                                                    "warranted": False,
                                                    "request_quote": None,
                                                    "evidence_assessment": "A fiscal heading was not requested.",
                                                },
                                            }
                                        ),
                                    },
                                },
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
            assistant_reasoning_effort="minimal",
        )
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            report = await judge_answer(
                question, answer, registry, build_judge(config, client)
            )
            assert report.gap_decisions[0].warranted is False

    asyncio.run(check())
    assert len(requests) == 1
    schema = requests[0]["tools"][0]["function"]["parameters"]
    assert schema["required"] == ["C0", "G0"]
    messages = requests[0]["messages"]
    assert messages[-1] == {"role": "user", "content": question}
    draft = json.loads(next(m["content"] for m in messages if m["role"] == "assistant"))
    assert draft["actual_user_request"]["text"] == question
    assert (
        draft["proposed_answer"]["gaps"][0]["missing_detail"]
        == "An explicit fiscal-period heading"
    )


def test_openai_requests_enforce_nested_tool_and_output_schemas():
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        output = (
            {
                "claims": [],
                "gaps": [
                    {
                        "target": None,
                        "reason": "outside_scope",
                        "request_quote": "Schema probe",
                    }
                ],
            }
            if len(requests) == 1
            else {"decisions": []}
            if len(requests) == 2
            else {
                "operation": None,
                "first_candidate_id": None,
                "second_candidate_id": None,
                "segment": None,
            }
        )
        return httpx.Response(
            200,
            json={
                "id": "schema-probe",
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
                                    "id": "output-1",
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
            openai_chat_model="gpt-4o-mini",
            openai_grounding_model="gpt-4o-mini",
            assistant_reasoning_effort="minimal",
            assistant_output_retries=1,
            assistant_output_tokens=3000,
            grounding_output_tokens=2000,
        )
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            from tests.assistant.test_tools import deps

            d = deps()
            d.question = "Schema probe"
            from app.assistant.tools import expose_groups
            from tests.assistant.test_contracts import passage

            expose_groups(
                d,
                [
                    (
                        "Source",
                        [passage("Azure provides compute. Azure provides storage.")],
                    )
                ],
            )
            await build_agent(config, client).run("Schema probe", deps=d)
            await build_judge(config, client).run("Schema probe")
            await build_fact_extractor(config, client).run("Schema probe")

    asyncio.run(check())

    def check_objects(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            assert "default" not in value
            for child in value.values():
                check_objects(child)
        elif isinstance(value, list):
            for child in value:
                check_objects(child)

    assert len(requests) == 3
    output_schema = next(
        t["function"]["parameters"]
        for t in requests[0]["tools"]
        if t["function"]["name"] == "final_result"
    )
    assert output_schema["$defs"]["SelectedClaim"]["properties"]["evidence_ids"][
        "items"
    ]["enum"] == ["E1", "E2"]
    assert "request_quote" in output_schema["$defs"]["RequestedGap"]["required"]
    for body in requests:
        for tool in body["tools"]:
            assert tool["function"].get("strict") is True
            check_objects(tool["function"]["parameters"])
    assert all(t["function"]["name"] != "calculate" for t in requests[0]["tools"])
