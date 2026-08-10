"""The shared EmbeddingProvider contract suite (ADR-0012).

A single behavioural specification every ``EmbeddingProvider`` implementation must
satisfy. Providers opt in by subclassing :class:`EmbeddingProviderContract` and
overriding the ``provider`` fixture. The deterministic ``FakeEmbeddingProvider``
and the real ``OllamaEmbeddingProvider`` (over respx) both passing this identical
suite is the executable proof the embedding abstraction is real — mirroring the
provider and repository contract suites.

Only **universal** invariants live here (determinism, dimension consistency, batch
shape). Model-specific behaviour (e.g. whether a query embedding equals a document
embedding, or semantic quality) is not asserted — the fake is lexical, real models
differ, and quality is measured by the separate evaluation harness.

Not named ``test_*`` so pytest collects only the ``Test*`` subclasses.
"""

from __future__ import annotations

import pytest

from aiplatform.domain.knowledge.ports import EmbeddingProvider


class EmbeddingProviderContract:
    """Behavioural invariants every ``EmbeddingProvider`` must satisfy."""

    @pytest.fixture
    def provider(self) -> EmbeddingProvider:
        """The provider under test. Subclasses MUST override this."""
        raise NotImplementedError("contract subclasses must provide a `provider` fixture")

    async def test_query_embedding_has_declared_dimension(
        self, provider: EmbeddingProvider
    ) -> None:
        vector = await provider.embed_query("hello world")
        assert vector.dimension == provider.capabilities().dimension

    async def test_query_embedding_is_deterministic(self, provider: EmbeddingProvider) -> None:
        first = await provider.embed_query("the quick brown fox")
        second = await provider.embed_query("the quick brown fox")
        assert first == second

    async def test_distinct_texts_produce_distinct_vectors(
        self, provider: EmbeddingProvider
    ) -> None:
        a = await provider.embed_query("apples and oranges")
        b = await provider.embed_query("quantum chromodynamics")
        assert a != b

    async def test_embed_documents_returns_one_vector_per_input(
        self, provider: EmbeddingProvider
    ) -> None:
        texts = ["first document", "second document", "third document"]
        vectors = await provider.embed_documents(texts)
        assert len(vectors) == len(texts)
        dimension = provider.capabilities().dimension
        assert all(vector.dimension == dimension for vector in vectors)

    async def test_embed_documents_is_deterministic(self, provider: EmbeddingProvider) -> None:
        texts = ["alpha", "beta"]
        assert await provider.embed_documents(texts) == await provider.embed_documents(texts)

    async def test_embed_documents_empty_returns_empty(self, provider: EmbeddingProvider) -> None:
        assert await provider.embed_documents([]) == []

    def test_capabilities_are_pure_and_consistent(self, provider: EmbeddingProvider) -> None:
        first = provider.capabilities()
        second = provider.capabilities()
        assert first == second  # deterministic, no hidden I/O
        assert first.dimension > 0
        assert first.model
