"""Inspect retrieval without generating answers. Live runs use OpenAI and read-only Postgres."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import pydantic_ai
from pydantic import BaseModel, Field

from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import (
    ComparisonResult,
    RetrievalResult,
    SearchFilters,
    format_passages_for_agent,
)


class EvaluationCase(BaseModel):
    id: str
    question: str
    targets: list[SearchFilters] = Field(min_length=1, max_length=25)


def parse_target(value: str) -> SearchFilters:
    ticker, year = value.split(":")
    return SearchFilters(ticker=ticker, corpus_years=[int(year)], form="10-K")


def display_result(result: RetrievalResult) -> None:
    print(
        f"Lexical available: {result.lexical_available}; query: {result.lexical_query}"
    )
    print(
        f"Candidates: semantic={len(result.semantic_hits)} FTS={len(result.lexical_hits)}; selected={len(result.passages)}"
    )
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(
        "Semantic-only ranking:", [str(h.chunk_id) for h in result.semantic_hits[:10]]
    )
    print("FTS-only ranking:", [str(h.chunk_id) for h in result.lexical_hits[:10]])
    print(
        "Fused ranking:", [(str(p.chunk_id), p.fusion_score) for p in result.passages]
    )
    print(format_passages_for_agent(result.passages))


async def main() -> None:
    from app.config import settings

    pydantic_ai.BANNER_ENABLED = False

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--question")
    mode.add_argument("--cases", type=Path, help="JSON worksheet with explicit targets")
    parser.add_argument("--ticker")
    parser.add_argument("--corpus-years", type=int, nargs="+")
    parser.add_argument("--fiscal-years", type=int, nargs="+")
    parser.add_argument("--form", default="10-K")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Repeat TICKER:CORPUS_YEAR for comparisons",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full structured report instead of formatted excerpts",
    )
    parser.add_argument(
        "--output", type=Path, help="Also save the full structured JSON report"
    )
    args = parser.parse_args()
    reports = []
    async with DocumentRetriever(settings) as retriever:
        if args.cases:
            cases = [
                EvaluationCase.model_validate(case)
                for case in json.loads(args.cases.read_text(encoding="utf-8"))
            ]
        else:
            targets = [parse_target(value) for value in args.target]
            if targets and (args.ticker or args.corpus_years or args.fiscal_years):
                raise ValueError("Use comparison targets or a single set of filters")
            if targets:
                cases = [
                    EvaluationCase(
                        id="comparison", question=args.question, targets=targets
                    )
                ]
            else:
                filters = SearchFilters(
                    ticker=args.ticker,
                    corpus_years=args.corpus_years,
                    fiscal_years=args.fiscal_years,
                    form=args.form,
                )
                result = await retriever.search(args.question, filters=filters)
                reports.append(
                    {
                        "id": "lookup",
                        "question": args.question,
                        "result": result.model_dump(mode="json"),
                    }
                )
                if not args.json:
                    display_result(result)
                    print(
                        "Usage:",
                        result.usage.model_dump(),
                        "Timing ms:",
                        result.timings_ms,
                    )
                cases = []
        for case in cases:
            print(
                f"Retrieving {case.id}: {len(case.targets)} targets",
                file=sys.stderr,
                flush=True,
            )
            result: ComparisonResult = await retriever.compare(
                case.question, targets=case.targets
            )
            reports.append(
                {
                    "id": case.id,
                    "question": case.question,
                    "result": result.model_dump(mode="json"),
                }
            )
            if not args.json:
                print(f"\n{case.id}: {case.question}")
                for entry in result.targets:
                    print("Target:", entry.target.model_dump(exclude_none=True))
                    display_result(entry.result)
                print(
                    "Usage:", result.usage.model_dump(), "Timing ms:", result.timings_ms
                )
    payload = json.dumps(reports, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    if args.json:
        print(payload)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        asyncio.run(main())
    except Exception as error:  # noqa: BLE001 -- CLI boundary must not expose driver/provider credentials.
        raise SystemExit(
            f"Retrieval smoke failed ({type(error).__name__}). Raw service error suppressed."
        ) from None
