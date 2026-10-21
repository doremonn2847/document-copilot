"""Run grounded answers against live services, without writing chat history."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pydantic_ai
import structlog

from app.chat.orchestrator import generate_reply


async def evaluate(case: dict) -> dict:
    started = monotonic()
    stages = []

    async def progress(stage):
        stages.append(stage)
        print(f"{case['id']}: {stage}", file=sys.stderr, flush=True)

    try:
        result = await generate_reply(case["question"], [], uuid4(), uuid4(), progress)
        return {
            **case,
            "status": "accepted",
            "progress": stages,
            "answer": result.answer.model_dump(mode="json"),
            "reply": result.reply.model_dump(mode="json"),
            "diagnostics": result.diagnostics,
        }
    except Exception as error:  # noqa: BLE001 -- never emit raw live exceptions
        # Never serialize SDK/driver exception text or request/response payloads.
        return {
            **case,
            "status": "failed",
            "failure_category": type(error).__name__,
            "category": getattr(error, "category", "service"),
            "diagnostics": getattr(error, "diagnostics", {}),
            "progress": stages,
            "elapsed_seconds": round(monotonic() - started, 2),
        }


async def main() -> None:
    pydantic_ai.BANNER_ENABLED = False
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--question")
    mode.add_argument("--cases", type=Path)
    parser.add_argument("--only", nargs="+", help="Case IDs from the worksheet")
    parser.add_argument(
        "--output", type=Path, help="Write a JSON artifact; no chats are saved"
    )
    args = parser.parse_args()
    cases = (
        json.loads(args.cases.read_text(encoding="utf-8"))
        if args.cases
        else [{"id": "single", "question": args.question}]
    )
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
    if not cases:
        parser.error("No matching cases")
    results = []
    for case in cases:
        result = await evaluate(case)
        results.append(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
