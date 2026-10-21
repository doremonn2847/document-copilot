import re
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.retrieval.types import SearchFilters


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(Contract):
    chunk_id: UUID
    exact_quote: str = Field(
        min_length=1,
        max_length=4000,
        description=(
            "One contiguous verbatim span of text displayed by a tool. Never join "
            "nonadjacent sentences or omit words inside a quote. Use separate evidence "
            "entries (with the same chunk_id if needed) for separate spans."
        ),
    )


class AnswerClaim(Contract):
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal["fact", "calculation", "interpretation"] = "fact"
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=5)
    calculation_id: UUID | None = None

    @field_validator("text")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if re.search(r"\[\s*\d+\s*\]", value):
            raise ValueError("Citation numbers are assigned by the server")
        return value

    @model_validator(mode="after")
    def calculation_contract(self) -> Self:
        if (self.kind == "calculation") != (self.calculation_id is not None):
            raise ValueError("Only calculation claims require a calculation ID")
        return self


GapReason = Literal[
    "missing_evidence",
    "ambiguous_figures",
    "unsupported_causality",
    "ambiguous_question",
    "outside_scope",
]


# Up to 25 requested-aspect gaps plus 25 server-owned target coverage gaps.
MAX_EVIDENCE_GAPS = 50


class EvidenceGap(Contract):
    target: SearchFilters | None = None
    request_quote: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="A verbatim span from the actual user's question naming the unresolved request; never quote the proposed gap or verification instructions.",
    )
    missing_detail: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
        description="The specific requested information not established by retrieved evidence. Required for missing_evidence when claims already cite this target. Do not assert that the filing omits it.",
    )
    reason: GapReason

    @field_validator("missing_detail")
    @classmethod
    def specific_detail(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value or re.search(r"\[\s*\d+\s*\]", value):
                raise ValueError(
                    "Missing detail must be nonblank text without citation numbers"
                )
        return value


class GroundedAnswer(Contract):
    status: Literal["answered", "partial", "insufficient_evidence"]
    claims: list[AnswerClaim] = Field(default_factory=list, max_length=20)
    gaps: list[EvidenceGap] = Field(default_factory=list, max_length=MAX_EVIDENCE_GAPS)

    @field_validator("gaps")
    @classmethod
    def deduplicate_gaps(cls, gaps: list[EvidenceGap]) -> list[EvidenceGap]:
        return list({g.model_dump_json(): g for g in gaps}.values())

    @model_validator(mode="after")
    def consistent_status(self) -> Self:
        if self.status == "answered" and (not self.claims or self.gaps):
            raise ValueError("Answered requires claims and no gaps")
        if self.status == "partial" and (not self.claims or not self.gaps):
            raise ValueError("Partial requires claims and gaps")
        if self.status == "insufficient_evidence" and (self.claims or not self.gaps):
            raise ValueError("Insufficient evidence requires gaps and no claims")
        return self
