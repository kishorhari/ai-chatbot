"""Unit tests for knowledge/RAG configuration (M3.6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.infrastructure.config.settings import (
    AppSettings,
    EmbeddingBackend,
    VectorBackend,
)


def _settings(**kwargs: object) -> AppSettings:
    return AppSettings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_defaults_are_disabled_fake_and_memory() -> None:
    knowledge = _settings().knowledge
    assert knowledge.enabled is False
    assert knowledge.embedding.backend is EmbeddingBackend.FAKE
    assert knowledge.vector.backend is VectorBackend.MEMORY
    assert knowledge.retrieval.k == 5


def test_enabled_and_backends_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__KNOWLEDGE__ENABLED", "true")
    monkeypatch.setenv("AIP__KNOWLEDGE__EMBEDDING__BACKEND", "ollama")
    monkeypatch.setenv("AIP__KNOWLEDGE__VECTOR__BACKEND", "pgvector")
    monkeypatch.setenv("AIP__KNOWLEDGE__RETRIEVAL__K", "8")
    knowledge = _settings().knowledge
    assert knowledge.enabled is True
    assert knowledge.embedding.backend is EmbeddingBackend.OLLAMA
    assert knowledge.vector.backend is VectorBackend.PGVECTOR
    assert knowledge.retrieval.k == 8


def test_invalid_backend_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__KNOWLEDGE__VECTOR__BACKEND", "faiss")
    with pytest.raises(ValidationError):
        _settings()


def test_chunk_overlap_must_be_below_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__KNOWLEDGE__CHUNK__SIZE_TOKENS", "100")
    monkeypatch.setenv("AIP__KNOWLEDGE__CHUNK__OVERLAP_TOKENS", "100")
    with pytest.raises(ValidationError):
        _settings()


def test_min_score_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__KNOWLEDGE__RETRIEVAL__MIN_SCORE", "2.0")
    with pytest.raises(ValidationError):
        _settings()
