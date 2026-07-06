"""Unit tests for the Conversation aggregate root (M2.0)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId, MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

_WHEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _start(**overrides: object) -> Conversation:
    kwargs: dict[str, object] = {"owner": "user-1", "created_at": _WHEN}
    kwargs.update(overrides)
    return Conversation.start(**kwargs)  # type: ignore[arg-type]


# --- construction & validation ------------------------------------------------


def test_start_generates_an_id_and_empty_history() -> None:
    conversation = _start()
    assert isinstance(conversation.id, ConversationId)
    assert conversation.message_count == 0
    assert conversation.last_message is None
    assert conversation.has_system_message is False


def test_start_accepts_an_explicit_id() -> None:
    conversation_id = ConversationId.generate()
    assert _start(conversation_id=conversation_id).id == conversation_id


def test_owner_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="owner must be non-empty"):
        _start(owner="")


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="must be timezone-aware"):
        _start(created_at=datetime(2026, 1, 1, 12, 0))  # intentionally naive


# --- append -------------------------------------------------------------------


def test_append_assigns_contiguous_sequences() -> None:
    conversation = _start()
    first = conversation.append_user("hi", created_at=_WHEN)
    second = conversation.append_assistant("hello", created_at=_WHEN)
    assert (first.sequence, second.sequence) == (0, 1)
    assert conversation.message_count == 2
    assert conversation.last_message == second


def test_append_returns_the_created_message() -> None:
    conversation = _start()
    message = conversation.append_user("hi", created_at=_WHEN)
    assert isinstance(message, Message)
    assert message.role is Role.USER
    assert conversation.messages[-1] is message


def test_append_assistant_carries_usage() -> None:
    conversation = _start()
    usage = TokenUsage(prompt_tokens=2, completion_tokens=3)
    message = conversation.append_assistant("hello", created_at=_WHEN, usage=usage)
    assert message.usage == usage


def test_append_accepts_an_explicit_message_id() -> None:
    conversation = _start()
    message_id = MessageId.generate()
    message = conversation.append_user("hi", created_at=_WHEN, message_id=message_id)
    assert message.id == message_id


def test_system_message_must_be_first() -> None:
    conversation = _start()
    conversation.append_user("hi", created_at=_WHEN)
    with pytest.raises(ValueError, match="system message must be the first"):
        conversation.append_system("late system prompt", created_at=_WHEN)


def test_system_message_as_first_is_allowed() -> None:
    conversation = _start()
    conversation.append_system("you are helpful", created_at=_WHEN)
    assert conversation.has_system_message is True


def test_empty_content_is_rejected_on_append() -> None:
    conversation = _start()
    with pytest.raises(ValueError, match="content must be non-empty"):
        conversation.append_user("", created_at=_WHEN)


# --- immutable view -----------------------------------------------------------


def test_messages_view_is_an_immutable_snapshot() -> None:
    conversation = _start()
    conversation.append_user("hi", created_at=_WHEN)
    snapshot = conversation.messages
    assert isinstance(snapshot, tuple)
    conversation.append_assistant("hello", created_at=_WHEN)
    assert len(snapshot) == 1  # the earlier snapshot did not change


# --- reconstitution -----------------------------------------------------------


def _message(sequence: int, role: Role = Role.USER, content: str = "x") -> Message:
    return Message(
        id=MessageId.generate(),
        role=role,
        content=content,
        sequence=sequence,
        created_at=_WHEN,
    )


def test_reconstitute_round_trips_a_valid_history() -> None:
    conversation_id = ConversationId.generate()
    messages = [
        _message(0, Role.SYSTEM, "sys"),
        _message(1, Role.USER, "hi"),
        _message(2, Role.ASSISTANT, "hello"),
    ]
    conversation = Conversation.reconstitute(
        conversation_id=conversation_id, owner="user-1", created_at=_WHEN, messages=messages
    )
    assert conversation.id == conversation_id
    assert conversation.message_count == 3
    assert conversation.has_system_message is True


def test_reconstitute_rejects_non_contiguous_sequences() -> None:
    with pytest.raises(ValueError, match="contiguous from 0"):
        Conversation.reconstitute(
            conversation_id=ConversationId.generate(),
            owner="user-1",
            created_at=_WHEN,
            messages=[_message(0), _message(2)],
        )


def test_reconstitute_rejects_a_non_leading_system_message() -> None:
    with pytest.raises(ValueError, match="system message must be the first"):
        Conversation.reconstitute(
            conversation_id=ConversationId.generate(),
            owner="user-1",
            created_at=_WHEN,
            messages=[_message(0, Role.USER), _message(1, Role.SYSTEM)],
        )


# --- entity identity ----------------------------------------------------------


def test_equality_and_hash_are_by_identity() -> None:
    conversation_id = ConversationId.generate()
    a = _start(conversation_id=conversation_id)
    b = _start(conversation_id=conversation_id)
    a.append_user("hi", created_at=_WHEN)  # differing state must not affect equality
    assert a == b
    assert hash(a) == hash(b)
    assert a in {b}


def test_not_equal_to_other_types() -> None:
    assert _start() != "not a conversation"


def test_exposes_owner_created_at_and_repr() -> None:
    conversation = _start()
    assert conversation.owner == "user-1"
    assert conversation.created_at == _WHEN
    assert "Conversation(id=" in repr(conversation)
