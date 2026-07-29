"""In-memory ``KnowledgeRepository`` implementation (ADR-0016).

A process-local mapping of document id → document, the reference the shared
knowledge-repository contract suite runs against first (pgvector/SQLAlchemy at
M3.7 must pass the identical suite). Like the M2 conversation repository, it
enforces snapshot independence by copying via ``KnowledgeDocument.reconstitute``
on every write and read — a loaded document's mutation never touches storage, and
two loads never alias.
"""

from __future__ import annotations

from aiplatform.domain.knowledge.document import KnowledgeDocument
from aiplatform.domain.knowledge.errors import (
    KnowledgeDocumentAlreadyExistsError,
    KnowledgeDocumentNotFoundError,
)
from aiplatform.domain.knowledge.ids import KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import MetadataFilter
from aiplatform.domain.knowledge.ports import KnowledgeRepository


class InMemoryKnowledgeRepository(KnowledgeRepository):
    """Stores knowledge documents in an in-process mapping keyed by identity."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._documents: dict[KnowledgeDocumentId, KnowledgeDocument] = {}

    async def add(self, document: KnowledgeDocument) -> None:
        """Store a new document; reject a duplicate identity."""
        if document.id in self._documents:
            raise KnowledgeDocumentAlreadyExistsError(document.id)
        self._documents[document.id] = self._snapshot(document)

    async def get(self, document_id: KnowledgeDocumentId) -> KnowledgeDocument:
        """Return an independent copy of the stored document."""
        stored = self._documents.get(document_id)
        if stored is None:
            raise KnowledgeDocumentNotFoundError(document_id)
        return self._snapshot(stored)

    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Delete a document; raise if it does not exist."""
        if document_id not in self._documents:
            raise KnowledgeDocumentNotFoundError(document_id)
        del self._documents[document_id]

    async def list(self, filter: MetadataFilter) -> tuple[KnowledgeDocument, ...]:
        """Return independent copies of the documents matching ``filter``."""
        return tuple(
            self._snapshot(document)
            for document in self._documents.values()
            if filter.matches(document.metadata)
        )

    @staticmethod
    def _snapshot(document: KnowledgeDocument) -> KnowledgeDocument:
        """Return an independent, re-validated copy of ``document``."""
        return KnowledgeDocument.reconstitute(
            document_id=document.id,
            source=document.source,
            created_at=document.created_at,
            metadata=document.metadata,
            status=document.status,
            chunks=document.chunks,
        )
