"""Unit tests for FakeEmbeddingProvider specifics beyond the contract (M3.1)."""

from __future__ import annotations

from math import sqrt

import pytest

from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider


async def test_vectors_are_l2_normalised() -> None:
    vector = await FakeEmbeddingProvider(dimension=128).embed_query("hello world")
    magnitude = sqrt(sum(value * value for value in vector.values))
    assert abs(magnitude - 1.0) < 1e-9


async def test_shared_words_are_more_similar_than_disjoint() -> None:
    provider = FakeEmbeddingProvider(dimension=512)
    a = await provider.embed_query("machine learning models")
    shared = await provider.embed_query("machine learning systems")
    disjoint = await provider.embed_query("banana bread recipe")
    assert a.cosine_similarity(shared) > a.cosine_similarity(disjoint)


async def test_is_case_insensitive_on_tokens() -> None:
    provider = FakeEmbeddingProvider(dimension=64)
    assert await provider.embed_query("Hello") == await provider.embed_query("hello")


async def test_reported_dimension_matches_output() -> None:
    provider = FakeEmbeddingProvider(dimension=32, model="fake-32")
    caps = provider.capabilities()
    assert caps.dimension == 32
    assert caps.model == "fake-32"
    assert (await provider.embed_query("x")).dimension == 32


def test_non_positive_dimension_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        FakeEmbeddingProvider(dimension=0)
