"""Unit tests for the KnowledgeDocument aggregate + KnowledgeChunk (M3.0)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.domain.knowledge.chunk import KnowledgeChunk
from aiplatform.domain.knowledge.document import IngestionStatus, KnowledgeDocument
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _document() -> KnowledgeDocument:
    return KnowledgeDocument.start(source="handbook.md", created_at=_TS)


def test_start_creates_pending_empty_document() -> None:
    doc = _document()
    assert doc.source == "handbook.md"
    assert doc.status is IngestionStatus.PENDING
    assert doc.chunk_count == 0
    assert isinstance(doc.id, KnowledgeDocumentId)


def test_empty_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="source must be non-empty"):
        KnowledgeDocument.start(source="", created_at=_TS)


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        KnowledgeDocument.start(source="x", created_at=datetime(2026, 7, 29, 12, 0, 0))


def test_add_chunk_assigns_contiguous_ordinals() -> None:
    doc = _document()
    doc.add_chunk("first")
    doc.add_chunk("second", metadata=Metadata.of({"section": "intro"}))
    assert [c.ordinal for c in doc.chunks] == [0, 1]
    assert [c.text for c in doc.chunks] == ["first", "second"]
    assert doc.chunks[1].metadata.get("section") == "intro"


def test_status_transitions() -> None:
    doc = _document()
    doc.mark_indexed()
    assert doc.status is IngestionStatus.INDEXED
    doc.mark_failed()
    assert doc.status is IngestionStatus.FAILED


def test_chunks_snapshot_is_immutable() -> None:
    doc = _document()
    doc.add_chunk("a")
    snapshot = doc.chunks
    doc.add_chunk("b")
    assert len(snapshot) == 1  # earlier snapshot unaffected


def test_reconstitute_validates_ordinal_contiguity() -> None:
    bad_chunks = [
        KnowledgeChunk(id=KnowledgeChunkId.generate(), ordinal=0, text="a"),
        KnowledgeChunk(id=KnowledgeChunkId.generate(), ordinal=2, text="c"),  # gap
    ]
    with pytest.raises(ValueError, match="contiguous"):
        KnowledgeDocument.reconstitute(
            document_id=KnowledgeDocumentId.generate(),
            source="x",
            created_at=_TS,
            metadata=Metadata(),
            status=IngestionStatus.INDEXED,
            chunks=bad_chunks,
        )


def test_reconstitute_round_trips_state() -> None:
    original = _document()
    original.add_chunk("only")
    original.mark_indexed()
    rebuilt = KnowledgeDocument.reconstitute(
        document_id=original.id,
        source=original.source,
        created_at=original.created_at,
        metadata=original.metadata,
        status=original.status,
        chunks=original.chunks,
    )
    assert rebuilt == original  # equal by identity
    assert rebuilt.status is IngestionStatus.INDEXED
    assert rebuilt.chunk_count == 1


def test_equality_is_by_identity() -> None:
    a = _document()
    b = KnowledgeDocument.start(source="other.md", created_at=_TS, document_id=a.id)
    assert a == b  # same id, different state
    assert hash(a) == hash(b)


def test_chunk_rejects_empty_text_and_negative_ordinal() -> None:
    with pytest.raises(ValueError, match="text must be non-empty"):
        KnowledgeChunk(id=KnowledgeChunkId.generate(), ordinal=0, text="")
    with pytest.raises(ValueError, match="ordinal must be non-negative"):
        KnowledgeChunk(id=KnowledgeChunkId.generate(), ordinal=-1, text="x")
