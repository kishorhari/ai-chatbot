"""The ``Conversation`` aggregate root.

``Conversation`` owns its ``Message`` entities and is the transactional
consistency boundary (ADR-0007): all history changes go through the root, which
enforces the aggregate's invariants in one place —

* messages are appended with contiguous, zero-based ``sequence`` values;
* a ``SYSTEM`` message, if present, may only be the first message (index 0),
  so there is at most one;
* the conversation always has a non-empty ``owner`` (the principal), present from
  day one so multi-tenancy (M6) becomes enforcement, not a schema change.

Two construction paths exist: :meth:`start` for a brand-new conversation, and
:meth:`reconstitute` for rebuilding one from persisted state (the repository's
entry point, ADR-0008). Both run the same invariant checks, so a stored
conversation can never re-enter the domain in an invalid shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Self

from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

from .ids import ConversationId, MessageId
from .message import Message


class Conversation:
    """A conversation and its ordered, append-only message history."""

    def __init__(
        self,
        *,
        conversation_id: ConversationId,
        owner: str,
        created_at: datetime,
        messages: Sequence[Message],
    ) -> None:
        """Construct and validate a conversation.

        Prefer the :meth:`start` / :meth:`reconstitute` factories; this
        initialiser is shared by both and enforces every invariant.

        Args:
            conversation_id: The conversation's identity.
            owner: The principal that owns the conversation; must be non-empty.
            created_at: When the conversation began; must be timezone-aware.
            messages: The existing messages, in order (empty for a new conversation).

        Raises:
            ValueError: If the owner is empty, ``created_at`` is naive, or the
                messages violate the sequence/system-message invariants.
        """
        if not owner:
            raise ValueError("conversation owner must be non-empty")
        if created_at.tzinfo is None:
            raise ValueError("conversation created_at must be timezone-aware")
        self._id = conversation_id
        self._owner = owner
        self._created_at = created_at
        self._messages: list[Message] = list(messages)
        self._validate_history(self._messages)

    @classmethod
    def start(
        cls,
        *,
        owner: str,
        created_at: datetime,
        conversation_id: ConversationId | None = None,
    ) -> Self:
        """Begin a new, empty conversation.

        Args:
            owner: The owning principal.
            created_at: The (timezone-aware) start time.
            conversation_id: An explicit id; a fresh one is generated when omitted.

        Returns:
            A new conversation with no messages.
        """
        return cls(
            conversation_id=conversation_id or ConversationId.generate(),
            owner=owner,
            created_at=created_at,
            messages=(),
        )

    @classmethod
    def reconstitute(
        cls,
        *,
        conversation_id: ConversationId,
        owner: str,
        created_at: datetime,
        messages: Sequence[Message],
    ) -> Self:
        """Rebuild a conversation from persisted state (repository entry point).

        Runs the same invariant checks as :meth:`start`/:meth:`append`, so
        invalid stored data is rejected rather than silently trusted.

        Args:
            conversation_id: The stored identity.
            owner: The stored owner.
            created_at: The stored (timezone-aware) creation time.
            messages: The stored messages, in order.

        Returns:
            The rehydrated conversation.

        Raises:
            ValueError: If the stored state violates any invariant.
        """
        return cls(
            conversation_id=conversation_id,
            owner=owner,
            created_at=created_at,
            messages=messages,
        )

    @staticmethod
    def _validate_history(messages: Sequence[Message]) -> None:
        """Enforce contiguous sequencing and the single-leading-system rule."""
        for index, message in enumerate(messages):
            if message.sequence != index:
                raise ValueError(
                    f"message sequence must be contiguous from 0; "
                    f"expected {index}, got {message.sequence}"
                )
            if message.role is Role.SYSTEM and index != 0:
                raise ValueError("a system message must be the first message")

    def append(
        self,
        *,
        role: Role,
        content: str,
        created_at: datetime,
        usage: TokenUsage | None = None,
        message_id: MessageId | None = None,
    ) -> Message:
        """Append a message to the history and return it.

        The next ``sequence`` is assigned by the aggregate, so contiguity cannot
        be violated by callers. A ``SYSTEM`` message is only permitted as the very
        first message.

        Args:
            role: The author role.
            content: The message text (must be non-empty).
            created_at: The (timezone-aware) message time, supplied by the caller.
            usage: Optional token accounting for this turn.
            message_id: An explicit id; a fresh one is generated when omitted.

        Returns:
            The newly appended message.

        Raises:
            ValueError: If a system message is not first, or the content/time are
                invalid (enforced by :class:`Message`).
        """
        sequence = len(self._messages)
        if role is Role.SYSTEM and sequence != 0:
            raise ValueError("a system message must be the first message")
        message = Message(
            id=message_id or MessageId.generate(),
            role=role,
            content=content,
            sequence=sequence,
            created_at=created_at,
            usage=usage,
        )
        self._messages.append(message)
        return message

    def append_system(
        self,
        content: str,
        *,
        created_at: datetime,
        message_id: MessageId | None = None,
    ) -> Message:
        """Append a system message (only valid as the first message)."""
        return self.append(
            role=Role.SYSTEM, content=content, created_at=created_at, message_id=message_id
        )

    def append_user(
        self,
        content: str,
        *,
        created_at: datetime,
        message_id: MessageId | None = None,
    ) -> Message:
        """Append a user message."""
        return self.append(
            role=Role.USER, content=content, created_at=created_at, message_id=message_id
        )

    def append_assistant(
        self,
        content: str,
        *,
        created_at: datetime,
        usage: TokenUsage | None = None,
        message_id: MessageId | None = None,
    ) -> Message:
        """Append an assistant message, optionally with token usage."""
        return self.append(
            role=Role.ASSISTANT,
            content=content,
            created_at=created_at,
            usage=usage,
            message_id=message_id,
        )

    @property
    def id(self) -> ConversationId:
        """The conversation's identity."""
        return self._id

    @property
    def owner(self) -> str:
        """The owning principal."""
        return self._owner

    @property
    def created_at(self) -> datetime:
        """When the conversation began."""
        return self._created_at

    @property
    def messages(self) -> tuple[Message, ...]:
        """An immutable, ordered snapshot of the history."""
        return tuple(self._messages)

    @property
    def message_count(self) -> int:
        """The number of messages in the history."""
        return len(self._messages)

    @property
    def last_message(self) -> Message | None:
        """The most recent message, or ``None`` if the conversation is empty."""
        return self._messages[-1] if self._messages else None

    @property
    def has_system_message(self) -> bool:
        """Whether the conversation opens with a system message."""
        return bool(self._messages) and self._messages[0].role is Role.SYSTEM

    def __eq__(self, other: object) -> bool:
        """Entities are equal by identity, not by current state."""
        if not isinstance(other, Conversation):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        """Hash by the stable identity (safe despite mutable history)."""
        return hash(self._id)

    def __repr__(self) -> str:
        """Return an unambiguous, state-summarising representation."""
        return f"Conversation(id={self._id}, owner={self._owner!r}, messages={len(self._messages)})"
