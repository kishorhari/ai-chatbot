"""Run the shared knowledge-repository contract suite over SQLite (M3.7).

Fast, local executed evidence that the SQLAlchemy knowledge repository — the same
code path used for PostgreSQL — satisfies the identical suite the in-memory store
passes. The authoritative PostgreSQL run is in
``test_postgres_knowledge_repository_contract.py`` (CI).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from knowledge_repository_contract import KnowledgeRepositoryContract
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aiplatform.infrastructure.knowledge.repository.sqlalchemy.models import KnowledgeBase
from aiplatform.infrastructure.knowledge.repository.sqlalchemy.repository import (
    SqlAlchemyKnowledgeRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider


class TestSqliteKnowledgeRepositoryContract(KnowledgeRepositoryContract):
    """The SQLAlchemy knowledge repository must satisfy every invariant."""

    @pytest_asyncio.fixture
    async def repository(self) -> AsyncIterator[SqlAlchemyKnowledgeRepository]:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # SQLite does not enforce foreign keys unless asked per connection. Enable it
        # so this local suite exercises the same FK behaviour PostgreSQL enforces in
        # CI — otherwise a document/chunk insert-ordering fault passes here and only
        # surfaces in CI (exactly what happened before the M3.9 hardening fix).
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        async with engine.begin() as connection:
            await connection.run_sync(KnowledgeBase.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield SqlAlchemyKnowledgeRepository(provider)
        finally:
            await provider.aclose()
