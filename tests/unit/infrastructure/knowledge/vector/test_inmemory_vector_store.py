"""Unit tests for InMemoryVectorStore specifics beyond the contract (M3.2)."""

from __future__ import annotations

import pytest

from aiplatform.domain.knowledge.errors import DimensionMismatchError
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.domain.knowledge.vectors import EmbeddingVector
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore


def _entry(vector: tuple[float, ...]) -> VectorEntry:
    return VectorEntry(
        chunk_id=KnowledgeChunkId.generate(),
        document_id=KnowledgeDocumentId.generate(),
        vector=EmbeddingVector(vector),
        text="t",
        metadata=Metadata(),
    )


async def test_non_positive_k_returns_empty() -> None:
    store = InMemoryVectorStore()
    await store.upsert([_entry((1.0, 0.0))])
    assert await store.search(EmbeddingVector((1.0, 0.0)), k=0, filter=MetadataFilter.none()) == []


async def test_dimension_stays_established_after_deleting_all() -> None:
    store = InMemoryVectorStore()
    entry = _entry((1.0, 0.0, 0.0))
    await store.upsert([entry])
    await store.delete(entry.document_id)  # store now empty but dimension remembered
    with pytest.raises(DimensionMismatchError):
        await store.search(EmbeddingVector((1.0, 0.0)), k=1, filter=MetadataFilter.none())


async def test_empty_upsert_is_a_noop() -> None:
    store = InMemoryVectorStore()
    await store.upsert([])
    assert await store.search(EmbeddingVector((1.0,)), k=1, filter=MetadataFilter.none()) == []
