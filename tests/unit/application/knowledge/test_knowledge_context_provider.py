"""Unit tests for KnowledgeContextProvider composition (M3.5).

Exercised end to end over the offline path (fake embedder + in-memory vector
store) — retrieval + enrichment with no model or network.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.context_provider import KnowledgeContextProvider
from aiplatform.application.knowledge.prompt_enricher import PromptEnricher
from aiplatform.application.knowledge.retrieval_service import RetrievalService
from aiplatform.application.knowledge.semantic_retriever import SemanticRetriever
from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.domain.llm.messages import Role
from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _user(text: str) -> Message:
    return Message(
        id=MessageId.generate(), role=Role.USER, content=text, sequence=0, created_at=_TS
    )


async def _provider() -> KnowledgeContextProvider:
    embedder = FakeEmbeddingProvider(dimension=128)
    store = InMemoryVectorStore()
    text = "The capital of France is Paris."
    vector = (await embedder.embed_documents([text]))[0]
    await store.upsert(
        [
            VectorEntry(
                chunk_id=KnowledgeChunkId.generate(),
                document_id=KnowledgeDocumentId.generate(),
                vector=vector,
                text=text,
                metadata=Metadata.of({"topic": "geography"}),
            )
        ]
    )
    retrieval = RetrievalService(
        SemanticRetriever(embedder=embedder, vector_store=store), min_score=-1.0
    )
    return KnowledgeContextProvider(
        retrieval=retrieval, enricher=PromptEnricher(HeuristicTokenEstimator())
    )


async def test_enriches_messages_with_retrieved_context() -> None:
    provider = await _provider()
    messages = (_user("What is the capital of France?"),)
    result = await provider.enrich(messages, query="capital of France", max_context_tokens=None)
    assert result[0].role is Role.SYSTEM
    assert "Paris" in result[0].content
    assert result[-1].content == "What is the capital of France?"


async def test_no_relevant_knowledge_leaves_messages_effectively_unchanged() -> None:
    # A high threshold filters out the only (lexically unrelated) chunk.
    embedder = FakeEmbeddingProvider(dimension=128)
    store = InMemoryVectorStore()
    vector = (await embedder.embed_documents(["completely unrelated content"]))[0]
    await store.upsert(
        [
            VectorEntry(
                chunk_id=KnowledgeChunkId.generate(),
                document_id=KnowledgeDocumentId.generate(),
                vector=vector,
                text="completely unrelated content",
                metadata=Metadata(),
            )
        ]
    )
    provider = KnowledgeContextProvider(
        retrieval=RetrievalService(
            SemanticRetriever(embedder=embedder, vector_store=store), min_score=0.99
        ),
        enricher=PromptEnricher(HeuristicTokenEstimator()),
    )
    messages = (_user("quantum chromodynamics"),)
    result = await provider.enrich(
        messages, query="quantum chromodynamics", max_context_tokens=None
    )
    assert result == messages  # nothing passed the threshold → no enrichment
