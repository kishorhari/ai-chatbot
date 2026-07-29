"""The ``KnowledgeDocument`` aggregate root (ADR-0011/0016).

Mirrors the M2 ``Conversation`` aggregate: it owns its append-only
``KnowledgeChunk`` entities and is the consistency boundary, enforcing its
invariants in one place —

* chunks have contiguous, zero-based ``ordinal`` values;
* the ``source`` (origin identifier) is non-empty;
* ``created_at`` is timezone-aware (time is injected, never read from a clock).

Two construction paths mirror the conversation aggregate: :meth:`start` for a new
document and :meth:`reconstitute` for rebuilding from persisted state (the
repository's entry point), both running the same invariant checks.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Self

from .chunk import KnowledgeChunk
from .ids import KnowledgeChunkId, KnowledgeDocumentId
from .metadata import Metadata


class IngestionStatus(StrEnum):
    """Lifecycle of a document's indexing.

    ``PENDING`` on creation, ``INDEXED`` once its chunks are embedded and stored,
    ``FAILED`` if ingestion did not complete. The status is metadata about the
    ingestion process, not about the content.
    """

    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeDocument:
    """A source document and its ordered, append-only chunks."""

    def __init__(
        self,
        *,
        document_id: KnowledgeDocumentId,
        source: str,
        created_at: datetime,
        metadata: Metadata | None = None,
        status: IngestionStatus = IngestionStatus.PENDING,
        chunks: Sequence[KnowledgeChunk] = (),
    ) -> None:
        """Construct and validate a document.

        Prefer the :meth:`start` / :meth:`reconstitute` factories; this initialiser
        is shared by both and enforces every invariant.

        Raises:
            ValueError: If the source is empty, ``created_at`` is naive, or the
                chunk ordinals are not contiguous from zero.
        """
        if not source:
            raise ValueError("knowledge document source must be non-empty")
        if created_at.tzinfo is None:
            raise ValueError("knowledge document created_at must be timezone-aware")
        self._id = document_id
        self._source = source
        self._created_at = created_at
        self._metadata = metadata if metadata is not None else Metadata()
        self._status = status
        self._chunks: list[KnowledgeChunk] = list(chunks)
        self._validate_ordinals(self._chunks)

    @classmethod
    def start(
        cls,
        *,
        source: str,
        created_at: datetime,
        metadata: Metadata | None = None,
        document_id: KnowledgeDocumentId | None = None,
    ) -> Self:
        """Begin a new, unindexed document with no chunks."""
        return cls(
            document_id=document_id or KnowledgeDocumentId.generate(),
            source=source,
            created_at=created_at,
            metadata=metadata,
            status=IngestionStatus.PENDING,
            chunks=(),
        )

    @classmethod
    def reconstitute(
        cls,
        *,
        document_id: KnowledgeDocumentId,
        source: str,
        created_at: datetime,
        metadata: Metadata,
        status: IngestionStatus,
        chunks: Sequence[KnowledgeChunk],
    ) -> Self:
        """Rebuild a document from persisted state (repository entry point)."""
        return cls(
            document_id=document_id,
            source=source,
            created_at=created_at,
            metadata=metadata,
            status=status,
            chunks=chunks,
        )

    @staticmethod
    def _validate_ordinals(chunks: Sequence[KnowledgeChunk]) -> None:
        """Enforce contiguous, zero-based chunk ordinals."""
        for index, chunk in enumerate(chunks):
            if chunk.ordinal != index:
                raise ValueError(
                    f"chunk ordinals must be contiguous from 0; "
                    f"expected {index}, got {chunk.ordinal}"
                )

    def add_chunk(
        self, text: str, *, metadata: Metadata | None = None, token_count: int | None = None
    ) -> KnowledgeChunk:
        """Append a chunk to the document and return it.

        The next ``ordinal`` is assigned by the aggregate, so contiguity cannot be
        violated by callers.
        """
        chunk = KnowledgeChunk(
            id=KnowledgeChunkId.generate(),
            ordinal=len(self._chunks),
            text=text,
            metadata=metadata if metadata is not None else Metadata(),
            token_count=token_count,
        )
        self._chunks.append(chunk)
        return chunk

    def mark_indexed(self) -> None:
        """Record that the document's chunks have been embedded and stored."""
        self._status = IngestionStatus.INDEXED

    def mark_failed(self) -> None:
        """Record that ingestion did not complete."""
        self._status = IngestionStatus.FAILED

    @property
    def id(self) -> KnowledgeDocumentId:
        """The document's identity."""
        return self._id

    @property
    def source(self) -> str:
        """The document's origin identifier."""
        return self._source

    @property
    def created_at(self) -> datetime:
        """When the document was created."""
        return self._created_at

    @property
    def metadata(self) -> Metadata:
        """The document-level metadata."""
        return self._metadata

    @property
    def status(self) -> IngestionStatus:
        """The current ingestion status."""
        return self._status

    @property
    def chunks(self) -> tuple[KnowledgeChunk, ...]:
        """An immutable, ordered snapshot of the chunks."""
        return tuple(self._chunks)

    @property
    def chunk_count(self) -> int:
        """The number of chunks in the document."""
        return len(self._chunks)

    def __eq__(self, other: object) -> bool:
        """Entities are equal by identity, not by current state."""
        if not isinstance(other, KnowledgeDocument):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        """Hash by the stable identity."""
        return hash(self._id)

    def __repr__(self) -> str:
        """Return an unambiguous, state-summarising representation."""
        return (
            f"KnowledgeDocument(id={self._id}, source={self._source!r}, "
            f"status={self._status.value}, chunks={len(self._chunks)})"
        )
