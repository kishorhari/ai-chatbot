"""Domain-generated identifiers for the conversation aggregate.

Identity is created in the domain, not by the database (ADR-0007): a
``Conversation`` and its ``Message`` entities have stable identity *before* they
are ever persisted, which is what makes the in-memory-first strategy (ADR-0005)
and database-free tests possible.

The identifiers are typed wrappers around ``uuid.UUID`` rather than bare UUIDs so
the type system prevents passing a :class:`MessageId` where a
:class:`ConversationId` is expected — two ids with the same underlying UUID but
different types never compare equal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EntityId:
    """Base for domain-generated, UUID-backed identifiers.

    Immutable and hashable. Not used directly — see :class:`ConversationId` and
    :class:`MessageId`, whose distinct types keep identifiers from being mixed up.
    """

    value: UUID

    @classmethod
    def generate(cls) -> Self:
        """Create a fresh, random identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> Self:
        """Parse an identifier from its string form.

        Args:
            raw: A canonical UUID string.

        Returns:
            The parsed identifier.

        Raises:
            ValueError: If ``raw`` is not a valid UUID.
        """
        return cls(UUID(raw))

    def __str__(self) -> str:
        """Return the canonical UUID string (e.g. for URLs and logs)."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ConversationId(EntityId):
    """Identity of a :class:`~aiplatform.domain.conversation.conversation.Conversation`."""


@dataclass(frozen=True, slots=True)
class MessageId(EntityId):
    """Identity of a :class:`~aiplatform.domain.conversation.message.Message`."""
