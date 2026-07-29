"""Run the shared repository contract suite against a real PostgreSQL (M2.5).

**This is the authoritative equivalence proof (ADR-0008):** the SQLAlchemy
repository passes the *identical* suite the in-memory repository passes, against a
real database. It runs in CI against a PostgreSQL service container and is skipped
locally when ``AIP__TEST_POSTGRES_DSN`` is unset (and requires the ``postgres``
extra / ``asyncpg`` to be installed).

The schema is created and dropped per test for clean isolation.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from repository_contract import ConversationRepositoryContract
from sqlalchemy.ext.asyncio import create_async_engine

from aiplatform.infrastructure.persistence.sqlalchemy.models import Base
from aiplatform.infrastructure.persistence.sqlalchemy.repository import (
    SqlAlchemyConversationRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider

_DSN = os.environ.get("AIP__TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not _DSN, reason="AIP__TEST_POSTGRES_DSN not set"),
]


class TestPostgresRepositoryContract(ConversationRepositoryContract):
    """The SQLAlchemy repository must satisfy every invariant on PostgreSQL."""

    @pytest_asyncio.fixture
    async def repository(self) -> AsyncIterator[SqlAlchemyConversationRepository]:
        assert _DSN is not None  # guarded by skipif
        engine = create_async_engine(_DSN)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield SqlAlchemyConversationRepository(provider)
        finally:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
            await provider.aclose()
