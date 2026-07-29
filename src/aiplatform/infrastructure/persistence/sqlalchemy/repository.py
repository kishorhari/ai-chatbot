"""SQLAlchemy ``ConversationRepository`` implementation (ADR-0008).

Speaks only in domain aggregates (via the mapping layer); callers never see a
session, ORM row, or SQL. Snapshot independence — the same contract the in-memory
repository honours — is intrinsic here: every :meth:`get` rebuilds a fresh
aggregate from rows, so a mutation to a loaded aggregate touches storage only when
it is passed back to :meth:`save`.

Messages are append-only (ADR-0007): :meth:`save` inserts only the messages beyond
those already stored, so an unsaved mutation never leaks and a re-save is a no-op.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import (
    ConversationAlreadyExistsError,
    ConversationNotFoundError,
    ConversationRepository,
)

from .mapping import conversation_to_row, message_to_row, rows_to_conversation
from .models import ConversationRow, MessageRow
from .session import SessionProvider


class SqlAlchemyConversationRepository(ConversationRepository):
    """Persists conversations to a relational database via SQLAlchemy."""

    def __init__(self, provider: SessionProvider) -> None:
        """Store the session provider (shared with the transaction boundary)."""
        self._provider = provider

    async def add(self, conversation: Conversation) -> None:
        """Insert a new conversation and all its messages."""
        async with self._provider.session() as session:
            if await self._exists(session, conversation.id):
                raise ConversationAlreadyExistsError(conversation.id)
            session.add(conversation_to_row(conversation))
            for message in conversation.messages:
                session.add(message_to_row(conversation.id, message))

    async def get(self, conversation_id: ConversationId) -> Conversation:
        """Load a conversation and its sequence-ordered messages."""
        async with self._provider.session() as session:
            root = await session.get(ConversationRow, conversation_id.value)
            if root is None:
                raise ConversationNotFoundError(conversation_id)
            rows = (
                (
                    await session.execute(
                        select(MessageRow)
                        .where(MessageRow.conversation_id == conversation_id.value)
                        .order_by(MessageRow.sequence)
                    )
                )
                .scalars()
                .all()
            )
            return rows_to_conversation(root, rows)

    async def save(self, conversation: Conversation) -> None:
        """Persist newly-appended messages of an existing conversation."""
        async with self._provider.session() as session:
            if not await self._exists(session, conversation.id):
                raise ConversationNotFoundError(conversation.id)
            stored = await self._message_count(session, conversation.id)
            for message in conversation.messages[stored:]:
                session.add(message_to_row(conversation.id, message))

    @staticmethod
    async def _exists(session: AsyncSession, conversation_id: ConversationId) -> bool:
        return await session.get(ConversationRow, conversation_id.value) is not None

    @staticmethod
    async def _message_count(session: AsyncSession, conversation_id: ConversationId) -> int:
        count = (
            await session.execute(
                select(func.count())
                .select_from(MessageRow)
                .where(MessageRow.conversation_id == conversation_id.value)
            )
        ).scalar_one()
        return int(count)
