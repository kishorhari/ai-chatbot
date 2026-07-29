"""Unit tests for ConversationService (M2.4).

Exercised against the real in-memory repository and transaction boundary with a
fixed clock — no HTTP, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.application.conversation.conversation_service import ConversationService
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import ConversationNotFoundError
from aiplatform.domain.llm.messages import Role
from aiplatform.infrastructure.persistence.memory.repository import (
    InMemoryConversationRepository,
)
from aiplatform.infrastructure.persistence.memory.transaction import (
    InMemoryTransactionBoundary,
)

_TS = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _TS


def _service() -> tuple[ConversationService, InMemoryConversationRepository]:
    repo = InMemoryConversationRepository()
    service = ConversationService(
        repository=repo, clock=_FixedClock(), transactions=InMemoryTransactionBoundary()
    )
    return service, repo


async def test_start_conversation_persists_and_returns_view() -> None:
    service, repo = _service()
    view = await service.start_conversation(owner="alice")
    assert view.owner == "alice"
    assert view.created_at == _TS
    assert view.messages == ()
    # Persisted through the repository.
    stored = await repo.get(view.id)
    assert stored.owner == "alice"


async def test_start_conversation_with_system_prompt_seeds_message() -> None:
    service, _ = _service()
    view = await service.start_conversation(owner="alice", system_prompt="Be nice.")
    assert len(view.messages) == 1
    assert view.messages[0].role is Role.SYSTEM
    assert view.messages[0].content == "Be nice."
    assert view.messages[0].created_at == _TS


async def test_get_conversation_returns_view() -> None:
    service, _ = _service()
    created = await service.start_conversation(owner="bob", system_prompt="Sys")
    fetched = await service.get_conversation(created.id)
    assert fetched.id == created.id
    assert fetched.owner == "bob"
    assert fetched.messages[0].content == "Sys"


async def test_get_unknown_raises_not_found() -> None:
    service, _ = _service()
    with pytest.raises(ConversationNotFoundError):
        await service.get_conversation(ConversationId.generate())
