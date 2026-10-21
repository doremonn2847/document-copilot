import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.retrieval.embeddings import embed_query
from app.retrieval.keywords import (
    FtsKeywords,
    KeywordDeps,
    extract_keywords,
    filter_keywords,
)
from app.retrieval.types import SearchFilters


def test_embedding_full_question_and_validation(config):
    client = SimpleNamespace(embeddings=SimpleNamespace(create=AsyncMock()))
    client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=[0.1] * 1536)],
        usage=SimpleNamespace(total_tokens=8),
    )
    vector, tokens = asyncio.run(
        embed_query("The full analyst question", config, client)
    )
    assert len(vector) == 1536 and tokens == 8
    assert (
        client.embeddings.create.call_args.kwargs["input"]
        == "The full analyst question"
    )
    for invalid in ([0.1], [float("nan")] * 1536, [0.0] * 1536):
        client.embeddings.create.return_value.data[0].embedding = invalid
        with pytest.raises(ValueError):
            asyncio.run(embed_query("question", config, client))


def test_short_query_skips_model(config):
    agent = SimpleNamespace(run=AsyncMock(side_effect=AssertionError("Paid call")))
    result = asyncio.run(
        extract_keywords("Azure cloud", [SearchFilters(ticker="MSFT")], config, agent)
    )
    assert result.text == "Azure cloud" and result.usage.keyword_requests == 0
    agent.run.assert_not_called()


def test_typed_keyword_output_and_failure(config):
    agent = Agent(
        TestModel(custom_output_args={"terms": ["Azure", "cloud", "capacity"]}),
        output_type=FtsKeywords,
        deps_type=KeywordDeps,
    )
    result = asyncio.run(
        extract_keywords(
            "What changed about Azure cloud capacity over time?", [], config, agent
        )
    )
    assert result.text == "Azure cloud capacity"
    assert result.usage.keyword_requests == 1
    bad_agent = Agent(
        TestModel(
            custom_output_args={
                "terms": ["too many words for the lexical search budget"]
            }
        ),
        output_type=FtsKeywords,
        deps_type=KeywordDeps,
        retries={"output": 1, "tools": 0},
    )
    bad = asyncio.run(
        extract_keywords(
            "This question has more than five search words", [], config, bad_agent
        )
    )
    assert bad.text is None and "unavailable" in bad.warning.lower()
    assert bad.usage.keyword_requests == 2


def test_keyword_provider_failure_is_visible(config):
    agent = SimpleNamespace(run=AsyncMock(side_effect=TimeoutError()))
    result = asyncio.run(
        extract_keywords(
            "What changed about Microsoft Azure capacity in recent years?",
            [],
            config,
            agent,
        )
    )
    assert result.text is None and result.warning


def test_redundant_company_and_year_words_removed(config):
    filters = [SearchFilters(ticker="AAPL", corpus_years=[2025])]
    assert filter_keywords(
        ["Apple", "2025", "tariffs", "supply", "chains"], filters, config
    ) == ["tariffs", "supply", "chains"]
    assert filter_keywords(
        ["Microsoft", "Azure", "cloud", "services"],
        [SearchFilters(ticker="MSFT")],
        config,
    ) == ["Azure", "cloud", "services"]
    with pytest.raises(ValueError):
        filter_keywords(["Apple", "supply", "chains"], filters, config)


def test_keyword_schema_exposes_individual_word_budget():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FtsKeywords(terms=["operating income", "margin", "AWS"])
    assert FtsKeywords(terms=["operating", "income", "margin", "AWS"]).terms == [
        "operating",
        "income",
        "margin",
        "AWS",
    ]
