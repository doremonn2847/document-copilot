from types import SimpleNamespace

import pytest


@pytest.fixture
def config():
    return SimpleNamespace(
        database_url="postgresql://test:test@localhost/test",
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=1536,
        retrieval_candidate_k=50,
        retrieval_top_k=10,
        retrieval_rrf_k=60,
        retrieval_neighbor_radius=1,
        retrieval_fts_config="english",
        retrieval_fts_keyword_model="gpt-4o-mini",
        retrieval_fts_keyword_min=3,
        retrieval_fts_keyword_max=5,
        retrieval_fts_keyword_fast_path_tokens=5,
    )
