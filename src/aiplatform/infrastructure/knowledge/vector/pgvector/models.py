"""SQLAlchemy model for the pgvector store (ADR-0013).

A single ``knowledge_vectors`` table keyed by chunk id, carrying the embedding
(a dimensionless pgvector ``vector`` column, accepting whatever dimension the
embedding model produces) plus the retrieval payload (text + metadata). It lives
in its own declarative base — separate from the SQLite-portable record store —
because the ``vector`` type is PostgreSQL-only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class VectorBase(DeclarativeBase):
    """Declarative base for the pgvector table (owns its metadata)."""


class KnowledgeVectorRow(VectorBase):
    """A row in the ``knowledge_vectors`` table (a chunk's indexed embedding)."""

    __tablename__ = "knowledge_vectors"

    chunk_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(Uuid(), nullable=False, index=True)
    embedding: Mapped[Any] = mapped_column(Vector(), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
