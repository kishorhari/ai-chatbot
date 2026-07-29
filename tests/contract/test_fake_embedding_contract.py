"""Run the shared embedding contract suite against FakeEmbeddingProvider (M3.1)."""

from __future__ import annotations

import pytest
from embedding_contract import EmbeddingProviderContract

from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider


class TestFakeEmbeddingContract(EmbeddingProviderContract):
    """FakeEmbeddingProvider must satisfy every EmbeddingProvider invariant."""

    @pytest.fixture
    def provider(self) -> FakeEmbeddingProvider:
        return FakeEmbeddingProvider(dimension=64)
