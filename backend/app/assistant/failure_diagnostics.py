"""Retain SDK failure categories without recording model text or credentials."""

import json
import re

from pydantic import ValidationError
from pydantic_ai import ModelRetry
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import RetryPromptPart

FIELDS = {
    "claims",
    "gaps",
    "request_quote",
    "request_id",
    "missing_detail",
    "reason",
    "target",
    "ticker",
    "form",
    "corpus_years",
    "fiscal_years",
    "text",
    "kind",
    "evidence_ids",
    "calculation_id",
}
ERROR_TYPES = {
    "missing",
    "extra_forbidden",
    "string_type",
    "string_too_short",
    "string_too_long",
    "literal_error",
    "uuid_parsing",
    "json_invalid",
    "list_type",
    "int_parsing",
    "finite_number",
    "value_error",
    "too_long",
    "too_short",
}


def output_retry_feedback(error: UnexpectedModelBehavior) -> str:
    """Private model feedback only; never include this in public diagnostics/logs."""
    cause = error
    for _ in range(8):
        feedback = None
        if isinstance(cause, ModelRetry):
            feedback = cause.message
        elif isinstance(cause, ValidationError):
            feedback = cause.errors(
                include_input=False, include_context=False, include_url=False
            )
        retry = getattr(cause, "tool_retry", None)
        if isinstance(retry, RetryPromptPart):
            feedback = retry.content
        if feedback is not None:
            if isinstance(feedback, list):
                feedback = [
                    {key: entry[key] for key in ("loc", "type", "msg") if key in entry}
                    for entry in feedback[:10]
                ]
            return json.dumps(feedback, default=str)[:4000]
        next_cause = cause.__cause__ or cause.__context__
        if next_cause is None or next_cause is cause:
            break
        cause = next_cause
    return "No specific output-validation feedback was retained."


def structural_failure_summary(reports: list[dict]) -> list[dict]:
    """Log fixed categories only; validation errors may contain source/model text."""
    prefixes = {
        "selected excerpts cannot establish absence": "whole_filing_absence",
        "comparison superlatives across filings": "comparison_scope",
        "financial figures require explicit fiscal periods: missing_claim_year": "financial_period_claim_year_missing",
        "financial figures require explicit fiscal periods: missing_quoted_year": "financial_period_source_year_missing",
        "financial figures require explicit fiscal periods": "financial_period",
        "financial amounts require explicit currency": "financial_currency",
        "financial amounts require matching quoted scale": "financial_scale",
        "cite this claim's own evidence for every named company": "company_citation_coverage",
        "uncited numeric tokens": "uncited_number",
        "factual claims must cite one filing": "multiple_factual_filings",
    }
    summaries = []
    for report in reports:
        if report.get("stage") != "structural":
            continue
        errors = report.get("errors", [])
        kinds = set()
        claims_by_kind = {}
        for error in errors:
            detail = re.sub(r"^(?:claim|gap) \d+: ", "", error)
            kind = next(
                (
                    kind
                    for prefix, kind in prefixes.items()
                    if detail.startswith(prefix)
                ),
                "other_structural",
            )
            kinds.add(kind)
            if match := re.match(r"^claim (\d+): ", error):
                claims_by_kind.setdefault(kind, set()).add(int(match[1]))
        summaries.append(
            {
                "attempt": len(summaries),
                "error_count": len(errors),
                "kinds": sorted(kinds),
                "claims_by_kind": {
                    kind: sorted(indices)
                    for kind, indices in sorted(claims_by_kind.items())
                },
            }
        )
    return summaries


def http_failure_diagnostics(error: ModelHTTPError) -> dict:
    body = error.body if isinstance(error.body, dict) else {}
    body = body.get("error", body)
    body = body if isinstance(body, dict) else {}
    codes = {
        "unsupported_parameter",
        "unsupported_value",
        "invalid_function_parameters",
        "invalid_request_error",
        "model_not_found",
        "insufficient_quota",
        "rate_limit_exceeded",
        "permission_denied",
        "context_length_exceeded",
        "invalid_api_key",
    }
    code = body.get("code")
    parameter = body.get("param")
    safe_parameter = isinstance(parameter, str) and re.fullmatch(
        r"model|reasoning_effort|max_completion_tokens|temperature|tool_choice|parallel_tool_calls|tools\[\d+\]\.function\.(?:parameters|name|strict)",
        parameter,
    )
    return {
        "kind": "provider_http_error",
        "status_code": error.status_code,
        "code": code if isinstance(code, str) and code in codes else "unclassified",
        "parameter": parameter if safe_parameter else "unclassified",
    }


def unexpected_response_diagnostics(error: UnexpectedModelBehavior) -> dict:
    kind = "unexpected_response"
    for prefix, category in (
        ("Exceeded maximum output retries", "output_retries_exhausted"),
        ("Exceeded maximum retries", "tool_retries_exhausted"),
        ("Model token limit", "empty_response_at_token_limit"),
        ("Function tool calls must have unique", "duplicate_tool_call_ids"),
        ("Deferred tool calls must have unique", "duplicate_tool_call_ids"),
    ):
        if error.message.startswith(prefix):
            kind = category
            break
    details = {"kind": kind, "validation_errors": []}
    cause = error
    # SDK wrapping may retain the final validation failure in several nested causes.
    for _ in range(8):
        entries = []
        retry_text = None
        if isinstance(cause, ValidationError):
            entries = cause.errors(
                include_input=False, include_context=False, include_url=False
            )
        retry = getattr(cause, "tool_retry", None)
        if isinstance(retry, RetryPromptPart):
            if isinstance(retry.content, list):
                entries = retry.content
            elif isinstance(retry.content, str):
                retry_text = retry.content
        if isinstance(cause, ModelRetry):
            retry_text = cause.message
        if retry_text is not None:
            details["retry_reason"] = (
                "request_anchor_invalid"
                if retry_text.startswith(
                    "Each model-written gap requires request_quote"
                )
                else "semantic_validation"
            )
        for entry in entries[:10]:
            field = ".".join(
                part if part in FIELDS else "<field>"
                for part in entry.get("loc", ())
                if isinstance(part, str)
            )
            code = entry.get("type")
            item = {
                "field": field,
                "type": code if code in ERROR_TYPES else "validation",
            }
            if (
                item not in details["validation_errors"]
                and len(details["validation_errors"]) < 10
            ):
                details["validation_errors"].append(item)
        next_cause = cause.__cause__ or cause.__context__
        if next_cause is None or next_cause is cause:
            break
        cause = next_cause
    return details
