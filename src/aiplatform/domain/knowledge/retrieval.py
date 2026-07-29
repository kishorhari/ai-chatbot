"""Retrieval value objects (ADR-0011/0015).

``RetrievedContext`` is the immutable result of a retrieval: the ordered chunks a
query surfaced, each with its similarity score. It is the value the (M3.5)
``ContextProvider`` consumes to enrich a prompt; defined in the domain so both the
retriever and the enricher speak one vocabulary. It carries no provider or
vector-store detail — only chunk identity, text, metadata, and score.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .ids import KnowledgeChunkId, KnowledgeDocumentId
from .metadata import Metadata


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A single chunk surfaced by retrieval, with its similarity score.

    Attributes:
        chunk_id: Identity of the retrieved chunk.
        document_id: The document the chunk belongs to (provenance).
        text: The chunk text (carried so enrichment needs no second lookup).
        metadata: The chunk's scalar metadata.
        score: Cosine similarity to the query, in ``[-1.0, 1.0]``.
    """

    chunk_id: KnowledgeChunkId
    document_id: KnowledgeDocumentId
    text: str
    metadata: Metadata
    score: float


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """The ordered set of chunks retrieved for a query.

    Attributes:
        query: The query text the retrieval answered.
        chunks: The retrieved chunks, ordered most-relevant first.
    """

    query: str
    chunks: tuple[RetrievedChunk, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls, query: str = "") -> RetrievedContext:
        """An empty context (no knowledge retrieved) — the RAG-off result."""
        return cls(query=query, chunks=())

    @property
    def is_empty(self) -> bool:
        """Whether no chunks were retrieved."""
        return not self.chunks

    def __post_init__(self) -> None:
        """Enforce that chunks are ordered by non-increasing score."""
        scores = [chunk.score for chunk in self.chunks]
        if scores != sorted(scores, reverse=True):
            raise ValueError("retrieved chunks must be ordered by descending score")

    @staticmethod
    def ordered(query: str, chunks: Sequence[RetrievedChunk]) -> RetrievedContext:
        """Build a context, sorting chunks by descending score defensively."""
        ranked = tuple(sorted(chunks, key=lambda chunk: chunk.score, reverse=True))
        return RetrievedContext(query=query, chunks=ranked)
