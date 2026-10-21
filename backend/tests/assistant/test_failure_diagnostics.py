import asyncio
from uuid import uuid4

import pytest
from openai import AsyncOpenAI
from pydantic_ai.models.test import TestModel

from app.assistant.agent import build_agent
from app.chat import orchestrator
from app.config import settings
from tests.assistant.test_tools import deps


def test_private_repair_feedback_is_bounded_and_not_public_diagnostics():
    from pydantic_ai import ModelRetry
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from app.assistant.failure_diagnostics import (
        output_retry_feedback,
        unexpected_response_diagnostics,
    )

    error = UnexpectedModelBehavior("private-provider-body")
    assert "private-provider-body" not in output_retry_feedback(error)
    error.__cause__ = ModelRetry("Unknown evidence IDs: private-E99" + "x" * 5000)
    feedback = output_retry_feedback(error)
    assert "Unknown evidence IDs" in feedback
    assert len(feedback) == 4000
    assert "private" not in str(unexpected_response_diagnostics(error))


def test_failure_summary_excludes_raw_body_messages_and_untrusted_field_names():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from pydantic_ai.messages import RetryPromptPart

    from app.assistant.failure_diagnostics import unexpected_response_diagnostics

    error = UnexpectedModelBehavior(
        "private-exception-text", body="private-response-body"
    )
    wrapped = RuntimeError("private-cause-text")
    wrapped.tool_retry = RetryPromptPart(
        content=[
            {
                "loc": ("gaps", 0, "private-field-name"),
                "type": "private-error-type",
                "input": "private-input",
                "msg": "private-validation-message",
            }
        ]
    )
    error.__cause__ = wrapped
    details = unexpected_response_diagnostics(error)
    assert details == {
        "kind": "unexpected_response",
        "validation_errors": [
            {"field": "gaps.<field>", "type": "validation"},
        ],
    }
    assert "private" not in str(details)


@pytest.mark.parametrize("nested", [False, True])
def test_http_failure_retains_only_status_and_allowlisted_fields(nested):
    from pydantic_ai.exceptions import ModelHTTPError

    from app.assistant.failure_diagnostics import http_failure_diagnostics

    body = {
        "code": "unsupported_parameter",
        "type": "invalid_request_error",
        "param": "reasoning_effort",
        "message": "private-provider-text",
    }
    error = ModelHTTPError(
        status_code=400,
        model_name="gpt-5.4-mini",
        body={"error": body} if nested else body,
    )
    assert http_failure_diagnostics(error) == {
        "kind": "provider_http_error",
        "status_code": 400,
        "code": "unsupported_parameter",
        "parameter": "reasoning_effort",
    }
    secret = ModelHTTPError(
        status_code=403,
        model_name="gpt-5.4-mini",
        body={"code": "private-code", "param": "private-param"},
    )
    assert "private" not in str(http_failure_diagnostics(secret))


@pytest.mark.parametrize("quote", [None, "private-invalid-request-quote"])
def test_sdk_output_retry_failure_retains_safe_diagnosis(monkeypatch, quote):
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

    async def fail(*args, **kwargs):
        d = deps()
        d.question = "What does Azure provide?"
        gap = {"reason": "missing_evidence"}
        if quote is not None:
            gap["request_quote"] = quote
        async with AsyncOpenAI(api_key="offline-unit-test") as client:
            agent = build_agent(settings, client)
            with agent.override(
                model=TestModel(
                    call_tools=[], custom_output_args={"claims": [], "gaps": [gap]}
                )
            ):
                await agent.run(d.question, deps=d)

    monkeypatch.setattr(orchestrator, "run_grounded", fail)
    with pytest.raises(orchestrator.AssistantFailure) as captured:
        asyncio.run(orchestrator.generate_reply("Fixture", [], uuid4(), uuid4()))
    failure = captured.value
    assert failure.category == "service"
    assert failure.diagnostics["failure_type"] == "UnexpectedModelBehavior"
    details = failure.diagnostics["model_failure"]
    assert details["kind"] == "output_retries_exhausted"
    if quote is None:
        assert {"field": "gaps.request_quote", "type": "missing"} in details[
            "validation_errors"
        ]
    else:
        assert details["retry_reason"] == "request_anchor_invalid"
    assert "private-invalid-request-quote" not in str(failure.diagnostics)


def test_structural_diagnostics_preserve_categories_without_rejected_text():
    from app.assistant.failure_diagnostics import structural_failure_summary

    reports = [
        {
            "stage": "structural",
            "attempt": 0,
            "errors": [
                "claim 0: financial figures require explicit fiscal periods private-text",
                "claim 0: financial amounts require explicit currency private-text",
                "claim 1: cite this claim's own evidence for every named company private-text",
                "claim 2: private-unknown-error",
            ],
        },
        {"decisions": [{"evidence_assessment": "private-text"}]},
        {"stage": "structural", "attempt": 1, "errors": []},
    ]
    summaries = structural_failure_summary(reports)
    assert summaries == [
        {
            "attempt": 0,
            "error_count": 4,
            "kinds": [
                "company_citation_coverage",
                "financial_currency",
                "financial_period",
                "other_structural",
            ],
            "claims_by_kind": {
                "company_citation_coverage": [1],
                "financial_currency": [0],
                "financial_period": [0],
                "other_structural": [2],
            },
        },
        {"attempt": 1, "error_count": 0, "kinds": [], "claims_by_kind": {}},
    ]
    assert "private" not in str(summaries)
