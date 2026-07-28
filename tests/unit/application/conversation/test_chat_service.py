"""Unit tests for ChatService orchestration (M2.3).

The service is exercised against *real* collaborators where they are cheap and
deterministic — the in-memory repository, in-memory transaction boundary, real
context-window policy, and real prompt assembler — with only the provider stubbed
(to control output and inject failures) and the clock fixed (for determinism).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from aiplatform.application.conversation.chat_service import ChatResult, ChatService
from aiplatform.application.conversation.context_window import ContextWindowPolicy
from aiplatform.application.conversation.prompt_assembler import PromptAssembler
from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.llm.provider_registry import ProviderRegistry
from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import ConversationNotFoundError, RepositoryError
from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.errors import LLMTimeoutError
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk, FinishReason, TokenUsage
from aiplatform.infrastructure.persistence.memory.repository import InMemoryConversationRepository
from aiplatform.infrastructure.persistence.memory.transaction import InMemoryTransactionBoundary

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class _StubProvider(LLMProvider):
    """Returns a canned reply, or raises a pre-set error, and records its request."""

    def __init__(
        self,
        *,
        reply: str = "echo",
        usage: TokenUsage | None = None,
        error: Exception | None = None,
        max_context_tokens: int | None = None,
    ) -> None:
        self._reply = reply
        self._usage = usage if usage is not None else TokenUsage.empty()
        self._error = error
        self._caps = ProviderCapabilities(
            model="stub-model",
            supports_streaming=True,
            supports_system_prompt=True,
            reports_token_usage=True,
            max_context_tokens=max_context_tokens,
        )
        self.received_request: CompletionRequest | None = None

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        if self._error is not None:
            raise self._error
        self.received_request = request
        yield CompletionChunk(delta=self._reply)
        yield CompletionChunk(
            delta="", is_final=True, finish_reason=FinishReason.STOP, usage=self._usage
        )

    def capabilities(self) -> ProviderCapabilities:
        return self._caps


class _StubRegistry(ProviderRegistry):
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @property
    def default_name(self) -> str:
        return "stub"

    def get(self, name: str) -> LLMProvider:
        return self._provider


class _FixedClock:
    """Yields the supplied timestamps in order, clamping at the last."""

    def __init__(self, *times: datetime) -> None:
        self._times = list(times) or [_T0]
        self._index = 0

    def now(self) -> datetime:
        value = self._times[min(self._index, len(self._times) - 1)]
        self._index += 1
        return value


def _service(
    provider: LLMProvider,
    *,
    repository: InMemoryConversationRepository,
    clock: _FixedClock | None = None,
) -> ChatService:
    return ChatService(
        repository=repository,
        clock=clock or _FixedClock(_T0),
        provider_registry=_StubRegistry(provider),
        context_window=ContextWindowPolicy(HeuristicTokenEstimator()),
        prompt_assembler=PromptAssembler(),
        transactions=InMemoryTransactionBoundary(),
    )


async def _seed(
    repository: InMemoryConversationRepository, *, with_system: bool = False
) -> ConversationId:
    convo = Conversation.start(owner="alice", created_at=_T0)
    if with_system:
        convo.append_system("You are helpful.", created_at=_T0)
    await repository.add(convo)
    return convo.id


async def test_appends_user_and_assistant_and_persists() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo)
    provider = _StubProvider(
        reply="hi there", usage=TokenUsage(prompt_tokens=3, completion_tokens=2)
    )

    result = await _service(provider, repository=repo).send_message(cid, "hello")

    assert isinstance(result, ChatResult)
    assert result.content == "hi there"
    assert result.model == "stub-model"
    assert result.usage.total_tokens == 5
    assert result.finish_reason is FinishReason.STOP

    stored = await repo.get(cid)
    assert [(m.role, m.content) for m in stored.messages] == [
        (Role.USER, "hello"),
        (Role.ASSISTANT, "hi there"),
    ]
    assert result.message_id == stored.messages[-1].id


async def test_model_override_reaches_the_request() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo)
    provider = _StubProvider(reply="x")
    await _service(provider, repository=repo).send_message(cid, "hello", model="llama3")
    assert provider.received_request is not None
    assert provider.received_request.model == "llama3"


async def test_windowed_history_is_assembled_into_the_request() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo, with_system=True)
    provider = _StubProvider(reply="x")
    await _service(provider, repository=repo).send_message(cid, "hello")
    request = provider.received_request
    assert request is not None
    assert [(m.role, m.content) for m in request.messages] == [
        (Role.SYSTEM, "You are helpful."),
        (Role.USER, "hello"),
    ]


async def test_clock_supplies_both_message_timestamps() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo)
    t_user, t_assistant = _T0, _T0 + timedelta(seconds=5)
    provider = _StubProvider(reply="x")
    result = await _service(
        provider, repository=repo, clock=_FixedClock(t_user, t_assistant)
    ).send_message(cid, "hello")
    stored = await repo.get(cid)
    assert stored.messages[0].created_at == t_user
    assert stored.messages[1].created_at == t_assistant
    assert result.created_at == t_assistant


async def test_conversation_not_found_propagates_unwrapped() -> None:
    repo = InMemoryConversationRepository()
    service = _service(_StubProvider(), repository=repo)
    with pytest.raises(ConversationNotFoundError):
        await service.send_message(ConversationId.generate(), "hello")


async def test_provider_error_propagates_and_persists_nothing() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo)
    provider = _StubProvider(error=LLMTimeoutError("timed out"))

    with pytest.raises(LLMTimeoutError):
        await _service(provider, repository=repo).send_message(cid, "hello")

    stored = await repo.get(cid)
    assert stored.message_count == 0  # user message was appended in memory only, never saved


async def test_repository_save_failure_propagates_and_leaves_no_partial_write() -> None:
    class _FailingSaveRepo(InMemoryConversationRepository):
        async def save(self, conversation: Conversation) -> None:
            raise RepositoryError("save failed")

    repo = _FailingSaveRepo()
    cid = await _seed(repo)
    provider = _StubProvider(reply="x")

    with pytest.raises(RepositoryError):
        await _service(provider, repository=repo).send_message(cid, "hello")

    stored = await repo.get(cid)
    assert stored.message_count == 0  # rolled back / never committed


async def test_service_handles_sequential_turns() -> None:
    repo = InMemoryConversationRepository()
    cid = await _seed(repo)
    service = _service(_StubProvider(reply="ok"), repository=repo)

    await service.send_message(cid, "first")
    await service.send_message(cid, "second")

    stored = await repo.get(cid)
    assert [(m.role, m.content) for m in stored.messages] == [
        (Role.USER, "first"),
        (Role.ASSISTANT, "ok"),
        (Role.USER, "second"),
        (Role.ASSISTANT, "ok"),
    ]
