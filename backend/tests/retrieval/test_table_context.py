import asyncio
import hashlib

import pytest

from app.retrieval import queries
from tests.assistant.test_contracts import passage

TABLE = """| (In millions) | 2025 | 2024 |
|---|---|---|
| Revenue | $281,724 | $245,122 |
| Gross margin | 193,893 | 171,008 |"""
MARKDOWN = (
    "SUMMARY RESULTS OF OPERATIONS\n\n"
    + TABLE
    + "\n\nFiscal Year 2025 Compared with Fiscal Year 2024\n"
)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_hydration_restores_original_table_with_hash_and_table_reference(
    config, monkeypatch, newline
):
    p = passage("Revenue, = 281,724. Gross margin, = 193,893.")
    row = p.model_dump(exclude={"neighbors"})
    row.update(
        source_markdown=MARKDOWN,
        chunk_metadata={
            "item_refs": ["#/tables/0"],
            "source_sha256": hashlib.sha256(
                MARKDOWN.replace("\n", newline).encode()
            ).hexdigest(),
        },
    )
    monkeypatch.setattr(queries, "fetch_rows", lambda *args: [row])
    result = asyncio.run(queries.get_chunks(config, [p.chunk_id]))[0]
    assert result.text == p.text
    assert TABLE in result.source_context
    assert "Fiscal Year 2025 Compared with Fiscal Year 2024" in result.source_context


def test_modified_original_cannot_supply_table_context(config, monkeypatch):
    p = passage("Revenue, = 281,724.")
    row = p.model_dump(exclude={"neighbors"})
    row.update(
        source_markdown=MARKDOWN,
        chunk_metadata={
            "item_refs": ["#/tables/0"],
            "source_sha256": "0" * 64,
        },
    )
    monkeypatch.setattr(queries, "fetch_rows", lambda *args: [row])
    with pytest.raises(ValueError, match="hash"):
        asyncio.run(queries.get_chunks(config, [p.chunk_id]))


def test_original_cover_heading_binds_period_without_inventing_index_metadata():
    from app.retrieval.table_context import original_table_context

    markdown = "For the Fiscal Year Ended June 30, 2025\n\n" + TABLE
    context = original_table_context(
        markdown,
        {
            "item_refs": ["#/tables/0"],
            "source_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
        },
        "Revenue, = 281,724.",
    )
    assert "For the Fiscal Year Ended June 30, 2025" in context
    assert TABLE in context


def test_original_table_is_one_citable_span_in_actual_chat_tool():
    from app.assistant.tools import expose_groups
    from tests.assistant.test_tools import deps

    p = passage("Revenue, = 281,724. Gross margin, = 193,893.").model_copy(
        update={"source_context": [TABLE]}
    )
    d = deps()
    result = expose_groups(d, [("MSFT", [p])])
    assert TABLE in result
    ref = next(
        ref for ref in d.registry.evidence_refs.values() if ref.exact_quote == TABLE
    )
    d.registry.verify(ref)
    assert len(result) <= d.settings.assistant_tool_chars


def test_unexposed_context_cannot_leak_into_judge_metadata():
    import json

    from app.assistant.deps import TurnRegistry
    from app.assistant.outputs import AnswerClaim, EvidenceRef, GroundedAnswer
    from app.grounding.judge import judge_prompt

    p = passage("Azure provides compute.").model_copy(
        update={"source_context": [TABLE]}
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    payload = judge_prompt("What does Azure provide?", answer, registry)
    assert "281,724" not in payload
    assert (
        "source_context"
        not in json.loads(payload)["proposed_answer"]["claims"][0]["cited_evidence"][0][
            "metadata"
        ]
    )


def test_separate_source_spans_cannot_be_joined_into_an_invented_quote():
    from app.assistant.deps import TurnRegistry
    from app.assistant.outputs import EvidenceRef

    p = passage("First source sentence.").model_copy(
        update={"source_context": ["Separate source context."]}
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
    registry.expose(p, p.source_context[0])
    with pytest.raises(ValueError, match="non-contiguous"):
        registry.verify(
            EvidenceRef(
                chunk_id=p.chunk_id,
                exact_quote="First source sentence. Separate source context.",
            )
        )


def test_five_year_evidence_exposes_complete_table_rows_within_chat_budget():
    from types import SimpleNamespace

    from app.assistant.selection import SelectedClaim, final_answer
    from app.assistant.tools import expose_groups
    from app.grounding.validator import structural_errors
    from tests.assistant.test_tools import deps

    d = deps()
    groups = []
    for year in range(2021, 2026):
        table = TABLE.replace("2025", str(year)).replace("2024", str(year - 1))
        heading = f"Fiscal Year {year} Compared with Fiscal Year {year - 1}"
        p = passage("Revenue, = 281,724. Gross margin, = 193,893.").model_copy(
            update={
                "ticker": "MSFT",
                "corpus_year": year,
                "source_context": [heading, table],
            }
        )
        groups.append((f"MSFT {year}", [p]))
    output = expose_groups(d, groups)
    claims = []
    for _, items in groups:
        p = items[0]
        keys = [
            key
            for key, ref in d.registry.evidence_refs.items()
            if ref.chunk_id == p.chunk_id and ref.exact_quote in p.source_context
        ]
        assert len(keys) == 2
        claims.append(
            SelectedClaim(
                text=f"Revenue for fiscal {p.corpus_year} was $281,724 million and gross margin was $193,893 million.",
                evidence_ids=keys,
            )
        )
    answer = final_answer(SimpleNamespace(deps=d), claims, [])
    assert structural_errors(answer, d.registry, searches=1) == []
    assert len(output) <= d.settings.assistant_tool_chars
