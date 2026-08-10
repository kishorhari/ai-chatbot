"""The ``ContextProvider`` port — ChatService's context-acquisition seam (ADR-0015).

``ChatService`` delegates the entire "obtain-and-enrich contextual knowledge" step
to a single collaborator behind this port, so it never accumulates retrieval or
enrichment responsibilities (the owner-ratified refinement). The port speaks only
in conversation ``Message``s — a windowed message sequence and the query in, the
(possibly context-augmented) sequence to assemble out — so ChatService depends on
nothing from the ``knowledge`` package.

The port lives here, beside its consumer, precisely because its contract is
conversation-message-shaped; the RAG implementation (``KnowledgeContextProvider``)
lives in ``application/knowledge`` and implements this port, so the dependency
flows knowledge → conversation (a feature depending on the core), never the
reverse. The ``NullContextProvider`` is the RAG-off default that returns the
messages unchanged, keeping M2 behaviour identical.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from aiplatform.domain.conversation.message import Message


class ContextProvider(ABC):
    """Acquires and injects contextual knowledge into a turn's messages."""

    @abstractmethod
    async def enrich(
        self, messages: Sequence[Message], *, query: str, max_context_tokens: int | None
    ) -> tuple[Message, ...]:
        """Return the messages to assemble, optionally augmented with context.

        Args:
            messages: The windowed conversation messages, in order.
            query: The text to retrieve context for (typically the latest user turn).
            max_context_tokens: The model's context budget, or ``None`` if unknown;
                an implementation must not let the augmented prompt exceed it.

        Returns:
            The message sequence to hand to the prompt assembler — unchanged when
            no context applies. Any augmentation is ephemeral (request-only); the
            conversation aggregate is never mutated.
        """


class NullContextProvider(ContextProvider):
    """The RAG-off provider: returns the messages unchanged."""

    async def enrich(
        self, messages: Sequence[Message], *, query: str, max_context_tokens: int | None
    ) -> tuple[Message, ...]:
        """Return the messages verbatim — no retrieval, no enrichment."""
        return tuple(messages)
