"""Run the shared vector-store contract suite against InMemoryVectorStore (M3.2).

The in-memory store passing this suite (and, at M3.7, pgvector passing the
identical suite) is the executable proof the vector-search swap is real (ADR-0013).
"""

from __future__ import annotations

import pytest
from vector_store_contract import VectorStoreContract

from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore


class TestInMemoryVectorStoreContract(VectorStoreContract):
    """InMemoryVectorStore must satisfy every VectorStore invariant."""

    @pytest.fixture
    def store(self) -> InMemoryVectorStore:
        return InMemoryVectorStore()
