"""RetrievalService — the application-facing retrieval use case (ADR-0015).

A thin service over the ``Retriever`` port that applies retrieval **policy** —
default ``k`` and an optional minimum-similarity threshold — and exposes a stable
query API. Delivery (the M3.6 debug search endpoint) and the M3.5
``ContextProvider`` call this rather than a concrete retriever, so the retrieval
*strategy* stays swappable behind the port while defaults and thresholds live in
one place.

It depends only on the ``Retriever`` port and domain value objects; metadata
filtering itself is performed by the retriever/vector store, and the score
threshold is applied here to the ordered result.
"""

from __future__ import annotations

from aiplatform.domain.knowledge.metadata import MetadataFilter
from aiplatform.domain.knowledge.retrieval import RetrievedContext

from .retriever import Retriever


class RetrievalService:
    """Runs a retrieval query with default ``k`` and a similarity threshold."""

    def __init__(self, retriever: Retriever, *, default_k: int = 5, min_score: float = 0.0) -> None:
        """Configure retrieval policy.

        Args:
            retriever: The retrieval strategy (a port).
            default_k: The ``k`` used when a query does not specify one; must be
                positive.
            min_score: Chunks scoring below this cosine similarity are dropped;
                must be in ``[-1.0, 1.0]``. ``-1.0`` disables the threshold.

        Raises:
            ValueError: If ``default_k`` is not positive or ``min_score`` is out of
                range.
        """
        if default_k <= 0:
            raise ValueError("default_k must be positive")
        if not -1.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [-1.0, 1.0]")
        self._retriever = retriever
        self._default_k = default_k
        self._min_score = min_score

    async def search(
        self, query: str, *, k: int | None = None, filter: MetadataFilter | None = None
    ) -> RetrievedContext:
        """Retrieve the relevant knowledge for ``query``, applying policy.

        Args:
            query: The query text.
            k: Maximum chunks to return; defaults to the configured ``default_k``.
            filter: Metadata constraints; defaults to no filter.

        Returns:
            A :class:`RetrievedContext` with sub-threshold chunks removed.
        """
        resolved_k = k if k is not None else self._default_k
        resolved_filter = filter if filter is not None else MetadataFilter.none()
        context = await self._retriever.retrieve(query, k=resolved_k, filter=resolved_filter)
        return self._apply_threshold(context)

    def _apply_threshold(self, context: RetrievedContext) -> RetrievedContext:
        """Drop chunks scoring below ``min_score`` (order is preserved)."""
        if self._min_score <= -1.0:
            return context
        kept = tuple(chunk for chunk in context.chunks if chunk.score >= self._min_score)
        if len(kept) == len(context.chunks):
            return context
        return RetrievedContext(query=context.query, chunks=kept)
