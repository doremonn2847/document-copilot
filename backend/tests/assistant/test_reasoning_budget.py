import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai.usage import RunUsage

from app.assistant.agent import build_agent
from app.assistant.facts import build_fact_extractor, build_input_judge
from app.grounding.judge import build_judge


def test_output_limit_is_classified_without_repair_or_private_error(monkeypatch):
    from uuid import uuid4

    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.usage import RequestUsage

    from app.assistant.model_settings import ModelOutputLimitExceeded
    from app.chat import orchestrator

    class Context:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def with_options(self, **kwargs):
            return self

    monkeypatch.setattr(orchestrator, "AsyncOpenAI", lambda **kwargs: Context())
    monkeypatch.setattr(
        orchestrator, "DocumentRetriever", lambda *args, **kwargs: Context()
    )
    for name in (
        "build_agent",
        "build_comparison_writer",
        "build_judge",
        "build_fact_extractor",
        "build_input_judge",
    ):
        monkeypatch.setattr(orchestrator, name, lambda *args: None)
    calls = []

    async def fail(*args, **kwargs):
        calls.append(True)
        raise ModelOutputLimitExceeded(
            "grounding",
            ModelResponse(
                parts=[],
                model_name="gpt-5-nano",
                finish_reason="length",
                usage=RequestUsage(
                    output_tokens=2000, details={"reasoning_tokens": 2000}
                ),
            ),
        )

    monkeypatch.setattr(orchestrator, "run_grounded", fail)
    with pytest.raises(orchestrator.AssistantFailure) as captured:
        asyncio.run(orchestrator.generate_reply("Fixture", [], uuid4(), uuid4()))
    assert calls == [True]
    assert captured.value.category == "model_output_limit"
    assert captured.value.diagnostics["model_failure"] == {
        "stage": "grounding",
        "model": "gpt-5-nano",
        "output_tokens": 2000,
        "reasoning_tokens": 2000,
    }


@pytest.mark.parametrize(
    "factory", [build_agent, build_fact_extractor, build_input_judge, build_judge]
)
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize(
    "model, effort, limit",
    [
        ("gpt-5-nano", "minimal", 2000),
        ("gpt-5.4-mini", "none", 4000),
    ],
)
def test_reasoning_truncation_stops_once_preserves_usage_and_sends_supported_effort(
    factory, partial, model, effort, limit
):
    from app.assistant.model_settings import ModelOutputLimitExceeded

    requests = []
    usage = RunUsage()

    def respond(request):
        requests.append(json.loads(request.content))
        message = {"role": "assistant", "content": ""}
        if partial:
            message["tool_calls"] = [
                {
                    "id": "cut-off",
                    "type": "function",
                    "function": {"name": "final_result", "arguments": '{"claims":['},
                }
            ]
        return httpx.Response(
            200,
            json={
                "id": "budget-fixture",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {"index": 0, "finish_reason": "length", "message": message}
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 2000,
                    "total_tokens": 2100,
                    "completion_tokens_details": {"reasoning_tokens": 2000},
                },
            },
        )

    async def check():
        config = SimpleNamespace(
            openai_chat_model=model,
            openai_grounding_model=model,
            assistant_reasoning_effort=effort,
            assistant_output_retries=1,
            assistant_output_tokens=limit,
            grounding_output_tokens=limit,
        )
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            with pytest.raises(ModelOutputLimitExceeded) as captured:
                await factory(config, client).run("Budget fixture", usage=usage)
            assert captured.value.reasoning_tokens == 2000
            assert captured.value.output_tokens == 2000

    asyncio.run(check())
    assert len(requests) == 1
    if effort == "none":
        assert "reasoning_effort" not in requests[0]
    else:
        assert requests[0]["reasoning_effort"] == effort
    assert "temperature" not in requests[0]
    assert requests[0]["max_completion_tokens"] == limit
    # The SDK counts committed steps, excluding this aborted response; billed tokens remain.
    assert usage.requests == 0 and usage.output_tokens == 2000
    assert usage.input_tokens == 100
