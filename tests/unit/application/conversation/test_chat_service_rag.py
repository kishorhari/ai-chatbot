"""ChatService with RAG enabled via a ContextProvider (M3.5).

Proves the single additive seam works end to end: with a KnowledgeContextProvider
wired, retrieved context reaches the generated CompletionRequest (merged into the
single system message); with the default NullContextProvider, it does not — so
RAG-off behaviour is identical to M2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from aiplatform.application.conversation.chat_service import ChatService
from aiplatform.application.conversation.context_window import ContextWindowPolicy
from aiplatform.application.conversation.prompt_assembler import PromptAssembler
from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.context_provider import KnowledgeContextProvider
from aiplatform.application.knowledge.prompt_enricher import PromptEnricher
from aiplatform.application.knowledge.retrieval_service import RetrievalService
from aiplatform.application.knowledge.semantic_retriever import SemanticRetriever
from aiplatform.application.llm.provider_registry import ProviderRegistry
from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk, CompletionResult, TokenUsage
from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore
from aiplatform.infrastructure.persistence.memory.repository import (
    InMemoryConversationRepository,
)
from aiplatform.infrastructure.persistence.memory.transaction import (
    InMemoryTransactionBoundary,
)

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_FACT = "The capital of France is Paris."


class _FixedClock:
    def now(self) -> datetime:
        return _TS


class _CapturingProvider(LLMProvider):
    """Records the request it is asked to complete; returns a canned reply."""

    def __init__(self) -> None:
        self.last_request: CompletionRequest | None = None

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta="", is_final=True)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model="capture",
            supports_streaming=True,
            supports_system_prompt=True,
            reports_token_usage=False,
            max_context_tokens=None,
        )

    async def complete_chat(self, request: CompletionRequest) -> CompletionResult:
        self.last_request = request
        return CompletionResult(text="ack", model="capture", usage=TokenUsage.empty())


class _StaticRegistry(ProviderRegistry):
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @property
    def default_name(self) -> str:
        return "capture"

    def get(self, name: str) -> LLMProvider:
        return self._provider


async def _knowledge_context_provider() -> KnowledgeContextProvider:
    embedder = FakeEmbeddingProvider(dimension=128)
    store = InMemoryVectorStore()
    vector = (await embedder.embed_documents([_FACT]))[0]
    await store.upsert(
        [
            VectorEntry(
                chunk_id=KnowledgeChunkId.generate(),
                document_id=KnowledgeDocumentId.generate(),
                vector=vector,
                text=_FACT,
                metadata=Metadata(),
            )
        ]
    )
    return KnowledgeContextProvider(
        retrieval=RetrievalService(
            SemanticRetriever(embedder=embedder, vector_store=store), min_score=-1.0
        ),
        enricher=PromptEnricher(HeuristicTokenEstimator()),
    )


async def _seed_conversation(repo: InMemoryConversationRepository) -> Conversation:
    conversation = Conversation.start(owner="u", created_at=_TS)
    conversation.append_system("You are helpful.", created_at=_TS)
    await repo.add(conversation)
    return conversation


def _service(
    provider: _CapturingProvider,
    repo: InMemoryConversationRepository,
    context_provider: KnowledgeContextProvider | None,
) -> ChatService:
    return ChatService(
        repository=repo,
        clock=_FixedClock(),
        provider_registry=_StaticRegistry(provider),
        context_window=ContextWindowPolicy(HeuristicTokenEstimator()),
        prompt_assembler=PromptAssembler(),
        transactions=InMemoryTransactionBoundary(),
        context_provider=context_provider,
    )


def _system_content(request: CompletionRequest) -> str:
    systems = [m for m in request.messages if m.role is Role.SYSTEM]
    assert len(systems) == 1  # single leading system message
    assert request.messages[0].role is Role.SYSTEM
    return systems[0].content


async def test_rag_enabled_injects_retrieved_context_into_the_request() -> None:
    provider = _CapturingProvider()
    repo = InMemoryConversationRepository()
    conversation = await _seed_conversation(repo)
    service = _service(provider, repo, await _knowledge_context_provider())

    await service.send_message(conversation.id, "What is the capital of France?")

    assert provider.last_request is not None
    system = _system_content(provider.last_request)
    assert "You are helpful." in system  # base system prompt retained
    assert "Paris" in system  # retrieved context injected


async def test_rag_disabled_by_default_injects_nothing() -> None:
    provider = _CapturingProvider()
    repo = InMemoryConversationRepository()
    conversation = await _seed_conversation(repo)
    service = _service(provider, repo, None)  # NullContextProvider default

    await service.send_message(conversation.id, "What is the capital of France?")

    assert provider.last_request is not None
    system = _system_content(provider.last_request)
    assert system == "You are helpful."  # unchanged — no context
    assert "Paris" not in system
