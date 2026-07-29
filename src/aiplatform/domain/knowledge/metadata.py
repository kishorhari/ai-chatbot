"""Knowledge metadata and query-time filtering (ADR-0016).

Metadata is a small, immutable map of scalar values — enough to tag documents and
chunks (source, title, section, tags) and to filter retrieval, and small enough to
map cleanly to a ``JSONB`` column and a vector-store payload. A rich query DSL is
deliberately out of scope (ADR-0016): only equality and membership constraints.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

#: The scalar value types metadata may hold.
MetadataValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class Metadata:
    """An immutable, scalar-valued metadata map.

    Stored as a sorted tuple of items so the value object is hashable and compares
    by content; exposed as a read-only mapping.
    """

    items: tuple[tuple[str, MetadataValue], ...] = ()

    @classmethod
    def of(cls, values: Mapping[str, MetadataValue] | None = None) -> Metadata:
        """Build metadata from a mapping (empty when ``None``)."""
        if not values:
            return cls(())
        return cls(tuple(sorted(values.items())))

    def __post_init__(self) -> None:
        """Reject empty keys and non-scalar values."""
        for key, value in self.items:
            if not key:
                raise ValueError("metadata keys must be non-empty")
            if not isinstance(value, (bool, int, float, str)):
                raise ValueError(f"metadata value for {key!r} must be a scalar")

    def as_dict(self) -> dict[str, MetadataValue]:
        """Return a plain dict copy of the metadata."""
        return dict(self.items)

    def get(self, key: str) -> MetadataValue | None:
        """Return the value for ``key``, or ``None`` if absent."""
        for existing_key, value in self.items:
            if existing_key == key:
                return value
        return None


@dataclass(frozen=True, slots=True)
class MetadataFilter:
    """A query-time constraint on chunk metadata.

    Attributes:
        equals: Fields that must equal the given scalar exactly.
        any_of: Fields whose value must be one of the given set.

    An empty filter matches everything.
    """

    equals: tuple[tuple[str, MetadataValue], ...] = ()
    any_of: tuple[tuple[str, tuple[MetadataValue, ...]], ...] = ()

    @classmethod
    def none(cls) -> MetadataFilter:
        """A filter that matches every chunk."""
        return cls()

    @property
    def is_empty(self) -> bool:
        """Whether the filter constrains nothing."""
        return not self.equals and not self.any_of

    def matches(self, metadata: Metadata) -> bool:
        """Return whether ``metadata`` satisfies every constraint."""
        for key, expected in self.equals:
            if metadata.get(key) != expected:
                return False
        for key, allowed in self.any_of:
            if metadata.get(key) not in allowed:
                return False
        return True
