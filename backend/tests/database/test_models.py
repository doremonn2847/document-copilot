from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.database.models import Base, ChatMessage, DocumentChunk, MessageCitation


def test_models_map_and_compile_for_postgres():
    configure_mappers()
    assert set(Base.metadata.tables) == {
        "users",
        "chat_threads",
        "chat_messages",
        "source_documents",
        "document_chunks",
        "message_citations",
        "message_feedback",
        "demo_visitors",
        "demo_budget_days",
        "demo_attempts",
        "demo_model_requests",
    }
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE {table.name}" in ddl
        for foreign_key in table.foreign_keys:
            assert foreign_key.column is not None


def test_ordering_and_ingestion_are_unique_per_parent():
    expected = [
        (ChatMessage, ("thread_id", "sequence")),
        (DocumentChunk, ("document_id", "chunk_index")),
        (MessageCitation, ("message_id", "citation_index")),
    ]
    for model, columns in expected:
        constraints = {
            tuple(constraint.columns.keys())
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert columns in constraints


def test_citations_protect_source_evidence_and_embedding_dimension():
    foreign_key = next(iter(MessageCitation.__table__.c.chunk_id.foreign_keys))
    assert foreign_key.ondelete == "RESTRICT"
    ddl = str(
        CreateTable(DocumentChunk.__table__).compile(dialect=postgresql.dialect())
    )
    assert "VECTOR(1536)" in ddl
