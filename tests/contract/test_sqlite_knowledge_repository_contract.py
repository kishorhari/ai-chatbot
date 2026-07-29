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
        async with engine.begin() as connection:
            await connection.run_sync(KnowledgeBase.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield SqlAlchemyKnowledgeRepository(provider)
        finally:
            await provider.aclose()
