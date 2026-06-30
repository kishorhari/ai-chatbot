"""Unit tests for application settings (M1.1-a).

Covers the testing-strategy requirements for ``settings.py``: fail-fast on
invalid values, nested env-var layering via the ``AIP__`` prefix and ``__``
delimiter, and SecretStr redaction.

Every construction passes ``_env_file=None`` so a developer's local ``.env`` can
never make these tests non-deterministic.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from aiplatform.infrastructure.config.settings import (
    AppSettings,
    Environment,
    LogFormat,
    LogLevel,
    load_settings,
)


def _settings(**_kwargs: object) -> AppSettings:
    """Build settings ignoring any on-disk .env for deterministic tests."""
    return AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_defaults_are_applied() -> None:
    settings = _settings()
    assert settings.env is Environment.LOCAL
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000
    assert settings.logging.level is LogLevel.INFO
    assert settings.logging.format is LogFormat.CONSOLE
    assert settings.llm.default_provider == "ollama"
    assert settings.ollama.base_url == "http://localhost:11434"
    assert settings.ollama.api_key is None


def test_nested_env_override_uses_prefix_and_delimiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIP__ENV", "production")
    monkeypatch.setenv("AIP__SERVER__PORT", "9001")
    monkeypatch.setenv("AIP__LOGGING__FORMAT", "json")
    monkeypatch.setenv("AIP__OLLAMA__MODEL", "qwen2.5:3b")

    settings = _settings()

    assert settings.env is Environment.PRODUCTION
    assert settings.is_production is True
    assert settings.server.port == 9001
    assert settings.logging.format is LogFormat.JSON
    assert settings.ollama.model == "qwen2.5:3b"


def test_default_provider_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "  Echo ")
    assert _settings().llm.default_provider == "echo"


@pytest.mark.parametrize(
    ("env_key", "bad_value"),
    [
        ("AIP__SERVER__PORT", "70000"),  # > 65535
        ("AIP__SERVER__PORT", "0"),  # < 1
        ("AIP__OLLAMA__BASE_URL", "not-a-url"),  # missing scheme/host
        ("AIP__OLLAMA__BASE_URL", "ftp://host"),  # wrong scheme
        ("AIP__OLLAMA__CONNECT_TIMEOUT_SECONDS", "0"),  # not > 0
        ("AIP__OLLAMA__MAX_CONNECT_RETRIES", "-1"),  # not >= 0
        ("AIP__LLM__DEFAULT_PROVIDER", "   "),  # empty after normalization
        ("AIP__ENV", "qa"),  # not a valid Environment
    ],
)
def test_invalid_config_fails_fast_at_load(
    monkeypatch: pytest.MonkeyPatch, env_key: str, bad_value: str
) -> None:
    """Invalid configuration raises at construction, not at request time."""
    monkeypatch.setenv(env_key, bad_value)
    with pytest.raises(ValidationError):
        _settings()


def test_unknown_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """extra='forbid' surfaces typo'd keys instead of silently ignoring them."""
    monkeypatch.setenv("AIP__OLLAMA__BSE_URL", "http://localhost:11434")
    with pytest.raises(ValidationError):
        _settings()


def test_base_url_trailing_slash_is_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIP__OLLAMA__BASE_URL", "http://localhost:11434/")
    assert _settings().ollama.base_url == "http://localhost:11434"


def test_secret_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__OLLAMA__API_KEY", "super-secret-token")
    settings = _settings()

    assert isinstance(settings.ollama.api_key, SecretStr)
    # The raw value is only available via explicit unwrap...
    assert settings.ollama.api_key.get_secret_value() == "super-secret-token"
    # ...and never leaks through str/repr (the logging redaction guarantee).
    assert "super-secret-token" not in str(settings.ollama.api_key)
    assert "super-secret-token" not in repr(settings)


def test_settings_are_immutable() -> None:
    settings = _settings()
    with pytest.raises(ValidationError):
        settings.server.port = 1234  # type: ignore[misc]


def test_load_settings_returns_validated_instance() -> None:
    assert isinstance(load_settings(), AppSettings)
