"""KnowledgeContextProvider — the RAG-on context provider (ADR-0015).

Implements the conversation ``ContextProvider`` port by composing the two
knowledge collaborators: it retrieves relevant knowledge for the query via the
``RetrievalService`` and injects it into the turn's messages via the pure
``PromptEnricher``. This is the single collaborator ``ChatService`` delegates to
when RAG is enabled; ``ChatService`` never sees the retriever or enricher.

It implements a port defined in ``application/conversation`` — so the dependency
flows knowledge → conversation (the feature depends on the core), and
``ChatService`` imports nothing from ``knowledge``.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiplatform.application.conversation.context_provider import ContextProvider
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.knowledge.metadata import MetadataFilter

from .prompt_enricher import PromptEnricher
from .retrieval_service import RetrievalService


class KnowledgeContextProvider(ContextProvider):
    """Retrieves knowledge for the query and enriches the prompt with it."""

    def __init__(
        self,
        *,
        retrieval: RetrievalService,
        enricher: PromptEnricher,
        k: int | None = None,
        metadata_filter: MetadataFilter | None = None,
    ) -> None:
        """Compose the retrieval and enrichment collaborators.

        Args:
            retrieval: The retrieval use case (applies default-k + threshold policy).
            enricher: The pure prompt enricher.
            k: Optional retrieval ``k`` override; ``None`` uses the service default.
            metadata_filter: Optional metadata constraint applied to every query.
        """
        self._retrieval = retrieval
        self._enricher = enricher
        self._k = k
        self._filter = metadata_filter

    async def enrich(
        self, messages: Sequence[Message], *, query: str, max_context_tokens: int | None
    ) -> tuple[Message, ...]:
        """Retrieve context for ``query`` and inject it into ``messages``."""
        context = await self._retrieval.search(query, k=self._k, filter=self._filter)
        return self._enricher.enrich(messages, context, max_context_tokens=max_context_tokens)
