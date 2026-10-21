from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str | None = Field(default=None, min_length=1, max_length=16)
    form: str | None = Field(default=None, min_length=1, max_length=16)
    corpus_years: list[int] | None = Field(default=None, min_length=1, max_length=25)
    fiscal_years: list[int] | None = Field(default=None, min_length=1, max_length=25)

    @field_validator("ticker", "form", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class RankedChunkHit(BaseModel):
    chunk_id: UUID
    rank: int
    score: float


class RetrievedPassage(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    ticker: str
    form: str
    accession_number: str
    source_url: str
    filing_date: date
    report_date: date | None = None
    corpus_year: int | None = None
    fiscal_year: int | None = None
    page: str | None = None
    section: str | None = None
    fusion_score: float = 0.0
    neighbors: list["RetrievedPassage"] = Field(default_factory=list)
    source_context: list[str] = Field(default_factory=list)


class RetrievalUsage(BaseModel):
    embedding_tokens: int = 0
    keyword_input_tokens: int = 0
    keyword_output_tokens: int = 0
    keyword_requests: int = 0


class KeywordResult(BaseModel):
    text: str | None = None
    warning: str | None = None
    usage: RetrievalUsage = Field(default_factory=RetrievalUsage)


class RetrievalResult(BaseModel):
    passages: list[RetrievedPassage] = Field(default_factory=list)
    lexical_query: str | None = None
    lexical_available: bool = True
    semantic_hits: list[RankedChunkHit] = Field(default_factory=list)
    lexical_hits: list[RankedChunkHit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    usage: RetrievalUsage = Field(default_factory=RetrievalUsage)


class ComparisonTargetResult(BaseModel):
    target: SearchFilters
    result: RetrievalResult


class ComparisonResult(BaseModel):
    targets: list[ComparisonTargetResult]
    usage: RetrievalUsage
    timings_ms: dict[str, float] = Field(default_factory=dict)


def format_passages_for_agent(passages: list[RetrievedPassage]) -> str:
    if not passages:
        return "No matching passages found."
    lines = []
    for passage in passages:
        for item in [passage, *passage.neighbors]:
            year = (
                f"FY{item.fiscal_year}"
                if item.fiscal_year is not None
                else "fiscal year unverified"
            )
            location = f"page {item.page}" if item.page else "page unverified"
            excerpt = (
                item.text
                if len(item.text) <= 800
                else item.text[:780] + " [excerpt truncated]"
            )
            lines.append(
                f"[{item.chunk_id}] {item.ticker} {item.form}; corpus year {item.corpus_year}; {year}; {location}; chunk {item.chunk_index}\n{item.source_url}\n{excerpt}"
            )
    output = "\n\n".join(lines)
    return output if len(output) <= 12000 else output[:11970] + "\n[output truncated]"
