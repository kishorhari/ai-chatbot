"""The ``EmbeddingVector`` value object (ADR-0011/0012).

A dense embedding as an immutable, fixed-dimension sequence of floats. It is a
domain value object — the vocabulary the ``EmbeddingProvider`` produces and the
``VectorStore`` indexes — but it is deliberately dependency-free: **no numpy**, so
the domain carries no numeric-library dependency (enforced by import-linter).

Cosine similarity lives here as pure math because it is an intrinsic property of
two vectors; the in-memory vector store reuses it, so the metric is defined once
(the contract fixes cosine as the similarity measure, ADR-0013).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """An immutable, fixed-dimension embedding.

    Attributes:
        values: The vector components; must be non-empty.
    """

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        """Reject an empty vector — a zero-dimension embedding is meaningless."""
        if not self.values:
            raise ValueError("embedding vector must have at least one dimension")

    @property
    def dimension(self) -> int:
        """The number of components in the vector."""
        return len(self.values)

    def cosine_similarity(self, other: EmbeddingVector) -> float:
        """Return the cosine similarity with ``other`` in ``[-1.0, 1.0]``.

        Args:
            other: A vector of the same dimension.

        Returns:
            The cosine similarity, or ``0.0`` if either vector has zero magnitude
            (similarity is undefined for a zero vector; treated as "unrelated").

        Raises:
            ValueError: If the dimensions differ.
        """
        if self.dimension != other.dimension:
            raise ValueError(f"dimension mismatch: {self.dimension} vs {other.dimension}")
        dot = sum(a * b for a, b in zip(self.values, other.values, strict=True))
        magnitude = self._magnitude() * other._magnitude()
        if magnitude == 0.0:
            return 0.0
        return dot / magnitude

    def _magnitude(self) -> float:
        """Return the Euclidean norm of the vector."""
        return sqrt(sum(component * component for component in self.values))
