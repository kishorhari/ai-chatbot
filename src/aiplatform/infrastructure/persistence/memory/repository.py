"""In-memory ``ConversationRepository`` implementation.

A process-local dictionary of conversations, used for development and DB-free
tests (ADR-0005). It is the reference implementation the shared repository
contract suite runs against first; PostgreSQL (M2.5) must pass the identical
suite.

Snapshot semantics (part of the port contract, ADR-0008) are enforced by copying
on every write **and** every read: stored and returned aggregates are always
independent of the caller's instance, so an unsaved mutation never leaks into
storage and two loads never alias. Copies are made via
:meth:`Conversation.reconstitute`, which also re-validates invariants — stored
state can never re-enter the domain in an invalid shape.
"""

from __future__ import annotations

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import (
    ConversationAlreadyExistsError,
    ConversationNotFoundError,
    ConversationRepository,
)


class InMemoryConversationRepository(ConversationRepository):
    """Stores conversations in an in-process mapping keyed by identity."""

    def __init__(self) -> None:
        """Create an empty repository."""
        self._conversations: dict[ConversationId, Conversation] = {}

    async def add(self, conversation: Conversation) -> None:
        """Store a new conversation; reject a duplicate identity."""
        if conversation.id in self._conversations:
            raise ConversationAlreadyExistsError(conversation.id)
        self._conversations[conversation.id] = self._snapshot(conversation)

    async def get(self, conversation_id: ConversationId) -> Conversation:
        """Return an independent copy of the stored conversation."""
        stored = self._conversations.get(conversation_id)
        if stored is None:
            raise ConversationNotFoundError(conversation_id)
        return self._snapshot(stored)

    async def save(self, conversation: Conversation) -> None:
        """Persist changes to an already-stored conversation."""
        if conversation.id not in self._conversations:
            raise ConversationNotFoundError(conversation.id)
        self._conversations[conversation.id] = self._snapshot(conversation)

    @staticmethod
    def _snapshot(conversation: Conversation) -> Conversation:
        """Return an independent, re-validated copy of ``conversation``.

        Messages are immutable, so snapshotting the ordered message tuple into a
        freshly reconstituted aggregate fully decouples it from the source's
        mutable internal list.
        """
        return Conversation.reconstitute(
            conversation_id=conversation.id,
            owner=conversation.owner,
            created_at=conversation.created_at,
            messages=conversation.messages,
        )
