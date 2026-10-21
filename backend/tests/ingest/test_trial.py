from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ingest.trial import embed, persist_trial, require_match, validate_vector


@pytest.mark.parametrize(
    "vector", [[1.0], [float("nan")] * 1536, [float("inf")] * 1536, [0.0] * 1536]
)
def test_rejects_invalid_vectors(vector):
    with pytest.raises(ValueError):
        validate_vector(vector)


def test_conflicting_rerun_is_rejected():
    with pytest.raises(ValueError):
        require_match({"source_sha256": "old"}, {"source_sha256": "changed"})


def test_matching_rerun_never_calls_embedding(monkeypatch):
    source = {
        "id": "source",
        "accession_number": "accession",
        "filing_date": "2025-10-31",
        "report_date": "2025-09-27",
    }
    chunk = {
        "id": "chunk",
        "document_id": "source",
        "chunk_index": 11,
        "text": "trade",
        "chunk_metadata": {"source_sha256": "same"},
    }
    conn = Mock()
    import json

    conn.execute.return_value.fetchone.side_effect = [
        {"locked": True},
        source,
        {**chunk, "vector_text": json.dumps([0.1] * 1536)},
    ]
    paid_call = Mock(side_effect=AssertionError("Must not make a paid call"))
    monkeypatch.setattr("ingest.trial.embed", paid_call)
    assert persist_trial(conn, source, chunk, {}, None)["embedding_requests"] == 0
    paid_call.assert_not_called()


def test_changed_rerun_fails_before_embedding(monkeypatch):
    conn = Mock()
    conn.execute.return_value.fetchone.side_effect = [
        {"locked": True},
        {
            "id": "source",
            "filing_date": "2025-10-31",
            "report_date": "2025-09-27",
            "accession_number": "accession",
            "markdown_content": "old",
        },
        None,
    ]
    paid_call = Mock()
    monkeypatch.setattr("ingest.trial.embed", paid_call)
    with pytest.raises(ValueError):
        persist_trial(
            conn,
            {
                "id": "source",
                "accession_number": "accession",
                "markdown_content": "new",
            },
            {"chunk_index": 11},
            {},
            None,
        )
    paid_call.assert_not_called()


def test_embedding_sends_only_selected_input(monkeypatch):
    client = Mock()
    client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=[0.1] * 1536)],
        usage=SimpleNamespace(total_tokens=840),
    )
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=client)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("ingest.trial.OpenAI", factory)
    settings = SimpleNamespace(
        openai_api_key=Mock(), openai_embedding_model="text-embedding-3-small"
    )
    vector, tokens = embed({"embedding_text": "reviewed passage"}, settings)
    assert len(vector) == 1536 and tokens == 840
    assert client.embeddings.create.call_args.kwargs["input"] == ["reviewed passage"]
    assert factory.call_args.kwargs["max_retries"] == 0
