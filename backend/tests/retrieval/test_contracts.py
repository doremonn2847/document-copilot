from uuid import UUID

import pytest
from pydantic import ValidationError

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.types import (
    RetrievedPassage,
    SearchFilters,
    format_passages_for_agent,
)


def passage(index=1, **changes):
    values = {
        "chunk_id": UUID(int=index),
        "document_id": UUID(int=100),
        "chunk_index": index,
        "text": "Evidence " * 1000,
        "ticker": "AAPL",
        "form": "10-K",
        "accession_number": "test",
        "source_url": "https://www.sec.gov/test",
        "filing_date": "2026-02-01",
        "report_date": "2025-12-31",
        "corpus_year": 2025,
    }
    return RetrievedPassage(**(values | changes))


def test_fusion_agreement_dedup_and_ties():
    a, b, c = [UUID(int=i) for i in (1, 2, 3)]
    result = reciprocal_rank_fusion([[a, a, b], [b, c]])
    assert result[0][0] == b
    assert dict(result)[a] == pytest.approx(1 / 61)
    assert dict(result)[b] == pytest.approx(1 / 62 + 1 / 61)
    assert reciprocal_rank_fusion([[b], [a]])[0][0] == a
    assert reciprocal_rank_fusion([[], []]) == []


def test_filters_and_unknown_year_labels():
    assert SearchFilters(ticker=" aapl ").ticker == "AAPL"
    with pytest.raises(ValidationError):
        SearchFilters(corpus_years=[])
    output = format_passages_for_agent([passage()])
    assert "corpus year 2025" in output
    assert "FY2026" not in output and "FY2025" not in output
    assert "fiscal year unverified" in output
    assert "truncated" in output


def test_formatting_total_cap_and_raw_text_preserved():
    passages = [passage(i) for i in range(1, 31)]
    output = format_passages_for_agent(passages)
    assert len(output) <= 12000 and "truncated" in output
    assert len(passages[0].text) == 9000
