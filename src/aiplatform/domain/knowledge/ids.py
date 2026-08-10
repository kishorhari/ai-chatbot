"""Domain-generated identifiers for the knowledge aggregate (ADR-0011/0016).

Identity is created in the domain, not by the database (the ADR-0007 precedent):
a ``KnowledgeDocument`` and its ``KnowledgeChunk`` entities have stable identity
before persistence, which keeps ingestion and the vector store keyed on
domain-owned ids and keeps tests database-free.

The knowledge context defines its **own** id base rather than importing the
conversation context's — bounded contexts do not share entity internals, so the
two remain independently evolvable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class _KnowledgeId:
    """Base for domain-generated, UUID-backed knowledge identifiers.

    Immutable and hashable. Not used directly — see :class:`KnowledgeDocumentId`
    and :class:`KnowledgeChunkId`, whose distinct types keep ids from being mixed.
    """

    value: UUID

    @classmethod
    def generate(cls) -> Self:
        """Create a fresh, random identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> Self:
        """Parse an identifier from its canonical UUID string.

        Raises:
            ValueError: If ``raw`` is not a valid UUID.
        """
        return cls(UUID(raw))

    def __str__(self) -> str:
        """Return the canonical UUID string (e.g. for URLs and logs)."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentId(_KnowledgeId):
    """Identity of a :class:`~aiplatform.domain.knowledge.document.KnowledgeDocument`."""


@dataclass(frozen=True, slots=True)
class KnowledgeChunkId(_KnowledgeId):
    """Identity of a :class:`~aiplatform.domain.knowledge.chunk.KnowledgeChunk`."""
