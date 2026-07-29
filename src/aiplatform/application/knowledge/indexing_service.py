"""IndexingService — the single ingestion orchestrator (ADR-0016, ADR-0010).

One application service coordinating a document's ingestion end to end:

    chunk -> embed -> persist record -> persist vectors

It depends only on ports and pure collaborators (the ``ChunkingStrategy``, the
``EmbeddingProvider`` / ``KnowledgeRepository`` / ``VectorStore`` domain ports, and
the ``Clock``); it imports no concrete adapter, SDK, or framework.

Consistency model (so partial indexing cannot leave inconsistent state)
-----------------------------------------------------------------------
1. **Slow work first, before any write.** Chunking and embedding happen up front;
   if either fails, nothing has been persisted — there is nothing to undo.
2. **Record before vectors.** The document record is written first, then the
   vectors. Ordering matters: vectors keyed by chunk id reference a record that
   already exists.
3. **Compensation on failure.** If the vector upsert fails (even partway), the
   service removes the just-written vectors (idempotent ``delete``) *and* the
   record, so no half-indexed document survives. Cleanup is best-effort and never
   masks the original error.

True cross-store atomicity is an explicit non-goal for M3 (ADR-0016): with two
independent stores, compensation — not a distributed transaction — is the
mechanism. When both stores are co-located in PostgreSQL/pgvector (M3.7) a shared
transaction may replace compensation; that is an M3.7 refinement, invisible here.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiplatform.application.clock import Clock
from aiplatform.domain.knowledge.document import KnowledgeDocument
from aiplatform.domain.knowledge.ids import KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.domain.knowledge.ports import (
    EmbeddingProvider,
    KnowledgeRepository,
    VectorEntry,
    VectorStore,
)

from .chunking import ChunkingStrategy


@dataclass(frozen=True, slots=True)
class IndexingResult:
    """The outcome of ingesting one document — an application DTO for delivery."""

    document_id: KnowledgeDocumentId
    source: str
    chunk_count: int


class IndexingService:
    """Ingests a document: chunk, embed, and persist record + vectors."""

    def __init__(
        self,
        *,
        chunker: ChunkingStrategy,
        embedder: EmbeddingProvider,
        repository: KnowledgeRepository,
        vector_store: VectorStore,
        clock: Clock,
    ) -> None:
        """Inject the ports and collaborators; store no per-request state."""
        self._chunker = chunker
        self._embedder = embedder
        self._repository = repository
        self._vector_store = vector_store
        self._clock = clock

    async def index(
        self, *, source: str, text: str, metadata: Metadata | None = None
    ) -> IndexingResult:
        """Ingest ``text`` as a new document.

        Args:
            source: The document's origin identifier.
            text: The raw document text.
            metadata: Optional document-level metadata (inherited by every chunk).

        Returns:
            An :class:`IndexingResult` describing the persisted document.

        Raises:
            ValueError: If ``text`` has no indexable content (produces no chunks).
            EmbeddingError / VectorStoreError: Propagated after cleanup; no
                partial document remains.
        """
        document_metadata = metadata if metadata is not None else Metadata()

        # 1. Slow work, before any persistence.
        drafts = self._chunker.chunk(text)
        if not drafts:
            raise ValueError("document has no indexable content")

        document = KnowledgeDocument.start(
            source=source, created_at=self._clock.now(), metadata=document_metadata
        )
        for draft in drafts:
            document.add_chunk(
                draft.text, metadata=document_metadata, token_count=draft.token_count
            )

        vectors = await self._embedder.embed_documents([chunk.text for chunk in document.chunks])
        entries = [
            VectorEntry(
                chunk_id=chunk.id,
                document_id=document.id,
                vector=vector,
                text=chunk.text,
                metadata=chunk.metadata,
            )
            for chunk, vector in zip(document.chunks, vectors, strict=True)
        ]
        document.mark_indexed()

        # 2. Persist record, then vectors, with compensation on failure.
        await self._repository.add(document)
        try:
            await self._vector_store.upsert(entries)
        except Exception:
            await self._compensate(document.id)
            raise

        return IndexingResult(
            document_id=document.id, source=source, chunk_count=document.chunk_count
        )

    async def _compensate(self, document_id: KnowledgeDocumentId) -> None:
        """Best-effort cleanup after a failed vector write — never masks the cause."""
        try:
            await self._vector_store.delete(document_id)
        except Exception:
            pass
        try:
            await self._repository.delete(document_id)
        except Exception:
            pass
