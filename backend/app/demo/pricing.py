"""Direct OpenAI Standard rates verified 2026-10-27; USD per million tokens.

Sources and conservative context-bound policy: public-demo-design.md.
Microdollars per token numerically equal dollars per million tokens.
"""

import json
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

import httpx

from app.demo.errors import DemoUnavailable

REVISION = "openai-standard-2026-10-27"
CHAT_RATES = {
    "gpt-5.4-mini": (400000, Decimal("0.75"), Decimal("4.50")),
    "gpt-4o-mini": (128000, Decimal("0.15"), Decimal("0.60")),
}


@dataclass(frozen=True)
class RequestBound:
    model: str
    endpoint: str
    input_limit: int
    output_limit: int
    input_rate: Decimal
    output_rate: Decimal

    @property
    def reservation(self) -> int:
        return rounded(
            self.input_limit * self.input_rate + self.output_limit * self.output_rate
        )


def rounded(amount: Decimal) -> int:
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def chat_bound(model: str, output_limit: int) -> RequestBound:
    context, input_rate, output_rate = CHAT_RATES[model]
    return RequestBound(
        model, "chat/completions", context, output_limit, input_rate, output_rate
    )


def request_bound(request: httpx.Request) -> RequestBound:
    if (
        request.method != "POST"
        or request.url.scheme != "https"
        or request.url.host != "api.openai.com"
        or request.url.port not in (None, 443)
        or request.url.query
    ):
        raise DemoUnavailable()
    try:
        body = json.loads(request.content)
        if not isinstance(body, dict):
            raise TypeError
        model = body["model"]
        if request.url.path == "/v1/embeddings":
            text = body.get("input")
            if (
                model != "text-embedding-3-small"
                or not isinstance(text, str)
                or not 0 < len(text.encode("utf-8")) <= 8191
                or set(body)
                - {"model", "input", "dimensions", "encoding_format", "user"}
            ):
                raise ValueError
            return RequestBound(
                model, "embeddings", 8192, 0, Decimal("0.02"), Decimal(0)
            )
        if request.url.path != "/v1/chat/completions" or model not in CHAT_RATES:
            raise ValueError
        # Reject new billable request shapes until their bounds/pricing are reviewed.
        allowed = {
            "model",
            "messages",
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "response_format",
            "max_tokens",
            "max_completion_tokens",
            "temperature",
            "top_p",
            "stop",
            "stream",
            "n",
            "service_tier",
            "reasoning_effort",
            "seed",
            "user",
            "frequency_penalty",
            "presence_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
            "store",
            "metadata",
        }
        if (
            set(body) - allowed
            or body.get("stream", False) is not False
            or body.get("n", 1) != 1
            or body.get("service_tier", "default") != "default"
        ):
            raise ValueError
        limit = body.get("max_completion_tokens", body.get("max_tokens"))
        if "max_completion_tokens" in body and "max_tokens" in body:
            raise ValueError
        if type(limit) is not int or not 0 < limit <= 16384:
            raise ValueError
        if any(tool.get("type") != "function" for tool in body.get("tools", [])):
            raise ValueError
        for message in body.get("messages", []):
            if set(message) - {
                "role",
                "content",
                "name",
                "tool_calls",
                "tool_call_id",
                "refusal",
            }:
                raise ValueError
            content = message.get("content")
            if isinstance(content, list):
                if any(
                    part.get("type") != "text" or not isinstance(part.get("text"), str)
                    for part in content
                ):
                    raise ValueError
            elif content is not None and not isinstance(content, str):
                raise ValueError
        return chat_bound(model, limit)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise DemoUnavailable() from None


def charge(bound: RequestBound, usage: dict) -> int:
    inputs = usage.get("prompt_tokens")
    outputs = usage.get("completion_tokens", 0 if bound.output_limit == 0 else None)
    if (
        type(inputs) is not int
        or type(outputs) is not int
        or not 0 <= inputs <= bound.input_limit
        or not 0 <= outputs <= bound.output_limit
    ):
        raise DemoUnavailable()
    return rounded(inputs * bound.input_rate + outputs * bound.output_rate)
