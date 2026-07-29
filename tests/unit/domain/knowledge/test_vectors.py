"""Unit tests for the EmbeddingVector value object (M3.0)."""

from __future__ import annotations

import math

import pytest

from aiplatform.domain.knowledge.vectors import EmbeddingVector


def test_dimension_reflects_length() -> None:
    assert EmbeddingVector((1.0, 2.0, 3.0)).dimension == 3


def test_empty_vector_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one dimension"):
        EmbeddingVector(())


def test_identical_vectors_have_similarity_one() -> None:
    vector = EmbeddingVector((1.0, 2.0, 2.0))
    assert math.isclose(vector.cosine_similarity(vector), 1.0)


def test_orthogonal_vectors_have_similarity_zero() -> None:
    a = EmbeddingVector((1.0, 0.0))
    b = EmbeddingVector((0.0, 1.0))
    assert math.isclose(a.cosine_similarity(b), 0.0)


def test_opposite_vectors_have_similarity_minus_one() -> None:
    a = EmbeddingVector((1.0, 1.0))
    b = EmbeddingVector((-1.0, -1.0))
    assert math.isclose(a.cosine_similarity(b), -1.0)


def test_zero_vector_similarity_is_zero_not_error() -> None:
    a = EmbeddingVector((0.0, 0.0))
    b = EmbeddingVector((1.0, 1.0))
    assert a.cosine_similarity(b) == 0.0


def test_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="dimension mismatch"):
        EmbeddingVector((1.0, 2.0)).cosine_similarity(EmbeddingVector((1.0,)))


def test_vector_is_immutable_and_hashable() -> None:
    vector = EmbeddingVector((1.0, 2.0))
    assert hash(vector) == hash(EmbeddingVector((1.0, 2.0)))
    with pytest.raises(AttributeError):
        vector.values = (3.0,)  # type: ignore[misc]
