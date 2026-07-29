"""Unit tests for persistence configuration (M2.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.infrastructure.config.settings import AppSettings, PersistenceBackend


def _settings(**kwargs: object) -> AppSettings:
    return AppSettings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_default_backend_is_memory() -> None:
    assert _settings().persistence.backend is PersistenceBackend.MEMORY


def test_backend_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__PERSISTENCE__BACKEND", "postgres")
    assert _settings().persistence.backend is PersistenceBackend.POSTGRES


def test_invalid_backend_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__PERSISTENCE__BACKEND", "mysql")
    with pytest.raises(ValidationError):
        _settings()
