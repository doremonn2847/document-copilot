"""Bound reasoning work and stop truncated responses before tools or repairs."""

from dataclasses import dataclass
from typing import Literal

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.profiles.openai import openai_model_profile
from pydantic_ai.settings import ModelSettings, ThinkingLevel


def bounded_settings(
    model_name: str,
    output_tokens: int,
    reasoning_effort: ThinkingLevel | Literal["none"],
) -> ModelSettings:
    profile = openai_model_profile(model_name)
    if profile and profile.get("openai_supports_reasoning"):
        if reasoning_effort == "none":
            # Omit the reasoning control when the provider already defaults to none.
            if not profile.get("thinking_enabled_by_default"):
                return {"max_tokens": output_tokens}
            return {"max_tokens": output_tokens, "thinking": False}
        return {"max_tokens": output_tokens, "thinking": reasoning_effort}
    return {"max_tokens": output_tokens, "temperature": 0}


class ModelOutputLimitExceeded(RuntimeError):
    def __init__(self, stage: str, response: ModelResponse):
        super().__init__("The model exhausted its response budget")
        self.stage = stage
        self.model = response.model_name
        self.output_tokens = response.usage.output_tokens
        self.reasoning_tokens = response.usage.details.get("reasoning_tokens", 0)

    def diagnostics(self) -> dict:
        return {
            "stage": self.stage,
            "model": self.model,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


@dataclass
class StopAtOutputLimit(AbstractCapability[object]):
    stage: str

    async def after_model_request(
        self,
        ctx: RunContext[object],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        # The SDK records billed usage before this hook, even when it raises.
        if response.finish_reason == "length":
            raise ModelOutputLimitExceeded(self.stage, response)
        return response
