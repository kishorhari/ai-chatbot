"""FakeEmbeddingProvider — the deterministic reference embedding (ADR-0012, ADR-0004).

A hashing "bag-of-words" embedding: each token is hashed (SHA-256 — stable across
processes, unlike the salted built-in ``hash``) into a signed component of a
fixed-dimension vector, which is then L2-normalised. It performs **no network or
model I/O** and is fully deterministic, so the whole RAG path is offline and
reproducible (the Echo precedent).

Because it is lexical, texts that share words produce more-similar vectors than
disjoint texts — crude but real similarity, which makes the offline retrieval
tests (M3.4/M3.8) meaningful without a model. It is not semantic; real embedding
quality is measured separately by the evaluation harness.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from math import sqrt
from typing import ClassVar

from aiplatform.domain.knowledge.ports import EmbeddingCapabilities, EmbeddingProvider
from aiplatform.domain.knowledge.vectors import EmbeddingVector

_TOKEN = re.compile(r"[a-z0-9]+")


class FakeEmbeddingProvider(EmbeddingProvider):
    """A deterministic, offline, lexical embedding provider.

    Args:
        dimension: The fixed output dimension.
        model: The model identifier reported by ``capabilities()``.
    """

    NAME: ClassVar[str] = "fake"

    def __init__(self, *, dimension: int = 256, model: str = "fake-embedding") -> None:
        """Configure the dimension and model id."""
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        self._dimension = dimension
        self._model = model

    def capabilities(self) -> EmbeddingCapabilities:
        """Return the model id and fixed dimension (no I/O)."""
        return EmbeddingCapabilities(model=self._model, dimension=self._dimension)

    async def embed_query(self, text: str) -> EmbeddingVector:
        """Embed a single text deterministically."""
        return self._embed(text)

    async def embed_documents(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Embed each text deterministically (batch == per-item for the fake)."""
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> EmbeddingVector:
        """Build a normalised, signed bag-of-words vector for ``text``."""
        buckets = [0.0] * self._dimension
        tokens = _TOKEN.findall(text.lower()) or [text]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            buckets[index] += sign
        norm = sqrt(sum(value * value for value in buckets))
        if norm == 0.0:  # degenerate (e.g. empty input): a fixed non-zero vector
            buckets[0] = 1.0
            norm = 1.0
        return EmbeddingVector(tuple(value / norm for value in buckets))
