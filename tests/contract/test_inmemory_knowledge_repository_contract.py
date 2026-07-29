"""Run the shared knowledge-repository contract suite against in-memory (M3.3)."""

from __future__ import annotations

import pytest
from knowledge_repository_contract import KnowledgeRepositoryContract

from aiplatform.infrastructure.knowledge.repository.memory.repository import (
    InMemoryKnowledgeRepository,
)


class TestInMemoryKnowledgeRepositoryContract(KnowledgeRepositoryContract):
    """InMemoryKnowledgeRepository must satisfy every KnowledgeRepository invariant."""

    @pytest.fixture
    def repository(self) -> InMemoryKnowledgeRepository:
        return InMemoryKnowledgeRepository()
