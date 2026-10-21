"""Real SEC evidence fixture for calculator/judge integration, not an agent-quality score."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest


@pytest.mark.integration
def test_real_narrative_calculation_has_verified_units_and_periods():
    asyncio.run(check_calculation())


@pytest.mark.integration
def test_autonomous_guided_ratio_uses_verified_inputs():
    from app.chat.orchestrator import generate_reply

    question = "What is the ratio of Microsoft's reported gross-margin increase to revenue increase for fiscal 2022 compared with fiscal 2021? This is a ratio of annual increases, not the company's gross margin."
    result = asyncio.run(generate_reply(question, [], uuid4(), uuid4()))
    artifact = (
        Path(__file__).resolve().parents[3]
        / "data/chunks/assistant/autonomous-ratio-latest.json"
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "answer": result.answer.model_dump(mode="json"),
                "diagnostics": result.diagnostics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert result.answer.status == "answered"
    records = result.diagnostics["calculations"]
    assert len(records) == 1 and records[0]["display"] == "65.56 %"
    assert [o["raw_number"] for o in records[0]["operands"]] == ["19.8", "30.2"]
    assert all(o["segment"] == "consolidated" for o in records[0]["operands"])
    assert "65.56 %" in result.reply.text
    assert len([p for p in result.reply.parts if p["type"] == "data-citation"]) >= 3


async def check_calculation():
    from openai import AsyncOpenAI

    from app.assistant.calculations import Operand, calculate
    from app.assistant.deps import DocumentAgentDeps
    from app.assistant.outputs import AnswerClaim, EvidenceRef, GroundedAnswer
    from app.assistant.rendering import render_answer
    from app.assistant.tools import read_chunk, search_filings
    from app.config import Settings
    from app.grounding.judge import build_judge, judge_prompt, support_errors
    from app.grounding.validator import structural_errors
    from app.retrieval.retriever import DocumentRetriever
    from app.retrieval.types import SearchFilters

    settings = Settings()
    question = "What is the ratio of Microsoft's reported gross-margin increase to revenue increase for fiscal 2022 compared with fiscal 2021? This is a ratio of annual increases, not the company's gross margin."
    async with (
        AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=0,
            timeout=30,
        ) as client,
        DocumentRetriever(settings, client=client) as retriever,
    ):
        deps = DocumentAgentDeps(uuid4(), uuid4(), retriever, settings)
        ctx = SimpleNamespace(deps=deps)
        await search_filings(
            ctx,
            "gross margin revenue increase",
            SearchFilters(ticker="MSFT", corpus_years=[2022]),
        )
        print("Real calculation fixture: search completed")
        chunk_id = UUID("dca204b5-c187-5dc8-8d88-62a09e01f8cd")
        await read_chunk(ctx, chunk_id)
        displayed = [
            ref.exact_quote
            for ref in deps.registry.evidence_refs.values()
            if ref.chunk_id == chunk_id
        ]
        heading = next(
            line
            for line in displayed
            if "Fiscal Year 2022 Compared with Fiscal Year 2021" in line
        )
        gross = max(
            (
                line
                for line in displayed
                if line.startswith("Gross margin increased $19.8 billion")
            ),
            key=len,
        )
        revenue = max(
            (
                line
                for line in displayed
                if line.startswith("Revenue increased $30.2 billion")
            ),
            key=len,
        )
        ref = lambda quote: EvidenceRef(chunk_id=chunk_id, exact_quote=quote)
        period = ref(heading)
        common = {
            "entity": "MSFT",
            "segment": "consolidated",
            "unit": "USD billions",
            "period": "fiscal 2022 compared with fiscal 2021",
            "period_type": "annual",
        }
        record = calculate(
            "ratio_percent",
            [
                Operand(
                    raw_number="19.8",
                    value="19.8",
                    measure="annual gross-margin increase",
                    evidence=[period, ref(gross)],
                    **common,
                ),
                Operand(
                    raw_number="30.2",
                    value="30.2",
                    measure="annual revenue increase",
                    evidence=[period, ref(revenue)],
                    **common,
                ),
            ],
            deps.registry,
        )
        answer = GroundedAnswer(
            status="answered",
            claims=[
                AnswerClaim(
                    text="The ratio of the annual gross-margin increase to the annual revenue increase for fiscal 2022 compared with fiscal 2021 is 65.56%. This is a ratio of changes, not the company's gross margin.",
                    kind="calculation",
                    calculation_id=record.id,
                    evidence=[period, ref(gross), ref(revenue)],
                )
            ],
        )
        print("Real calculation fixture: calculated", record.display)
        assert (
            structural_errors(answer, deps.registry, searches=deps.completed_retrievals)
            == []
        )
        judged = await build_judge(settings, client).run(
            judge_prompt(question, answer, deps.registry)
        )
        print("Real calculation fixture decisions:", judged.output.model_dump_json())
        assert support_errors(judged.output, 1) == []
        reply = render_answer(answer, deps.registry)
        assert record.display == "65.56 %"
        path = (
            Path(__file__).resolve().parents[3]
            / "data/chunks/assistant/verified-calculation-fixture.json"
        )
        # This is an explicitly labeled fixture; it is not an autonomous-agent result.
        payload = {
            "kind": "developer-assembled real-source integration fixture",
            "question": question,
            "answer": answer.model_dump(mode="json"),
            "reply": reply.model_dump(mode="json"),
            "calculation": record.model_dump(mode="json"),
            "validation": judged.output.model_dump(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
