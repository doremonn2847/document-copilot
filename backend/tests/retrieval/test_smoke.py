import pytest

from scripts.smoke_retrieval import parse_target


def test_explicit_target_parser():
    assert parse_target("aapl:2025").model_dump(exclude_none=True) == {
        "ticker": "AAPL",
        "form": "10-K",
        "corpus_years": [2025],
    }
    with pytest.raises(ValueError):
        parse_target("AAPL:not-a-year")
    with pytest.raises(ValueError):
        parse_target("AAPL:2025:extra")
