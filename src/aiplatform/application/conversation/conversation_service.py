"""ConversationService — conversation lifecycle and retrieval (ADR-0010).

The application service backing the *create* and *fetch* use cases, sibling to
``ChatService`` (which owns the chat turn). It exists so the delivery layer stays
thin: starting a conversation is orchestration — construct the aggregate, obtain
"now" from the ``Clock`` port, optionally seed a system prompt, and persist within
the transaction boundary — and must not live in an endpoint (ADR-0010).

It depends only on ports and returns immutable **application DTOs** (never the
aggregate), so callers render history without reaching into the domain. It imports
no concrete adapter, ``httpx``, SQLAlchemy, or framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Self

from aiplatform.application.clock import Clock
from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId, MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.conversation.ports import ConversationRepository
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage

from .transaction import TransactionBoundary


@dataclass(frozen=True, slots=True)
class MessageView:
    """An immutable projection of a stored ``Message`` for delivery."""

    id: MessageId
    role: Role
    content: str
    sequence: int
    created_at: datetime
    usage: TokenUsage | None

    @classmethod
    def of(cls, message: Message) -> Self:
        """Project a domain ``Message`` into a view."""
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            sequence=message.sequence,
            created_at=message.created_at,
            usage=message.usage,
        )


@dataclass(frozen=True, slots=True)
class ConversationView:
    """An immutable projection of a ``Conversation`` aggregate for delivery."""

    id: ConversationId
    owner: str
    created_at: datetime
    messages: tuple[MessageView, ...]

    @classmethod
    def of(cls, conversation: Conversation) -> Self:
        """Project a domain ``Conversation`` into a view."""
        return cls(
            id=conversation.id,
            owner=conversation.owner,
            created_at=conversation.created_at,
            messages=tuple(MessageView.of(m) for m in conversation.messages),
        )


class ConversationService:
    """Creates and retrieves conversations."""

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        clock: Clock,
        transactions: TransactionBoundary,
    ) -> None:
        """Inject collaborators; store no per-request state."""
        self._repository = repository
        self._clock = clock
        self._transactions = transactions

    async def start_conversation(
        self, *, owner: str, system_prompt: str | None = None
    ) -> ConversationView:
        """Create a new conversation, optionally seeded with a system prompt.

        Args:
            owner: The owning principal (required). Becomes the authenticated
                principal when auth arrives (M6); explicit for now.
            system_prompt: An optional leading system message.

        Returns:
            A view of the created conversation.
        """
        now = self._clock.now()
        conversation = Conversation.start(owner=owner, created_at=now)
        if system_prompt is not None:
            conversation.append_system(system_prompt, created_at=now)

        async with self._transactions.atomic():
            await self._repository.add(conversation)

        return ConversationView.of(conversation)

    async def get_conversation(self, conversation_id: ConversationId) -> ConversationView:
        """Return the full history of a conversation.

        Args:
            conversation_id: The conversation to fetch.

        Returns:
            A view of the conversation and its ordered messages.

        Raises:
            ConversationNotFoundError: If no conversation has that identity.
        """
        conversation = await self._repository.get(conversation_id)
        return ConversationView.of(conversation)
