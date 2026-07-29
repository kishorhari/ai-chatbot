"""Unit tests for SemanticRetriever (M3.4).

Exercised against the real fake embedder and in-memory vector store — the offline
path — so retrieval is deterministic without a model or network.
"""

from __future__ import annotations

from aiplatform.application.knowledge.semantic_retriever import SemanticRetriever
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore

_DOC = KnowledgeDocumentId.generate()


async def _seed(embedder: FakeEmbeddingProvider, store: InMemoryVectorStore) -> None:
    texts = {
        "python programming language tutorial": Metadata.of({"topic": "python"}),
        "banana bread baking recipe": Metadata.of({"topic": "cooking"}),
        "python data science with pandas": Metadata.of({"topic": "python"}),
    }
    vectors = await embedder.embed_documents(list(texts))
    entries = [
        VectorEntry(
            chunk_id=KnowledgeChunkId.generate(),
            document_id=_DOC,
            vector=vector,
            text=text,
            metadata=metadata,
        )
        for (text, metadata), vector in zip(texts.items(), vectors, strict=True)
    ]
    await store.upsert(entries)


def _retriever() -> tuple[SemanticRetriever, FakeEmbeddingProvider, InMemoryVectorStore]:
    embedder = FakeEmbeddingProvider(dimension=256)
    store = InMemoryVectorStore()
    return SemanticRetriever(embedder=embedder, vector_store=store), embedder, store


async def test_retrieves_lexically_relevant_chunks_first() -> None:
    retriever, embedder, store = _retriever()
    await _seed(embedder, store)

    context = await retriever.retrieve("python programming", k=3, filter=MetadataFilter.none())

    assert context.query == "python programming"
    assert not context.is_empty
    # The most similar chunk shares the most words with the query.
    assert "python" in context.chunks[0].text
    # Ordered by descending score.
    scores = [c.score for c in context.chunks]
    assert scores == sorted(scores, reverse=True)


async def test_k_bounds_the_result() -> None:
    retriever, embedder, store = _retriever()
    await _seed(embedder, store)
    context = await retriever.retrieve("python", k=1, filter=MetadataFilter.none())
    assert len(context.chunks) == 1


async def test_metadata_filter_is_applied() -> None:
    retriever, embedder, store = _retriever()
    await _seed(embedder, store)
    context = await retriever.retrieve(
        "recipe", k=5, filter=MetadataFilter(equals=(("topic", "cooking"),))
    )
    assert [c.metadata.get("topic") for c in context.chunks] == ["cooking"]


async def test_empty_store_yields_empty_context() -> None:
    retriever, _, _ = _retriever()
    context = await retriever.retrieve("anything", k=5, filter=MetadataFilter.none())
    assert context.is_empty
    assert context.query == "anything"


async def test_retrieved_chunks_carry_provenance() -> None:
    retriever, embedder, store = _retriever()
    await _seed(embedder, store)
    context = await retriever.retrieve("pandas", k=1, filter=MetadataFilter.none())
    chunk = context.chunks[0]
    assert chunk.document_id == _DOC
    assert isinstance(chunk.chunk_id, KnowledgeChunkId)
    assert chunk.text
