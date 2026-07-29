"""Knowledge domain ports (ADR-0011/0012/0013/0016).

Three infrastructure-facing contracts, each speaking only in domain value objects
(never SDK types) and each proven by a shared contract suite with ≥2
implementations (mirroring ``LLMProvider`` and ``ConversationRepository``):

* ``EmbeddingProvider`` — text → ``EmbeddingVector`` (ADR-0012).
* ``VectorStore`` — upsert / cosine similarity search / delete vectors (ADR-0013).
* ``KnowledgeRepository`` — persist the ``KnowledgeDocument`` record (ADR-0016).

Async throughout, to match the async LLM/persistence stack.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from .document import KnowledgeDocument
from .ids import KnowledgeChunkId, KnowledgeDocumentId
from .metadata import Metadata, MetadataFilter
from .vectors import EmbeddingVector


@dataclass(frozen=True, slots=True)
class EmbeddingCapabilities:
    """Static declaration of an embedding model's properties (no I/O).

    Attributes:
        model: The embedding model identifier.
        dimension: The fixed output vector dimension; used to validate the store.
    """

    model: str
    dimension: int


@dataclass(frozen=True, slots=True)
class VectorEntry:
    """A vector to index, with the payload retrieval needs (ADR-0013)."""

    chunk_id: KnowledgeChunkId
    document_id: KnowledgeDocumentId
    vector: EmbeddingVector
    text: str
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """A similarity-search hit: a chunk payload plus its score, ordered by score."""

    chunk_id: KnowledgeChunkId
    document_id: KnowledgeDocumentId
    text: str
    metadata: Metadata
    score: float


class EmbeddingProvider(ABC):
    """Abstract port turning text into embedding vectors (ADR-0012)."""

    @abstractmethod
    async def embed_documents(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Embed a batch of document texts (ingestion path).

        Returns one vector per input, in order; all of the provider's declared
        ``capabilities().dimension``.

        Raises:
            EmbeddingError: On any transport/vendor failure (no SDK error escapes).
        """

    @abstractmethod
    async def embed_query(self, text: str) -> EmbeddingVector:
        """Embed a single query text (retrieval path).

        Raises:
            EmbeddingError: On any transport/vendor failure.
        """

    @abstractmethod
    def capabilities(self) -> EmbeddingCapabilities:
        """Return the model id and vector dimension. Performs no I/O."""


class VectorStore(ABC):
    """Abstract port for vector upsert, cosine similarity search, and delete."""

    @abstractmethod
    async def upsert(self, entries: Sequence[VectorEntry]) -> None:
        """Insert or replace vectors (by chunk id) with their payloads.

        Raises:
            DimensionMismatchError: If an entry's vector dimension does not match
                the store's established dimension.
            VectorStoreError: On any backend failure.
        """

    @abstractmethod
    async def search(
        self, query: EmbeddingVector, *, k: int, filter: MetadataFilter
    ) -> list[VectorMatch]:
        """Return the ``k`` most cosine-similar entries matching ``filter``.

        Results are ordered by descending similarity. ``filter`` may be empty
        (``MetadataFilter.none()``) to search all entries.

        Raises:
            DimensionMismatchError: If the query dimension does not match the store.
            VectorStoreError: On any backend failure.
        """

    @abstractmethod
    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Remove all vectors belonging to ``document_id`` (idempotent)."""


class KnowledgeRepository(ABC):
    """Abstract persistence port for the ``KnowledgeDocument`` record (ADR-0016)."""

    @abstractmethod
    async def add(self, document: KnowledgeDocument) -> None:
        """Persist a new document and its chunks.

        Raises:
            KnowledgeDocumentAlreadyExistsError: If the identity is already stored.
        """

    @abstractmethod
    async def get(self, document_id: KnowledgeDocumentId) -> KnowledgeDocument:
        """Load a document by identity.

        Raises:
            KnowledgeDocumentNotFoundError: If no document has that identity.
        """

    @abstractmethod
    async def delete(self, document_id: KnowledgeDocumentId) -> None:
        """Delete a document and its chunks.

        Raises:
            KnowledgeDocumentNotFoundError: If no document has that identity.
        """

    @abstractmethod
    async def list(self, filter: MetadataFilter) -> tuple[KnowledgeDocument, ...]:
        """Return the documents whose metadata satisfies ``filter`` (empty = all)."""
