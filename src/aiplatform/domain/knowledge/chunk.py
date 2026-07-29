"""The ``KnowledgeChunk`` entity — one retrievable unit of a document (ADR-0011/0016).

A chunk is an immutable, append-only child of the ``KnowledgeDocument`` aggregate
with its own identity, an explicit contiguous ``ordinal`` position, its text, and
metadata. It mirrors the M2 ``Message`` entity: constructed by the aggregate (and
by repository mapping), never coerced from raw external input, so it is a frozen,
slotted dataclass.

The chunk's **embedding vector is not a field here** — it is stored in the vector
store keyed by ``id`` (ADR-0011). ``token_count`` is optional accounting recorded
at ingestion (used for budgeting), ``None`` when unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ids import KnowledgeChunkId
from .metadata import Metadata


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """An immutable, positioned chunk of a document's text.

    Attributes:
        id: The chunk's identity.
        ordinal: Zero-based position within its document; ordering is explicit and
            never inferred.
        text: The chunk text; must be non-empty.
        metadata: Scalar metadata (inherited from the document plus any own tags).
        token_count: Estimated token cost recorded at ingestion, if known.
    """

    id: KnowledgeChunkId
    ordinal: int
    text: str
    metadata: Metadata = field(default_factory=Metadata)
    token_count: int | None = None

    def __post_init__(self) -> None:
        """Enforce the chunk's invariants at construction."""
        if not self.text:
            raise ValueError("chunk text must be non-empty")
        if self.ordinal < 0:
            raise ValueError("chunk ordinal must be non-negative")
        if self.token_count is not None and self.token_count < 0:
            raise ValueError("chunk token_count must be non-negative")
