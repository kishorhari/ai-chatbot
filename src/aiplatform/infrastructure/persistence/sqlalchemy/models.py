"""SQLAlchemy ORM models for the conversation aggregate (ADR-0008).

Two tables mirroring the shallow aggregate (ADR-0007): ``conversations`` (the
root) and ``messages`` (append-only children). These are *persistence* models,
deliberately separate from the domain aggregate — the mapping layer translates
between them. Domain-generated UUIDs are the primary keys (identity exists before
persistence), ordering is the explicit ``sequence`` column, and a unique
constraint on ``(conversation_id, sequence)`` enforces contiguous, non-colliding
ordering at the database level.

Relationships are intentionally omitted: the repository issues explicit,
sequence-ordered queries to stay clear of async lazy-loading.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for the persistence models (owns the schema metadata)."""


class ConversationRow(Base):
    """A row in the ``conversations`` table (the aggregate root)."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageRow(Base):
    """A row in the ``messages`` table (an append-only aggregate child)."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_messages_conversation_sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
