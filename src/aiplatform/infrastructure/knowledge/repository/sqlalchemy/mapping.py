"""Pure translation between the knowledge aggregate and ORM rows (ADR-0016)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from aiplatform.domain.knowledge.chunk import KnowledgeChunk
from aiplatform.domain.knowledge.document import IngestionStatus, KnowledgeDocument
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata

from .models import KnowledgeChunkRow, KnowledgeDocumentRow


def document_to_row(document: KnowledgeDocument) -> KnowledgeDocumentRow:
    """Build the root row from a knowledge document."""
    return KnowledgeDocumentRow(
        id=document.id.value,
        source=document.source,
        created_at=document.created_at,
        status=document.status.value,
        doc_metadata=document.metadata.as_dict(),
    )


def chunk_to_row(document_id: KnowledgeDocumentId, chunk: KnowledgeChunk) -> KnowledgeChunkRow:
    """Build a chunk row belonging to ``document_id``."""
    return KnowledgeChunkRow(
        id=chunk.id.value,
        document_id=document_id.value,
        ordinal=chunk.ordinal,
        text=chunk.text,
        chunk_metadata=chunk.metadata.as_dict(),
        token_count=chunk.token_count,
    )


def rows_to_document(
    document: KnowledgeDocumentRow, chunks: Sequence[KnowledgeChunkRow]
) -> KnowledgeDocument:
    """Rebuild an aggregate from its root row and ordinal-ordered chunk rows."""
    domain_chunks = [_row_to_chunk(row) for row in chunks]
    return KnowledgeDocument.reconstitute(
        document_id=KnowledgeDocumentId(document.id),
        source=document.source,
        created_at=_ensure_utc(document.created_at),
        metadata=Metadata.of(document.doc_metadata),
        status=IngestionStatus(document.status),
        chunks=domain_chunks,
    )


def _row_to_chunk(row: KnowledgeChunkRow) -> KnowledgeChunk:
    """Rebuild a domain chunk from its row."""
    return KnowledgeChunk(
        id=KnowledgeChunkId(row.id),
        ordinal=row.ordinal,
        text=row.text,
        metadata=Metadata.of(row.chunk_metadata),
        token_count=row.token_count,
    )


def _ensure_utc(value: datetime) -> datetime:
    """Normalise a stored timestamp to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
