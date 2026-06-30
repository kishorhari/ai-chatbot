"""Chat message value objects — the domain vocabulary for conversation turns.

Pure domain types (ADR-0001): no I/O, no framework beyond pydantic, no
vendor concepts. Every provider speaks in these objects rather than vendor
payload shapes (ADR-0002).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    """The author of a chat message.

    String-valued so it serialises naturally and reads clearly in logs, while
    still being a closed set the domain controls (never a raw vendor string).
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """An immutable single turn in a conversation.

    Attributes:
        role: Who authored the message.
        content: The message text. Must be non-empty — an empty turn carries no
            domain meaning.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Role
    content: str = Field(min_length=1)

    @classmethod
    def system(cls, content: str) -> Self:
        """Create a system message."""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> Self:
        """Create a user message."""
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> Self:
        """Create an assistant message."""
        return cls(role=Role.ASSISTANT, content=content)
