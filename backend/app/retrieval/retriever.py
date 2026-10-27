"""Async hybrid orchestration; no answer generation or chat persistence."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Self
from uuid import UUID

from openai import AsyncOpenAI

from app.demo.client import demo_client_options
from app.retrieval import queries
from app.retrieval.embeddings import embed_query, validate_question
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keywords import build_keyword_agent, extract_keywords
from app.retrieval.types import (
    ComparisonResult,
    ComparisonTargetResult,
    KeywordResult,
    RetrievalResult,
    RetrievalUsage,
    RetrievedPassage,
    SearchFilters,
)

if TYPE_CHECKING:
    from app.config import Settings


class DocumentRetriever:
    def __init__(
        self, settings: Settings, *, client: AsyncOpenAI | None = None
    ) -> None:
        if (
            settings.openai_embedding_model != "text-embedding-3-small"
            or settings.openai_embedding_dimensions != 1536
        ):
            raise ValueError(
                "Retrieval requires the indexed text-embedding-3-small / 1536 configuration"
            )
        self.settings = settings
        self._owns_client = client is None
        self.client = (
            client
            if client is not None
            else AsyncOpenAI(
                **demo_client_options(),
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=30,
                max_retries=1,
            )
        )
        self.keyword_agent = build_keyword_agent(settings, self.client)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client:
            await self.client.close()

    async def _prepare(
        self, query: str, filters: list[SearchFilters]
    ) -> tuple[list[float], KeywordResult, RetrievalUsage]:
        (vector, embedding_tokens), keywords = await asyncio.gather(
            embed_query(query, self.settings, self.client),
            extract_keywords(query, filters, self.settings, self.keyword_agent),
        )
        usage = keywords.usage.model_copy(update={"embedding_tokens": embedding_tokens})
        return vector, keywords, usage

    async def search(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        top_k: int | None = None,
        include_neighbors: bool = True,
    ) -> RetrievalResult:
        query = validate_question(query)
        limit = self.settings.retrieval_top_k if top_k is None else top_k
        if not 1 <= limit <= self.settings.retrieval_candidate_k:
            raise ValueError("top_k must be positive and not exceed candidate_k")
        started = perf_counter()
        vector, keywords, usage = await self._prepare(
            query, [filters] if filters else []
        )
        prep_ms = (perf_counter() - started) * 1000
        result = await self._search_prepared(
            vector, keywords, filters, limit, include_neighbors
        )
        result.usage = usage
        result.timings_ms.update(
            preparation=prep_ms, total=(perf_counter() - started) * 1000
        )
        return result

    async def _search_prepared(
        self,
        vector: list[float],
        keywords: KeywordResult,
        filters: SearchFilters | None,
        top_k: int,
        include_neighbors: bool,
    ) -> RetrievalResult:
        started = perf_counter()
        semantic_task = queries.semantic_search(
            self.settings, vector, filters, self.settings.retrieval_candidate_k
        )
        if keywords.text is not None:
            semantic, lexical = await asyncio.gather(
                semantic_task,
                queries.full_text_search(
                    self.settings,
                    keywords.text,
                    filters,
                    self.settings.retrieval_candidate_k,
                ),
            )
        else:
            semantic, lexical = await semantic_task, []
        fused = reciprocal_rank_fusion(
            [[h.chunk_id for h in semantic], [h.chunk_id for h in lexical]],
            k=self.settings.retrieval_rrf_k,
        )[:top_k]
        hydrated = {
            p.chunk_id: p
            for p in await queries.get_chunks(
                self.settings, [key for key, _ in fused], filters
            )
        }
        if any(key not in hydrated for key, _ in fused):
            raise ValueError("A selected source passage is no longer available")
        passages = [
            hydrated[key].model_copy(update={"fusion_score": score})
            for key, score in fused
        ]
        seen = {p.chunk_id for p in passages}
        if include_neighbors:
            neighbors = await queries.get_neighbors(
                self.settings, passages, self.settings.retrieval_neighbor_radius
            )
            for anchor in passages:
                for neighbor in neighbors:
                    if (
                        neighbor.chunk_id not in seen
                        and neighbor.document_id == anchor.document_id
                        and 0
                        < abs(neighbor.chunk_index - anchor.chunk_index)
                        <= self.settings.retrieval_neighbor_radius
                    ):
                        anchor.neighbors.append(neighbor)
                        seen.add(neighbor.chunk_id)
        warnings = [keywords.warning] if keywords.warning else []
        # Fiscal years come from each filing's own XBRL tag (ingest.fiscal_years);
        # warn only when a returned filing lacks one.
        if any(p.fiscal_year is None for p in passages):
            warnings.append(
                "Fiscal-year coverage is unverified for some corpus rows. Corpus year and filing date are not fiscal years; fiscal-year filters exclude unverified rows."
            )
        if not passages:
            warnings.append(
                "No matching passages for these filters; this target has a retrieval gap."
            )
        return RetrievalResult(
            passages=passages,
            lexical_query=keywords.text,
            lexical_available=keywords.text is not None,
            semantic_hits=semantic,
            lexical_hits=lexical,
            warnings=warnings,
            timings_ms={"search_and_hydration": (perf_counter() - started) * 1000},
        )

    async def compare(
        self, query: str, *, targets: list[SearchFilters]
    ) -> ComparisonResult:
        query = validate_question(query)
        if not 1 <= len(targets) <= 25:
            raise ValueError("Comparisons require 1 to 25 explicit targets")
        started = perf_counter()
        vector, keywords, usage = await self._prepare(query, targets)
        semaphore = asyncio.Semaphore(2)

        async def search_target(target: SearchFilters) -> ComparisonTargetResult:
            async with semaphore:
                result = await self._search_prepared(vector, keywords, target, 3, True)
                return ComparisonTargetResult(target=target, result=result)

        results = await asyncio.gather(*(search_target(target) for target in targets))
        return ComparisonResult(
            targets=results,
            usage=usage,
            timings_ms={"total": (perf_counter() - started) * 1000},
        )

    async def read_chunk(self, chunk_id: UUID) -> RetrievedPassage | None:
        rows = await queries.get_chunks(self.settings, [chunk_id])
        return rows[0] if rows else None

    async def read_surrounding_chunks(
        self, chunk_id: UUID, *, radius: int = 1
    ) -> list[RetrievedPassage]:
        if not 0 <= radius <= self.settings.retrieval_neighbor_radius:
            raise ValueError("Neighbor radius exceeds configured bound")
        anchor = await self.read_chunk(chunk_id)
        return (
            await queries.get_neighbors(self.settings, [anchor], radius)
            if anchor
            else []
        )
