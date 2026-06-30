"""Unit tests for chat message value objects (M1.2-a)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.domain.llm.messages import ChatMessage, Role


def test_roles_are_lowercase_strings() -> None:
    assert Role.SYSTEM == "system"
    assert Role.USER == "user"
    assert Role.ASSISTANT == "assistant"


def test_factory_constructors_set_role() -> None:
    assert ChatMessage.system("s").role is Role.SYSTEM
    assert ChatMessage.user("u").role is Role.USER
    assert ChatMessage.assistant("a").role is Role.ASSISTANT


def test_content_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role=Role.USER, content="")


def test_message_is_immutable() -> None:
    message = ChatMessage.user("hello")
    with pytest.raises(ValidationError):
        message.content = "changed"  # type: ignore[misc]


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role=Role.USER, content="hi", extra="x")  # type: ignore[call-arg]


def test_value_equality() -> None:
    assert ChatMessage.user("hi") == ChatMessage.user("hi")
    assert ChatMessage.user("hi") != ChatMessage.assistant("hi")
