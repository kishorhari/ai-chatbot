"""Provider-agnostic knowledge/retrieval error taxonomy (ADR-0011/0012/0013).

Mirrors the ``LLMError`` taxonomy (ADR-0002): embedding and vector-store adapters
map their transport/vendor failures onto these domain errors so that **no SDK or
transport exception escapes the infrastructure layer**, and callers reason about
failures through stable types rather than string-matching vendor messages.

Pure standard library — no pydantic, no vendor imports.
"""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base class for all knowledge-domain failures."""


class EmbeddingError(KnowledgeError):
    """An embedding provider failed to produce vectors (transport/vendor fault)."""


class VectorStoreError(KnowledgeError):
    """A vector store operation failed (transport/backend fault)."""


class DimensionMismatchError(KnowledgeError):
    """A vector's dimension does not match what the store/provider expects.

    Guards the silent-invalidation risk (ADR-0013): a query or upsert whose vector
    dimension differs from the index's fails fast rather than corrupting results.
    """

    def __init__(self, *, expected: int, actual: int) -> None:
        """Record the expected and actual dimensions."""
        super().__init__(f"embedding dimension mismatch: expected {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


class KnowledgeDocumentNotFoundError(KnowledgeError):
    """Raised when no knowledge document exists for the requested identity."""

    def __init__(self, document_id: object) -> None:
        """Record the missing identity."""
        super().__init__(f"knowledge document {document_id} not found")
        self.document_id = document_id


class KnowledgeDocumentAlreadyExistsError(KnowledgeError):
    """Raised when adding a document whose identity is already stored."""

    def __init__(self, document_id: object) -> None:
        """Record the conflicting identity."""
        super().__init__(f"knowledge document {document_id} already exists")
        self.document_id = document_id
