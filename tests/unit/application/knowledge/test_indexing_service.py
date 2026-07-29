"""Unit tests for IndexingService orchestration + consistency (M3.3).

Exercised against the real in-memory repository and vector store, a fake embedder,
and a fixed clock — no network. The consistency tests use failing fakes to prove
that a failure leaves no partial document and triggers vector cleanup.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.chunking import TokenAwareChunker
from aiplatform.application.knowledge.indexing_service import IndexingService
from aiplatform.domain.knowledge.errors import VectorStoreError
from aiplatform.domain.knowledge.ids import KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider
from aiplatform.infrastructure.knowledge.repository.memory.repository import (
    InMemoryKnowledgeRepository,
)
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _TS


class _FailingVectorStore(InMemoryVectorStore):
    """Fails every upsert and records compensating deletes."""

    def __init__(self) -> None:
        super().__init__()
        self.deleted: list[KnowledgeDocumentId] = []

    async def upsert(self, entries: Sequence[VectorEntry]) -> None:
        raise VectorStoreError("simulated vector backend failure")

    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        self.deleted.append(document_id)
        await super().delete(document_id)


def _service(
    *,
    repository: InMemoryKnowledgeRepository | None = None,
    vector_store: InMemoryVectorStore | None = None,
) -> tuple[IndexingService, InMemoryKnowledgeRepository, InMemoryVectorStore]:
    repo = repository or InMemoryKnowledgeRepository()
    store = vector_store or InMemoryVectorStore()
    service = IndexingService(
        chunker=TokenAwareChunker(
            HeuristicTokenEstimator(), chunk_size_tokens=16, overlap_tokens=4
        ),
        embedder=FakeEmbeddingProvider(dimension=32),
        repository=repo,
        vector_store=store,
        clock=_FixedClock(),
    )
    return service, repo, store


async def test_index_persists_record_and_searchable_vectors() -> None:
    service, repo, store = _service()
    text = " ".join(f"Sentence {i} about topic alpha." for i in range(10))

    result = await service.index(source="doc.md", text=text, metadata=Metadata.of({"lang": "en"}))

    stored = await repo.get(result.document_id)
    assert stored.source == "doc.md"
    assert stored.chunk_count == result.chunk_count > 0
    assert stored.status.value == "indexed"

    query = await FakeEmbeddingProvider(dimension=32).embed_query("topic alpha")
    matches = await store.search(query, k=3, filter=MetadataFilter(equals=(("lang", "en"),)))
    assert matches
    assert all(m.document_id == result.document_id for m in matches)


async def test_empty_content_is_rejected_and_persists_nothing() -> None:
    service, repo, _ = _service()
    with pytest.raises(ValueError, match="no indexable content"):
        await service.index(source="empty.md", text="   \n\n  ")
    assert await repo.list(MetadataFilter.none()) == ()


async def test_vector_failure_rolls_back_the_record() -> None:
    repo = InMemoryKnowledgeRepository()
    service, _, _ = _service(repository=repo, vector_store=_FailingVectorStore())

    with pytest.raises(VectorStoreError):
        await service.index(source="doc.md", text="Some content that will chunk and embed.")

    # Compensation removed the record: no half-indexed document remains.
    assert await repo.list(MetadataFilter.none()) == ()


async def test_vector_failure_triggers_vector_cleanup() -> None:
    store = _FailingVectorStore()
    service, _, _ = _service(vector_store=store)

    with pytest.raises(VectorStoreError):
        await service.index(source="doc.md", text="content here that chunks fine.")

    # The compensation path attempted to delete the document's vectors.
    assert len(store.deleted) == 1


async def test_chunks_inherit_document_metadata() -> None:
    service, repo, _ = _service()
    result = await service.index(
        source="doc.md", text="Alpha beta. Gamma delta.", metadata=Metadata.of({"kind": "faq"})
    )
    stored = await repo.get(result.document_id)
    assert all(c.metadata.get("kind") == "faq" for c in stored.chunks)
