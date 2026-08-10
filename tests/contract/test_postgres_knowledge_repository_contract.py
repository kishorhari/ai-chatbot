"""Run the shared knowledge-repository contract suite over real PostgreSQL (M3.7).

Authoritative: the SQLAlchemy knowledge repository passes the identical suite the
in-memory store passes, against a real database (CI service container). Skipped
locally without ``AIP__TEST_POSTGRES_DSN``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from knowledge_repository_contract import KnowledgeRepositoryContract
from sqlalchemy.ext.asyncio import create_async_engine

from aiplatform.infrastructure.knowledge.repository.sqlalchemy.models import KnowledgeBase
from aiplatform.infrastructure.knowledge.repository.sqlalchemy.repository import (
    SqlAlchemyKnowledgeRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider

_DSN = os.environ.get("AIP__TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not _DSN, reason="AIP__TEST_POSTGRES_DSN not set"),
]


class TestPostgresKnowledgeRepositoryContract(KnowledgeRepositoryContract):
    """The SQLAlchemy knowledge repository must satisfy every invariant on PostgreSQL."""

    @pytest_asyncio.fixture
    async def repository(self) -> AsyncIterator[SqlAlchemyKnowledgeRepository]:
        assert _DSN is not None
        engine = create_async_engine(_DSN)
        async with engine.begin() as connection:
            await connection.run_sync(KnowledgeBase.metadata.drop_all)
            await connection.run_sync(KnowledgeBase.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield SqlAlchemyKnowledgeRepository(provider)
        finally:
            async with engine.begin() as connection:
                await connection.run_sync(KnowledgeBase.metadata.drop_all)
            await provider.aclose()
