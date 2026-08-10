"""Run the shared repository contract suite against the SQLAlchemy repository
over an in-memory SQLite engine (M2.5).

This is fast, local, executed evidence that the SQLAlchemy repository — the same
code path used for PostgreSQL — satisfies the *identical* contract suite the
in-memory repository passes. The authoritative PostgreSQL run (ADR-0008) lives in
``test_postgres_repository_contract.py`` and executes against a real database in
CI; SQLite is a developer convenience and is never a production or selectable
backend.

A single shared connection (``StaticPool``) keeps the in-memory database alive
across sessions; a fresh engine per test gives clean isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from repository_contract import ConversationRepositoryContract
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aiplatform.infrastructure.persistence.sqlalchemy.models import Base
from aiplatform.infrastructure.persistence.sqlalchemy.repository import (
    SqlAlchemyConversationRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider


class TestSqliteRepositoryContract(ConversationRepositoryContract):
    """The SQLAlchemy repository must satisfy every repository invariant."""

    @pytest_asyncio.fixture
    async def repository(self) -> AsyncIterator[SqlAlchemyConversationRepository]:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield SqlAlchemyConversationRepository(provider)
        finally:
            await provider.aclose()
