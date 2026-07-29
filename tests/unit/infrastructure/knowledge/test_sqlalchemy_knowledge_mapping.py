"""Unit tests for the knowledge domain <-> ORM mapping (M3.7) — pure, no database."""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.domain.knowledge.document import IngestionStatus, KnowledgeDocument
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.infrastructure.knowledge.repository.sqlalchemy import mapping
from aiplatform.infrastructure.knowledge.repository.sqlalchemy.models import KnowledgeChunkRow

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _document() -> KnowledgeDocument:
    doc = KnowledgeDocument.start(
        source="handbook.md", created_at=_TS, metadata=Metadata.of({"lang": "en"})
    )
    doc.add_chunk("first", metadata=Metadata.of({"lang": "en"}), token_count=1)
    doc.add_chunk("second", metadata=Metadata.of({"lang": "en"}), token_count=2)
    doc.mark_indexed()
    return doc


def test_round_trip_preserves_aggregate() -> None:
    original = _document()
    doc_row = mapping.document_to_row(original)
    chunk_rows = [mapping.chunk_to_row(original.id, c) for c in original.chunks]

    rebuilt = mapping.rows_to_document(doc_row, chunk_rows)

    assert rebuilt.id == original.id
    assert rebuilt.source == original.source
    assert rebuilt.created_at == original.created_at
    assert rebuilt.metadata == original.metadata
    assert rebuilt.status is IngestionStatus.INDEXED
    assert [c.text for c in rebuilt.chunks] == ["first", "second"]
    assert [c.ordinal for c in rebuilt.chunks] == [0, 1]
    assert rebuilt.chunks[1].token_count == 2
    assert rebuilt.chunks[0].metadata.get("lang") == "en"


def test_document_row_records_status_and_metadata() -> None:
    row = mapping.document_to_row(_document())
    assert row.status == "indexed"
    assert row.doc_metadata == {"lang": "en"}
    assert row.source == "handbook.md"


def test_naive_stored_timestamp_is_normalised_to_utc() -> None:
    doc = _document()
    row = mapping.document_to_row(doc)
    row.created_at = datetime(2026, 7, 29, 12, 0, 0)  # naive (e.g. from SQLite)
    chunk_row = KnowledgeChunkRow(
        id=doc.chunks[0].id.value,
        document_id=doc.id.value,
        ordinal=0,
        text="first",
        chunk_metadata={},
        token_count=1,
    )
    rebuilt = mapping.rows_to_document(row, [chunk_row])
    assert rebuilt.created_at.tzinfo is not None
    assert rebuilt.created_at == _TS
