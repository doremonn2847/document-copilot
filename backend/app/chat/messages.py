from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TextPart(BaseModel):
    type: Literal["text"]
    text: str = Field(max_length=16_000)


class StepStartPart(BaseModel):
    type: Literal["step-start"]


class UIMessage(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    role: Literal["user", "assistant"]
    parts: list[TextPart | StepStartPart] = Field(min_length=1, max_length=32)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threadId: UUID
    messages: list[UIMessage] = Field(min_length=1, max_length=200)
    # DefaultChatTransport includes these alongside its custom body.
    id: str | None = Field(default=None, max_length=128)
    trigger: Literal["submit-message"] = "submit-message"
    messageId: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_turn(self) -> Self:
        if self.messages[-1].role != "user" or not self.question.strip():
            raise ValueError("The last message must be a nonempty user question")
        if (
            sum(
                len(part.text)
                for message in self.messages
                for part in message.parts
                if isinstance(part, TextPart)
            )
            > 100_000
        ):
            raise ValueError("Message history is too large")
        if len(self.question) > 16_000:
            raise ValueError("Question is too large")
        if self.messageId is not None and self.messageId != self.messages[-1].id:
            raise ValueError("messageId must identify the last user message")
        return self

    @property
    def question(self) -> str:
        return "".join(
            part.text for part in self.messages[-1].parts if isinstance(part, TextPart)
        )
