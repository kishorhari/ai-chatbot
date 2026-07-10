"""The ``ConversationRepository`` port — persistence contract for the aggregate.

The repository of a domain aggregate is a **domain contract** (ADR-0008),
consistent with ``LLMProvider`` living in the domain. It speaks **only** in
domain aggregates — never ORM rows, DTOs, or SQL — so ``domain`` and
``application`` stay free of any persistence dependency (ADR-0001). Every
implementation (the in-memory repository now, PostgreSQL at M2.5) must satisfy the
shared repository contract suite; that suite is the executable proof of the swap.

The interface is deliberately minimal (YAGNI, ADR-0008): ``add`` a new
conversation, ``get`` one by identity, and ``save`` changes to a loaded one.
Owner-scoped listing and ``next_sequence`` are added only when a concrete use case
requires them.

Snapshot semantics are part of the contract, not an implementation detail: a
repository stores and returns **independent** aggregates. Mutating a conversation
obtained from :meth:`get` never affects stored state until it is passed back to
:meth:`save`, and never affects another loaded copy. PostgreSQL honours this
naturally (each load rehydrates from rows); the in-memory implementation must copy
explicitly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .conversation import Conversation
from .ids import ConversationId


class RepositoryError(Exception):
    """Base class for conversation-repository failures."""


class ConversationNotFoundError(RepositoryError):
    """Raised when no conversation exists for the requested identity."""

    def __init__(self, conversation_id: ConversationId) -> None:
        """Record the missing identity and build a clear message."""
        super().__init__(f"conversation {conversation_id} not found")
        self.conversation_id = conversation_id


class ConversationAlreadyExistsError(RepositoryError):
    """Raised when adding a conversation whose identity is already stored."""

    def __init__(self, conversation_id: ConversationId) -> None:
        """Record the conflicting identity and build a clear message."""
        super().__init__(f"conversation {conversation_id} already exists")
        self.conversation_id = conversation_id


class ConversationRepository(ABC):
    """Abstract persistence port for the ``Conversation`` aggregate.

    Async throughout, to match the async provider port and the (later) async
    SQLAlchemy implementation (ADR-0008).
    """

    @abstractmethod
    async def add(self, conversation: Conversation) -> None:
        """Persist a brand-new conversation.

        Args:
            conversation: The conversation to store. An independent snapshot is
                taken; later mutations of the passed instance do not affect stored
                state until :meth:`save`.

        Raises:
            ConversationAlreadyExistsError: If a conversation with the same
                identity is already stored.
        """

    @abstractmethod
    async def get(self, conversation_id: ConversationId) -> Conversation:
        """Load a conversation by identity.

        Args:
            conversation_id: The identity to load.

        Returns:
            An independent aggregate rehydrated from stored state (via
            :meth:`Conversation.reconstitute`). Mutating it does not change stored
            state until it is passed to :meth:`save`.

        Raises:
            ConversationNotFoundError: If no conversation has that identity.
        """

    @abstractmethod
    async def save(self, conversation: Conversation) -> None:
        """Persist changes to a previously-stored conversation.

        Appending new messages goes through the aggregate root
        (``conversation.append(...)``); this method durably records the resulting
        state.

        Args:
            conversation: The loaded, mutated conversation to persist. An
                independent snapshot is taken.

        Raises:
            ConversationNotFoundError: If the conversation was never added.
        """
