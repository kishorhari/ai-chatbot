"""PgVectorStore — similarity search over pgvector (ADR-0013).

Implements ``VectorStore`` on top of the pgvector extension, reusing the M2
``SessionProvider``. Cosine is the metric (the port contract): pgvector's cosine
*distance* (``<=>``) is ``1 - cosine_similarity``, so results are ordered by
ascending distance and the reported ``score`` is ``1 - distance``.

The store tracks the established dimension in memory (like the in-memory store) to
raise ``DimensionMismatchError`` before a mismatched query reaches the database —
the dimensionless column would otherwise let pgvector raise a raw dimension error.
The metadata filter is applied in Python over distance-ordered rows (portable and
consistent with the in-memory store); ANN indexing is deferred (ADR-0013).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aiplatform.domain.knowledge.errors import DimensionMismatchError
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry, VectorMatch, VectorStore
from aiplatform.domain.knowledge.vectors import EmbeddingVector
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider

from .models import KnowledgeVectorRow


class PgVectorStore(VectorStore):
    """Vector upsert/search/delete over a pgvector ``knowledge_vectors`` table."""

    def __init__(self, provider: SessionProvider) -> None:
        """Store the shared session provider; dimension is learned on first use."""
        self._provider = provider
        self._dimension: int | None = None

    async def upsert(self, entries: Sequence[VectorEntry]) -> None:
        """Insert or replace entries by chunk id (dimension-validated)."""
        rows = []
        for entry in entries:
            self._ensure_dimension(entry.vector.dimension)
            rows.append(
                {
                    "chunk_id": entry.chunk_id.value,
                    "document_id": entry.document_id.value,
                    "embedding": list(entry.vector.values),
                    "text": entry.text,
                    "metadata": entry.metadata.as_dict(),
                }
            )
        if not rows:
            return
        async with self._provider.session() as session:
            # Build the upsert against the Core table (not the ORM entity) so the
            # keys are resolved as column names. The "metadata" column collides with
            # SQLAlchemy's reserved declarative ``.metadata`` attribute (the Python
            # attribute is ``chunk_metadata``), which an ORM-entity insert would
            # misresolve; the Core table keys by column name and sidesteps that.
            table = cast(Table, KnowledgeVectorRow.__table__)
            statement = pg_insert(table).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.chunk_id],
                set_={
                    column: statement.excluded[column]
                    for column in ("document_id", "embedding", "text", "metadata")
                },
            )
            await session.execute(statement)

    async def search(
        self, query: EmbeddingVector, *, k: int, filter: MetadataFilter
    ) -> list[VectorMatch]:
        """Return the ``k`` most cosine-similar entries matching ``filter``."""
        if self._dimension is not None and query.dimension != self._dimension:
            raise DimensionMismatchError(expected=self._dimension, actual=query.dimension)
        if k <= 0:
            return []
        distance = KnowledgeVectorRow.embedding.cosine_distance(list(query.values))
        async with self._provider.session() as session:
            rows = await session.execute(
                select(KnowledgeVectorRow, distance.label("distance")).order_by(distance)
            )
            matches: list[VectorMatch] = []
            for row, dist in rows:
                metadata = Metadata.of(row.chunk_metadata)
                if not filter.matches(metadata):
                    continue
                matches.append(
                    VectorMatch(
                        chunk_id=KnowledgeChunkId(row.chunk_id),
                        document_id=KnowledgeDocumentId(row.document_id),
                        text=row.text,
                        metadata=metadata,
                        score=1.0 - float(dist),
                    )
                )
                if len(matches) >= k:
                    break
            return matches

    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Remove all vectors belonging to ``document_id`` (idempotent)."""
        from sqlalchemy import delete as sql_delete

        async with self._provider.session() as session:
            await session.execute(
                sql_delete(KnowledgeVectorRow).where(
                    KnowledgeVectorRow.document_id == document_id.value
                )
            )

    def _ensure_dimension(self, dimension: int) -> None:
        """Establish the store dimension on first use; reject mismatches after."""
        if self._dimension is None:
            self._dimension = dimension
        elif dimension != self._dimension:
            raise DimensionMismatchError(expected=self._dimension, actual=dimension)
