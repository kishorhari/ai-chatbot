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

from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry
from aiplatform.domain.knowledge.vectors import EmbeddingVector
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

    async def test_metadata_round_trips_and_updates_on_conflict(self, store: PgVectorStore) -> None:
        # Regression for the upsert "metadata" column-name collision (M3.9): the
        # ``metadata`` column is written on insert AND on the ON CONFLICT DO UPDATE
        # path. This exercises the real upsert twice for one chunk id — first insert,
        # then conflict-update — and proves the metadata mapping survives both.
        chunk_id = KnowledgeChunkId.generate()
        document_id = KnowledgeDocumentId.generate()

        def _entry(title: str, lang: str) -> VectorEntry:
            return VectorEntry(
                chunk_id=chunk_id,
                document_id=document_id,
                vector=EmbeddingVector((1.0, 0.0)),
                text="payload",
                metadata=Metadata.of({"title": title, "lang": lang}),
            )

        await store.upsert([_entry("first", "en")])
        inserted = await store.search(
            EmbeddingVector((1.0, 0.0)), k=1, filter=MetadataFilter.none()
        )
        assert inserted[0].metadata.get("title") == "first"
        assert inserted[0].metadata.get("lang") == "en"

        # Same chunk id → ON CONFLICT DO UPDATE must overwrite the metadata column.
        await store.upsert([_entry("second", "fr")])
        updated = await store.search(
            EmbeddingVector((1.0, 0.0)), k=10, filter=MetadataFilter.none()
        )
        assert len(updated) == 1  # still one row (updated, not duplicated)
        assert updated[0].metadata.get("title") == "second"
        assert updated[0].metadata.get("lang") == "fr"
        # And the updated metadata is filterable, proving the column really changed.
        filtered = await store.search(
            EmbeddingVector((1.0, 0.0)), k=10, filter=MetadataFilter(equals=(("lang", "fr"),))
        )
        assert len(filtered) == 1
