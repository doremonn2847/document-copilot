import asyncio

from openai import AsyncOpenAI
from pydantic_ai.models.test import TestModel

from app.assistant.agent import available_tool, build_agent
from app.grounding.judge import build_judge


def test_exhausted_tools_are_removed_before_next_model_request():
    from types import SimpleNamespace

    from pydantic_ai.tools import ToolDefinition

    from tests.assistant.test_tools import deps

    d = deps()
    d.tool_calls = d.settings.assistant_tool_calls
    tool = ToolDefinition(
        name="read_chunk", description="Read", parameters_json_schema={"type": "object"}
    )
    assert available_tool(SimpleNamespace(deps=d), tool) is None


def test_installed_sdk_accepts_tools_and_typed_output(monkeypatch):
    from app.config import Settings
    from tests.assistant.test_tools import deps

    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "test",
        "SUPABASE_SERVICE_ROLE_KEY": "test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "OPENAI_API_KEY": "test",
        "ALLOWED_ORIGINS": "http://localhost:5173",
    }.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)

    async def check():
        async with AsyncOpenAI(api_key="test") as client:
            agent = build_agent(settings, client)
            with agent.override(
                model=TestModel(
                    call_tools=[],
                    custom_output_args={
                        "claims": [],
                        "gaps": [{"reason": "outside_scope", "request_quote": "Hello"}],
                    },
                )
            ):
                d = deps()
                d.question = "Hello"
                result = await agent.run("Hello", deps=d)
                assert result.output.status == "insufficient_evidence"
            judge = build_judge(settings, client)
            with judge.override(model=TestModel(custom_output_args={"decisions": []})):
                result = await judge.run("No claims")
                assert result.output.decisions == []

    asyncio.run(check())
