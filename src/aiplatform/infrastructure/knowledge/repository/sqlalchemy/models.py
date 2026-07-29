"""SQLAlchemy models for the knowledge record store (ADR-0016).

Two tables mirroring the ``KnowledgeDocument`` aggregate: ``knowledge_documents``
(root) and ``knowledge_chunks`` (append-only children with explicit ``ordinal``
ordering). Metadata is a portable ``JSON`` column (JSONB on PostgreSQL). These are
kept in their **own** declarative base, separate from the vector table (which uses
a Postgres-only ``vector`` column), so this record store also runs on SQLite for
fast local tests.

The ``metadata`` **column** is exposed under a differently-named attribute because
``metadata`` is reserved on the SQLAlchemy declarative base.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class KnowledgeBase(DeclarativeBase):
    """Declarative base for the knowledge record tables (owns their metadata)."""


class KnowledgeDocumentRow(KnowledgeBase):
    """A row in the ``knowledge_documents`` table (the aggregate root)."""

    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    source: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


class KnowledgeChunkRow(KnowledgeBase):
    """A row in the ``knowledge_chunks`` table (an append-only child)."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
