import json
from types import SimpleNamespace

import pytest

from ingest.filing import check_saved, fingerprint, response_vectors, write_json


def test_response_reordered_by_index_and_missing_rejected():
    a, b = [0.1] * 1536, [0.2] * 1536
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=b),
            SimpleNamespace(index=0, embedding=a),
        ]
    )
    assert response_vectors(response, 2) == [a, b]
    with pytest.raises(ValueError):
        response_vectors(response, 3)
    response.data[0].index = 0
    with pytest.raises(ValueError):
        response_vectors(response, 2)


def test_saved_trial_is_reusable_but_changed_content_is_not():
    row = {
        "id": "a",
        "document_id": "b",
        "chunk_index": 0,
        "page": None,
        "section": None,
        "text": "Trade risk",
        "token_count": 2,
        "metadata": {"model": "small", "source_sha256": "original"},
    }
    saved = {
        **row,
        "chunk_metadata": {**row["metadata"], "trial": True},
        "vector_text": json.dumps([0.1] * 1536),
    }
    check_saved(saved, row)
    with pytest.raises(ValueError):
        check_saved(saved, {**row, "text": "Changed"})
    with pytest.raises(ValueError):
        check_saved(saved, {**row, "metadata": {"source_sha256": "changed"}})


def test_cache_survives_reload_and_detects_changes(tmp_path):
    row = {"text": "original", "metadata": {"model": "small"}}
    path = tmp_path / "cache.json"
    write_json(path, {"fingerprint": fingerprint(row), "vector": [0.1] * 1536})
    cached = json.loads(path.read_text())
    assert cached["fingerprint"] == fingerprint(row)
    assert cached["fingerprint"] != fingerprint({**row, "text": "changed"})
    assert not path.with_suffix(".json.tmp").exists()
