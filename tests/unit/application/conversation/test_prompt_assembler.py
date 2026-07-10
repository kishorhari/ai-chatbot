"""Unit tests for prompt assembly (M2.2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.application.conversation.prompt_assembler import PromptAssembler
from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.requests import GenerationParams

_WHEN = datetime(2026, 1, 1, tzinfo=UTC)


def _history() -> tuple[Message, ...]:
    convo = Conversation.start(owner="u", created_at=_WHEN)
    convo.append_system("You are helpful.", created_at=_WHEN)
    convo.append_user("Hello", created_at=_WHEN)
    convo.append_assistant("Hi there", created_at=_WHEN)
    return convo.messages


def _message(sequence: int, role: Role, content: str) -> Message:
    return Message(
        id=MessageId.generate(), role=role, content=content, sequence=sequence, created_at=_WHEN
    )


def test_maps_messages_to_chat_messages_in_order() -> None:
    request = PromptAssembler().assemble(_history())
    assert [(m.role, m.content) for m in request.messages] == [
        (Role.SYSTEM, "You are helpful."),
        (Role.USER, "Hello"),
        (Role.ASSISTANT, "Hi there"),
    ]


def test_defaults_model_and_params() -> None:
    request = PromptAssembler().assemble(_history())
    assert request.model is None
    assert request.params == GenerationParams()


def test_passes_model_and_params_through() -> None:
    params = GenerationParams(temperature=0.5)
    request = PromptAssembler().assemble(_history(), model="llama3", params=params)
    assert request.model == "llama3"
    assert request.params.temperature == 0.5


def test_rejects_empty_message_list() -> None:
    with pytest.raises(ValueError, match="empty message list"):
        PromptAssembler().assemble(())


def test_rejects_system_message_not_first() -> None:
    messages = [_message(0, Role.USER, "hi"), _message(1, Role.SYSTEM, "late system")]
    with pytest.raises(ValueError, match="only be the first message"):
        PromptAssembler().assemble(messages)


def test_rejects_a_second_system_message() -> None:
    messages = [_message(0, Role.SYSTEM, "sys"), _message(1, Role.SYSTEM, "sys again")]
    with pytest.raises(ValueError, match="only be the first message"):
        PromptAssembler().assemble(messages)


def test_single_leading_system_message_is_accepted() -> None:
    messages = [_message(0, Role.SYSTEM, "sys"), _message(1, Role.USER, "hi")]
    request = PromptAssembler().assemble(messages)
    assert request.messages[0].role is Role.SYSTEM
