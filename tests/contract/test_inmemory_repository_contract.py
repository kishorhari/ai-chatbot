"""Run the shared repository contract suite against the in-memory backend (M2.1).

The in-memory repository passing this suite (and, at M2.5, PostgreSQL passing the
identical suite) is the executable proof that the persistence swap is real
(ADR-0008).
"""

from __future__ import annotations

import pytest
from repository_contract import ConversationRepositoryContract

from aiplatform.infrastructure.persistence.memory.repository import (
    InMemoryConversationRepository,
)


class TestInMemoryRepositoryContract(ConversationRepositoryContract):
    """InMemoryConversationRepository must satisfy every repository invariant."""

    @pytest.fixture
    def repository(self) -> InMemoryConversationRepository:
        return InMemoryConversationRepository()
