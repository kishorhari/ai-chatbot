"""SQLAlchemy ``KnowledgeRepository`` implementation (ADR-0016).

Speaks only in domain aggregates (via the mapping layer); callers never see a
session or ORM row. Reuses the M2 ``SessionProvider``. Snapshot independence is
intrinsic: every ``get`` rebuilds a fresh aggregate from rows. ``list`` applies the
metadata filter in Python (portable across SQLite and PostgreSQL, and consistent
with the in-memory store), acceptable for M3's modest knowledge bases.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiplatform.domain.knowledge.document import KnowledgeDocument
from aiplatform.domain.knowledge.errors import (
    KnowledgeDocumentAlreadyExistsError,
    KnowledgeDocumentNotFoundError,
)
from aiplatform.domain.knowledge.ids import KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import KnowledgeRepository
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider

from .mapping import chunk_to_row, document_to_row, rows_to_document
from .models import KnowledgeChunkRow, KnowledgeDocumentRow


class SqlAlchemyKnowledgeRepository(KnowledgeRepository):
    """Persists knowledge documents to a relational database via SQLAlchemy."""

    def __init__(self, provider: SessionProvider) -> None:
        """Store the session provider (shared with the transaction boundary)."""
        self._provider = provider

    async def add(self, document: KnowledgeDocument) -> None:
        """Insert a new document and all its chunks."""
        async with self._provider.session() as session:
            if await session.get(KnowledgeDocumentRow, document.id.value) is not None:
                raise KnowledgeDocumentAlreadyExistsError(document.id)
            session.add(document_to_row(document))
            for chunk in document.chunks:
                session.add(chunk_to_row(document.id, chunk))

    async def get(self, document_id: KnowledgeDocumentId) -> KnowledgeDocument:
        """Load a document and its ordinal-ordered chunks."""
        async with self._provider.session() as session:
            return await self._load(session, document_id)

    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Delete a document and its chunks; raise if it does not exist."""
        async with self._provider.session() as session:
            root = await session.get(KnowledgeDocumentRow, document_id.value)
            if root is None:
                raise KnowledgeDocumentNotFoundError(document_id)
            await session.execute(
                delete(KnowledgeChunkRow).where(KnowledgeChunkRow.document_id == document_id.value)
            )
            await session.delete(root)

    async def list(self, filter: MetadataFilter) -> tuple[KnowledgeDocument, ...]:
        """Return the documents whose metadata satisfies ``filter``."""
        async with self._provider.session() as session:
            roots = (await session.execute(select(KnowledgeDocumentRow))).scalars().all()
            matched = [root for root in roots if filter.matches(Metadata.of(root.doc_metadata))]
            documents = [
                await self._load(session, KnowledgeDocumentId(root.id)) for root in matched
            ]
            return tuple(documents)

    async def _load(
        self, session: AsyncSession, document_id: KnowledgeDocumentId
    ) -> KnowledgeDocument:
        """Load and rebuild a single document (root + ordered chunks)."""
        root = await session.get(KnowledgeDocumentRow, document_id.value)
        if root is None:
            raise KnowledgeDocumentNotFoundError(document_id)
        chunks = (
            (
                await session.execute(
                    select(KnowledgeChunkRow)
                    .where(KnowledgeChunkRow.document_id == document_id.value)
                    .order_by(KnowledgeChunkRow.ordinal)
                )
            )
            .scalars()
            .all()
        )
        return rows_to_document(root, chunks)
