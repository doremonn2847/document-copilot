import json

import pytest

from ingest.preview import chunk_records, fit_chunk, load_filing


def test_overflow_split_preserves_text_and_context():
    import tiktoken
    from pydantic import BaseModel

    class Chunk(BaseModel):
        text: str

    class Chunker:
        def contextualize(self, chunk):
            return "Revenue (millions)\n" + chunk.text

    original = Chunk(text="2025 Revenue 123; 2024 Revenue 123; " * 100)
    encoding = tiktoken.get_encoding("cl100k_base")
    parts = fit_chunk(original, Chunker(), encoding, 64)
    assert len(parts) > 1
    assert "".join(part.text for part in parts) == original.text
    assert all(
        len(encoding.encode(Chunker().contextualize(part))) <= 64 for part in parts
    )


def test_manifest_match_uses_corpus_year_not_filing_date(tmp_path):
    (tmp_path / "markdown/2025").mkdir(parents=True)
    (tmp_path / "downloads").mkdir()
    source = tmp_path / "markdown/2025/amzn.md"
    source.write_text("# Revenue\nA filing.", encoding="utf-8")
    filing = {
        "ticker": "AMZN",
        "cik": "0001018724",
        "form": "10-K",
        "filing_date": "2026-02-06",
        "report_date": "2025-12-31",
        "accession_number": "0001018724-26-000004",
        "primary_document": "amzn.htm",
        "source_url": "https://www.sec.gov/example",
        "local_path": "2025\\amzn.htm",
    }
    (tmp_path / "downloads/manifest.json").write_text(json.dumps({"filings": [filing]}))
    result = load_filing(source, tmp_path)
    assert result["corpus_year"] == 2025
    assert result["filing_date"] == "2026-02-06"
    assert result == load_filing(source, tmp_path)
    with pytest.raises(ValueError):
        load_filing(tmp_path / "outside.md", tmp_path)


def test_real_chunker_limits_context_and_preserves_table(tmp_path):
    import tiktoken
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    source = tmp_path / "fixture.md"
    source.write_text(
        "# Revenue\n\nAmounts in millions.\n\n"
        "| Category | 2025 | 2024 |\n|---|---|---|\n| Services | 100 | 90 |\n\n"
        "# Risks\n\n" + "Demand changes can affect revenue. " * 100,
        encoding="utf-8",
    )
    document = (
        DocumentConverter(allowed_formats=[InputFormat.MD]).convert(source).document
    )
    filing = {
        "document_id": "sample",
        "ticker": "TEST",
        "form": "10-K",
        "corpus_year": 2025,
        "accession_number": "sample",
        "source_url": "https://example.test/filing",
        "source_sha256": "abc",
    }
    rows = chunk_records(document, filing, "text-embedding-3-small", 1536, 128)
    encoding = tiktoken.get_encoding("cl100k_base")
    assert len(rows) > 1
    assert all(0 < row["token_count"] <= 128 for row in rows)
    assert all(
        row["token_count"] == len(encoding.encode(row["embedding_text"]))
        for row in rows
    )
    assert all(row["page"] is None for row in rows)
    table = next(row for row in rows if "Services" in row["text"])
    assert all(value in table["text"] for value in ("2025", "2024", "100", "90"))
    assert "Revenue" in table["embedding_text"]
    repeated = chunk_records(document, filing, "text-embedding-3-small", 1536, 128)
    assert repeated == rows
    with pytest.raises(ValueError):
        chunk_records(document, filing, "text-embedding-3-small", 1024, 128)
