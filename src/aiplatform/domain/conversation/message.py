"""The ``Message`` entity — one durable, immutable turn in a conversation.

A stored message is deliberately distinct from the transport ``ChatMessage``
(ADR-0007): it is an entity with its own identity, an explicit position, a
timestamp, and optional token accounting — concerns that belong to persistence and
history, not to the frozen provider port. Prompt assembly (ADR-0009) maps a
``Message`` onto a ``ChatMessage`` when building a request; the two evolve
independently.

Modelled as a frozen, slotted dataclass (like ``CompletionChunk``): messages are
constructed by the aggregate and by the repository mapping, not coerced from raw
external input, so cheap immutable construction is preferred over input parsing.
Messages are **append-only and never mutated** — an edit or regeneration is a new
message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

from .ids import MessageId


@dataclass(frozen=True, slots=True)
class Message:
    """An immutable message within a conversation.

    Attributes:
        id: The message's identity.
        role: Who authored the message.
        content: The message text; must be non-empty (an empty turn carries no
            domain meaning, matching ``ChatMessage``).
        sequence: The message's zero-based position within its conversation.
            Ordering is explicit and never inferred from ``created_at`` (ADR-0007).
        created_at: When the message was created. Must be timezone-aware — the
            time is supplied by the caller, keeping the domain free of clock I/O.
        usage: Token accounting for this turn, when known (e.g. an assistant
            reply from a provider that reports usage); ``None`` otherwise.
    """

    id: MessageId
    role: Role
    content: str
    sequence: int
    created_at: datetime
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        """Enforce the message's invariants at construction."""
        if not self.content:
            raise ValueError("message content must be non-empty")
        if self.sequence < 0:
            raise ValueError("message sequence must be non-negative")
        if self.created_at.tzinfo is None:
            raise ValueError("message created_at must be timezone-aware")
