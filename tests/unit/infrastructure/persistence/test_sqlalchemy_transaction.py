"""Transaction-boundary behaviour of the SQLAlchemy backend (M2.5).

The repository contract suite exercises the repository directly; these tests
exercise the *transaction boundary* and session sharing (ADR-0008) over SQLite —
in particular **real rollback**, which the in-memory pass-through cannot
demonstrate. This is the mechanism ChatService/ConversationService rely on to make
a chat turn atomic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ports import ConversationNotFoundError
from aiplatform.infrastructure.persistence.sqlalchemy.models import Base
from aiplatform.infrastructure.persistence.sqlalchemy.repository import (
    SqlAlchemyConversationRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider
from aiplatform.infrastructure.persistence.sqlalchemy.transaction import (
    SqlAlchemyTransactionBoundary,
)

_TS = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


class _Persistence:
    def __init__(self, provider: SessionProvider) -> None:
        self.provider = provider
        self.repository = SqlAlchemyConversationRepository(provider)
        self.transactions = SqlAlchemyTransactionBoundary(provider)


@pytest_asyncio.fixture
async def persistence() -> AsyncIterator[_Persistence]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    provider = SessionProvider(engine)
    try:
        yield _Persistence(provider)
    finally:
        await provider.aclose()


async def test_atomic_commit_persists(persistence: _Persistence) -> None:
    convo = Conversation.start(owner="alice", created_at=_TS)
    async with persistence.transactions.atomic():
        await persistence.repository.add(convo)

    loaded = await persistence.repository.get(convo.id)
    assert loaded.id == convo.id


async def test_atomic_rollback_leaves_no_write(persistence: _Persistence) -> None:
    """A failure inside atomic() rolls the whole scope back (real transaction)."""
    convo = Conversation.start(owner="alice", created_at=_TS)
    with pytest.raises(RuntimeError, match="boom"):
        async with persistence.transactions.atomic():
            await persistence.repository.add(convo)
            raise RuntimeError("boom")  # mid-scope failure

    with pytest.raises(ConversationNotFoundError):
        await persistence.repository.get(convo.id)  # nothing was committed


async def test_atomic_scope_shares_one_session_for_multiple_writes(
    persistence: _Persistence,
) -> None:
    convo = Conversation.start(owner="alice", created_at=_TS)
    convo.append_user("hello", created_at=_TS)
    async with persistence.transactions.atomic():
        await persistence.repository.add(convo)

    loaded = await persistence.repository.get(convo.id)
    loaded.append_assistant("hi", created_at=_TS)
    async with persistence.transactions.atomic():
        await persistence.repository.save(loaded)

    reloaded = await persistence.repository.get(convo.id)
    assert reloaded.message_count == 2
    assert [m.content for m in reloaded.messages] == ["hello", "hi"]
