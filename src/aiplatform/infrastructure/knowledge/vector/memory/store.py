"""InMemoryVectorStore — the deterministic reference vector index (ADR-0013).

A process-local mapping of chunk id → entry, with brute-force cosine similarity
search. It is the offline reference the shared vector-store contract suite runs
against first; pgvector (M3.7) must pass the identical suite. It is a **search
index only** — distinct from the ``KnowledgeRepository`` record (ADR-0013) — and
stores each entry's payload (text + metadata) so retrieval is a single call.

The similarity metric is cosine (fixed by the port contract). The store's vector
dimension is established by the first upsert; a later entry or query of a
different dimension fails fast with ``DimensionMismatchError`` — the same guard
pgvector gives via its typed column.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiplatform.domain.knowledge.errors import DimensionMismatchError
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry, VectorMatch, VectorStore
from aiplatform.domain.knowledge.vectors import EmbeddingVector


class InMemoryVectorStore(VectorStore):
    """Stores vectors in an in-process mapping keyed by chunk id."""

    def __init__(self) -> None:
        """Create an empty store with no established dimension."""
        self._entries: dict[KnowledgeChunkId, VectorEntry] = {}
        self._dimension: int | None = None

    async def upsert(self, entries: Sequence[VectorEntry]) -> None:
        """Insert or replace entries by chunk id, validating dimension."""
        for entry in entries:
            self._ensure_dimension(entry.vector.dimension)
            self._entries[entry.chunk_id] = entry

    async def search(
        self, query: EmbeddingVector, *, k: int, filter: MetadataFilter
    ) -> list[VectorMatch]:
        """Return the ``k`` most cosine-similar entries matching ``filter``."""
        if self._dimension is not None and query.dimension != self._dimension:
            raise DimensionMismatchError(expected=self._dimension, actual=query.dimension)
        matches = [
            VectorMatch(
                chunk_id=entry.chunk_id,
                document_id=entry.document_id,
                text=entry.text,
                metadata=entry.metadata,
                score=query.cosine_similarity(entry.vector),
            )
            for entry in self._entries.values()
            if filter.matches(entry.metadata)
        ]
        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:k] if k > 0 else []

    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Remove all entries belonging to ``document_id`` (idempotent)."""
        self._entries = {
            chunk_id: entry
            for chunk_id, entry in self._entries.items()
            if entry.document_id != document_id
        }

    def _ensure_dimension(self, dimension: int) -> None:
        """Establish the store dimension on first use; reject mismatches after."""
        if self._dimension is None:
            self._dimension = dimension
        elif dimension != self._dimension:
            raise DimensionMismatchError(expected=self._dimension, actual=dimension)
