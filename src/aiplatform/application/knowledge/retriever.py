"""The ``Retriever`` port — the retrieval abstraction (ADR-0015).

An application-layer port: given a query and a metadata filter, return the ordered
knowledge relevant to it as a domain ``RetrievedContext``. It is the seam future
retrieval strategies (hybrid keyword+vector, reranking) will implement, and the
seam the M3.5 ``ContextProvider`` composes. The M3.4 implementation is
``SemanticRetriever`` (embedding + vector search).

The port speaks only in domain value objects — a query string in, a
``RetrievedContext`` out — and knows nothing of embeddings, vectors, or stores;
those are the implementation's collaborators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiplatform.domain.knowledge.metadata import MetadataFilter
from aiplatform.domain.knowledge.retrieval import RetrievedContext


class Retriever(ABC):
    """Abstract port that returns the knowledge relevant to a query."""

    @abstractmethod
    async def retrieve(self, query: str, *, k: int, filter: MetadataFilter) -> RetrievedContext:
        """Return up to ``k`` relevant chunks matching ``filter``, most-relevant first.

        Args:
            query: The query text.
            k: The maximum number of chunks to return.
            filter: Metadata constraints applied during retrieval (``none()`` = all).

        Returns:
            A :class:`RetrievedContext` (empty when nothing relevant is found).
        """
