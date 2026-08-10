"""Unit tests for the Message entity (M2.0)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

_WHEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _message(**overrides: object) -> Message:
    kwargs: dict[str, object] = {
        "id": MessageId.generate(),
        "role": Role.USER,
        "content": "hello",
        "sequence": 0,
        "created_at": _WHEN,
    }
    kwargs.update(overrides)
    return Message(**kwargs)  # type: ignore[arg-type]


def test_valid_message_construction() -> None:
    message = _message(usage=TokenUsage(prompt_tokens=1, completion_tokens=2))
    assert message.role is Role.USER
    assert message.content == "hello"
    assert message.sequence == 0
    assert message.usage is not None
    assert message.usage.total_tokens == 3


def test_usage_is_optional() -> None:
    assert _message().usage is None


def test_empty_content_is_rejected() -> None:
    with pytest.raises(ValueError, match="content must be non-empty"):
        _message(content="")


def test_negative_sequence_is_rejected() -> None:
    with pytest.raises(ValueError, match="sequence must be non-negative"):
        _message(sequence=-1)


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be timezone-aware"):
        _message(created_at=datetime(2026, 1, 1, 12, 0))  # intentionally naive


def test_non_utc_timezone_is_accepted() -> None:
    plus_two = timezone(timedelta(hours=2))
    message = _message(created_at=datetime(2026, 1, 1, tzinfo=plus_two))
    assert message.created_at.tzinfo is not None


def test_message_is_immutable() -> None:
    message = _message()
    with pytest.raises(AttributeError):
        message.content = "changed"  # type: ignore[misc]


def test_message_value_equality() -> None:
    message_id = MessageId.generate()
    assert _message(id=message_id) == _message(id=message_id)
    assert _message(id=message_id) != _message(id=message_id, content="other")
