"""SemanticRetriever — embedding-based retrieval (ADR-0015).

The default ``Retriever`` implementation: embed the query with the
``EmbeddingProvider``, search the ``VectorStore`` for the nearest chunks (cosine,
with the metadata filter applied at the store), and project the matches onto a
domain ``RetrievedContext``. It is an application service over two domain ports —
it holds no embedding SDK or vector client — so it is unit-testable offline with
the fake embedder and in-memory store.

Metadata filtering happens **at the vector store** (where it is efficient); this
retriever passes the filter through and maps the results.
"""

from __future__ import annotations

from aiplatform.domain.knowledge.metadata import MetadataFilter
from aiplatform.domain.knowledge.ports import EmbeddingProvider, VectorStore
from aiplatform.domain.knowledge.retrieval import RetrievedChunk, RetrievedContext

from .retriever import Retriever


class SemanticRetriever(Retriever):
    """Retrieves by embedding the query and searching the vector store."""

    def __init__(self, *, embedder: EmbeddingProvider, vector_store: VectorStore) -> None:
        """Inject the embedding and vector-store ports."""
        self._embedder = embedder
        self._vector_store = vector_store

    async def retrieve(self, query: str, *, k: int, filter: MetadataFilter) -> RetrievedContext:
        """Embed the query, search, and return the ordered matches as context."""
        query_vector = await self._embedder.embed_query(query)
        matches = await self._vector_store.search(query_vector, k=k, filter=filter)
        chunks = [
            RetrievedChunk(
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                text=match.text,
                metadata=match.metadata,
                score=match.score,
            )
            for match in matches
        ]
        return RetrievedContext.ordered(query, chunks)
