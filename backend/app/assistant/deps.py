import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic_ai.usage import RunUsage

from app.assistant.outputs import EvidenceRef
from app.retrieval.types import RetrievedPassage, SearchFilters

# Leave room for other enums within OpenAI's 1,000-value schema limit.
MAX_EVIDENCE_SPANS = 900

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from app.assistant.calculations import CalculationRecord, Operand, Operation
    from app.assistant.facts import FactSelection
    from app.config import Settings
    from app.grounding.judge import SupportReport
    from app.retrieval.retriever import DocumentRetriever


def normalized(text: str) -> str:
    return " ".join(text.split())


def source_contains(passage: RetrievedPassage, text: str) -> bool:
    return any(
        normalized(text) in normalized(span)
        for span in [passage.text, *passage.source_context]
    )


class BudgetExceeded(ValueError):
    pass


@dataclass
class TurnRegistry:
    passages: dict[UUID, RetrievedPassage] = field(default_factory=dict)
    observed: dict[UUID, list[str]] = field(default_factory=dict)
    calculations: dict[UUID, "CalculationRecord"] = field(default_factory=dict)
    exposed_characters: int = 0
    numeric_facts: dict[UUID, "Operand"] = field(default_factory=dict)
    calculation_pairs: dict[tuple[UUID, UUID], "Operation"] = field(
        default_factory=dict
    )
    comparison_targets: list[SearchFilters] = field(default_factory=list)
    request_spans: dict[str, str] = field(default_factory=dict)
    evidence_refs: dict[str, EvidenceRef] = field(default_factory=dict)
    displayed_ids: list[str] = field(default_factory=list)
    comparison_evidence_ids: list[str] | None = None

    def evidence_id(self, passage: RetrievedPassage, text: str) -> str:
        ref = EvidenceRef(chunk_id=passage.chunk_id, exact_quote=text)
        key = next((k for k, v in self.evidence_refs.items() if v == ref), None)
        if key is None:
            self.expose(passage, text)
            key = f"E{len(self.evidence_refs) + 1}"
            self.evidence_refs[key] = ref
        self.displayed_ids.append(key)
        return key

    def selectable_refs(self) -> dict[str, EvidenceRef]:
        # The guided comparison writer sees only its frozen evidence, so it may cite only that.
        if self.comparison_evidence_ids is None:
            return self.evidence_refs
        return {key: self.evidence_refs[key] for key in self.comparison_evidence_ids}

    def expose(self, passage: RetrievedPassage, text: str) -> None:
        if not text or not any(
            text in span for span in [passage.text, *passage.source_context]
        ):
            raise ValueError("Exposure must be an exact source span")
        self.passages[passage.chunk_id] = passage.model_copy(deep=True)
        self.observed.setdefault(passage.chunk_id, []).append(text)
        self.exposed_characters += len(text)

    def verify(self, ref: EvidenceRef) -> None:
        quote = normalized(ref.exact_quote)
        passage = self.passages.get(ref.chunk_id)
        if not quote:
            raise ValueError("Supporting quote must not be blank")
        if passage is None or not source_contains(passage, quote):
            alternatives = [
                str(chunk_id)
                for chunk_id, spans in self.observed.items()
                if source_contains(self.passages[chunk_id], quote)
                and any(quote in normalized(span) for span in spans)
            ]
            if alternatives:
                raise ValueError(
                    f"Quote belongs to these already-observed chunk IDs: {', '.join(alternatives)}; replace the incorrect ID {ref.chunk_id} or remove the unsupported claim"
                )
        if passage is None:
            raise ValueError(
                f"Unknown chunk ID {ref.chunk_id}; use an ID returned by a tool this turn"
            )
        if not source_contains(passage, quote):
            sentences = re.split(r"(?<=[.!?])\s+", quote)
            if 2 <= len(sentences) <= 5 and all(
                any(
                    sentence in normalized(span) for span in self.observed[ref.chunk_id]
                )
                for sentence in sentences
            ):
                raise ValueError(
                    "Quote is non-contiguous: it joins separate source sentences. "
                    "Use separate EvidenceRef entries with the same chunk_id for these spans; "
                    "do not concatenate them into one exact_quote. Exact observed spans: "
                    + json.dumps(sentences)
                )
            raise ValueError(
                f"Quote is not verbatim source text for chunk {ref.chunk_id}. "
                "Each exact_quote must be one contiguous source span; do not omit intervening "
                "words or sentences. Use separate references for nonadjacent spans."
            )
        if not any(quote in normalized(span) for span in self.observed[ref.chunk_id]):
            raise ValueError("Quote was not exposed this turn")


@dataclass
class DocumentAgentDeps:
    user_id: UUID
    thread_id: UUID
    retriever: "DocumentRetriever"
    settings: "Settings"
    registry: TurnRegistry = field(default_factory=TurnRegistry)
    progress: Callable[[str], Awaitable[None]] | None = None
    tool_calls: int = 0
    searches: int = 0
    completed_retrievals: int = 0
    retrieval_usage: list[dict] = field(default_factory=list)
    numeric_attempts: list[dict] = field(default_factory=list)
    generator_usage: RunUsage = field(default_factory=RunUsage)
    judge_usage: RunUsage = field(default_factory=RunUsage)
    validation_reports: list[dict] = field(default_factory=list)
    tool_notes: list[str] = field(default_factory=list)
    question: str = ""
    fact_extractor: "Agent[None, FactSelection] | None" = None
    fact_judge: "Agent[None, SupportReport] | None" = None
    fact_preparations: int = 0
    fact_checks: int = 0

    async def begin(self, stage: str, *, search: bool = False) -> None:
        self.tool_calls += 1
        if self.tool_calls > self.settings.assistant_tool_calls:
            raise BudgetExceeded("Tool budget exhausted")
        if search:
            self.searches += 1
            if self.searches > self.settings.assistant_search_calls:
                raise BudgetExceeded("Search budget exhausted")
        if self.progress:
            await self.progress(stage)
