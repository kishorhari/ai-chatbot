"""Unit tests for the domain <-> ORM mapping (M2.5) — pure, no database."""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage
from aiplatform.infrastructure.persistence.sqlalchemy import mapping
from aiplatform.infrastructure.persistence.sqlalchemy.models import MessageRow

_TS = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _conversation() -> Conversation:
    convo = Conversation.start(owner="alice", created_at=_TS)
    convo.append_system("You are helpful.", created_at=_TS)
    convo.append_user("Hello", created_at=_TS)
    convo.append_assistant(
        "Hi", created_at=_TS, usage=TokenUsage(prompt_tokens=3, completion_tokens=2)
    )
    return convo


def test_round_trip_preserves_aggregate() -> None:
    original = _conversation()
    conv_row = mapping.conversation_to_row(original)
    msg_rows = [mapping.message_to_row(original.id, m) for m in original.messages]

    rebuilt = mapping.rows_to_conversation(conv_row, msg_rows)

    assert rebuilt.id == original.id
    assert rebuilt.owner == original.owner
    assert rebuilt.created_at == original.created_at
    assert rebuilt.message_count == 3
    for got, expected in zip(rebuilt.messages, original.messages, strict=True):
        assert got.id == expected.id
        assert got.role == expected.role
        assert got.content == expected.content
        assert got.sequence == expected.sequence
        assert got.created_at == expected.created_at
        assert got.usage == expected.usage


def test_message_row_records_usage_columns() -> None:
    convo = _conversation()
    assistant = convo.messages[-1]
    row = mapping.message_to_row(convo.id, assistant)
    assert row.prompt_tokens == 3
    assert row.completion_tokens == 2
    assert row.role == Role.ASSISTANT.value
    assert row.sequence == 2


def test_message_without_usage_maps_to_null_columns() -> None:
    convo = _conversation()
    user = convo.messages[1]
    row = mapping.message_to_row(convo.id, user)
    assert row.prompt_tokens is None
    assert row.completion_tokens is None


def test_naive_stored_timestamp_is_normalised_to_utc() -> None:
    """Engines returning naive datetimes (e.g. SQLite) are re-attached UTC."""
    row = MessageRow(
        id=_conversation().messages[0].id.value,
        conversation_id=_conversation().id.value,
        role="user",
        content="hi",
        sequence=0,
        created_at=datetime(2026, 7, 10, 12, 0, 0),  # naive
        prompt_tokens=None,
        completion_tokens=None,
    )
    rebuilt = mapping._row_to_message(row)
    assert rebuilt.created_at.tzinfo is not None
    assert rebuilt.created_at == _TS
