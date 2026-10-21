from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from app.config import Settings


def validate_question(query: str) -> str:
    query = query.strip()
    # A UTF-8 byte cap is a conservative token bound without a runtime tokenizer dependency.
    if not query or len(query.encode("utf-8")) > 8191:
        raise ValueError("Question must be nonempty and at most 8191 UTF-8 bytes")
    return query


async def embed_query(
    query: str, settings: Settings, client: AsyncOpenAI
) -> tuple[list[float], int]:
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
        input=validate_question(query),
        encoding_format="float",
    )
    if len(response.data) != 1 or response.data[0].index != 0:
        raise ValueError("Unexpected query embedding response")
    vector = response.data[0].embedding
    if (
        len(vector) != settings.openai_embedding_dimensions
        or not all(math.isfinite(x) for x in vector)
        or not any(vector)
    ):
        raise ValueError("Invalid query embedding")
    return vector, response.usage.total_tokens
