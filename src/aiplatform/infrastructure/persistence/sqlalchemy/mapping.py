"""Pure translation between the conversation aggregate and ORM rows (ADR-0008).

The single place domain ↔ SQLAlchemy row conversion happens — the persistence
analogue of ``ollama/mapping.py`` (ADR-0002). No session, no I/O: it only builds
rows from a domain aggregate and rebuilds an aggregate from rows via
:meth:`Conversation.reconstitute`, which re-validates every invariant so stored
data can never re-enter the domain malformed.

Timestamps are normalised to timezone-aware UTC on the way out. PostgreSQL
``timestamptz`` returns aware datetimes; some engines (e.g. SQLite) return naive
ones — the domain rejects naive timestamps, so we re-attach UTC, which we always
store.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId, MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

from .models import ConversationRow, MessageRow


def conversation_to_row(conversation: Conversation) -> ConversationRow:
    """Build the root row from a conversation aggregate."""
    return ConversationRow(
        id=conversation.id.value,
        owner=conversation.owner,
        created_at=conversation.created_at,
    )


def message_to_row(conversation_id: ConversationId, message: Message) -> MessageRow:
    """Build a message row belonging to ``conversation_id``."""
    return MessageRow(
        id=message.id.value,
        conversation_id=conversation_id.value,
        role=message.role.value,
        content=message.content,
        sequence=message.sequence,
        created_at=message.created_at,
        prompt_tokens=message.usage.prompt_tokens if message.usage is not None else None,
        completion_tokens=message.usage.completion_tokens if message.usage is not None else None,
    )


def rows_to_conversation(
    conversation: ConversationRow, messages: Sequence[MessageRow]
) -> Conversation:
    """Rebuild an aggregate from its root row and ordered message rows.

    ``messages`` must be ordered by ``sequence``. Invariants are re-validated by
    :meth:`Conversation.reconstitute`.
    """
    domain_messages = [_row_to_message(row) for row in messages]
    return Conversation.reconstitute(
        conversation_id=ConversationId(conversation.id),
        owner=conversation.owner,
        created_at=_ensure_utc(conversation.created_at),
        messages=domain_messages,
    )


def _row_to_message(row: MessageRow) -> Message:
    """Rebuild a domain message from its row."""
    return Message(
        id=MessageId(row.id),
        role=Role(row.role),
        content=row.content,
        sequence=row.sequence,
        created_at=_ensure_utc(row.created_at),
        usage=_usage(row.prompt_tokens, row.completion_tokens),
    )


def _usage(prompt_tokens: int | None, completion_tokens: int | None) -> TokenUsage | None:
    """Rebuild token usage, or ``None`` when the row recorded no usage."""
    if prompt_tokens is None and completion_tokens is None:
        return None
    return TokenUsage(prompt_tokens=prompt_tokens or 0, completion_tokens=completion_tokens or 0)


def _ensure_utc(value: datetime) -> datetime:
    """Normalise a stored timestamp to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
