"""Unit tests for the ContextProvider port default (M3.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.application.conversation.context_provider import NullContextProvider
from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _message(role: Role, content: str, sequence: int) -> Message:
    return Message(
        id=MessageId.generate(), role=role, content=content, sequence=sequence, created_at=_TS
    )


async def test_null_provider_returns_messages_unchanged() -> None:
    messages = (
        _message(Role.SYSTEM, "You are helpful.", 0),
        _message(Role.USER, "Hello", 1),
    )
    result = await NullContextProvider().enrich(messages, query="Hello", max_context_tokens=None)
    assert result == messages


async def test_null_provider_returns_a_tuple_copy() -> None:
    messages = [_message(Role.USER, "Hi", 0)]
    result = await NullContextProvider().enrich(messages, query="Hi", max_context_tokens=4096)
    assert isinstance(result, tuple)
    assert list(result) == messages
