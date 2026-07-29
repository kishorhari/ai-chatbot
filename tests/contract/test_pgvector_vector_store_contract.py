"""Run the shared vector-store contract suite against pgvector (M3.7).

**Authoritative proof of the vector-search swap (ADR-0013):** the pgvector store
passes the *identical* ``VectorStoreContract`` the in-memory store passes, against
a real PostgreSQL + pgvector database (CI service container).

Skipped unless the ``pgvector`` package is installed *and* ``AIP__TEST_POSTGRES_DSN``
is set — so it neither imports nor runs on a driverless dev box; only CI exercises
it (SQLite has no vector type, so there is no local fallback for this store).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

pytest.importorskip("pgvector.sqlalchemy")

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from vector_store_contract import VectorStoreContract

from aiplatform.infrastructure.knowledge.vector.pgvector.models import (
    VectorBase,
)
from aiplatform.infrastructure.knowledge.vector.pgvector.store import (
    PgVectorStore,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import (
    SessionProvider,
)

_DSN = os.environ.get("AIP__TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not _DSN, reason="AIP__TEST_POSTGRES_DSN not set"),
]


class TestPgVectorStoreContract(VectorStoreContract):
    """PgVectorStore must satisfy every VectorStore invariant on real pgvector."""

    @pytest_asyncio.fixture
    async def store(self) -> AsyncIterator[PgVectorStore]:
        assert _DSN is not None
        engine = create_async_engine(_DSN)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(VectorBase.metadata.drop_all)
            await connection.run_sync(VectorBase.metadata.create_all)
        provider = SessionProvider(engine)
        try:
            yield PgVectorStore(provider)
        finally:
            async with engine.begin() as connection:
                await connection.run_sync(VectorBase.metadata.drop_all)
            await provider.aclose()
