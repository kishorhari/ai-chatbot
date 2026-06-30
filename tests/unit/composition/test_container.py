"""Unit tests for the composition container and provider wiring (M1.5).

Key assertions: providers are wired per environment, and switching the active
provider is a *configuration-only* change (roadmap §5 exit criterion 7).
"""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.application.llm.provider_registry import ProviderNotFoundError
from aiplatform.composition.container import build_container
from aiplatform.infrastructure.config.settings import AppSettings
from aiplatform.infrastructure.llm.echo.adapter import EchoProvider
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider


def _settings(*, env: str, default_provider: str) -> AppSettings:
    return AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        env=env,  # type: ignore[arg-type]
        llm={"default_provider": default_provider},
    )


async def test_local_env_wires_both_providers_with_ollama_default() -> None:
    container = build_container(_settings(env="local", default_provider="ollama"))
    try:
        assert set(container.registry.names) == {"echo", "ollama"}  # type: ignore[attr-defined]
        assert isinstance(container.registry.get_default(), OllamaProvider)
        assert isinstance(container.registry.get("echo"), EchoProvider)
    finally:
        await container.aclose()


async def test_production_wires_only_ollama() -> None:
    container = build_container(_settings(env="production", default_provider="ollama"))
    try:
        assert container.registry.names == ("ollama",)  # type: ignore[attr-defined]
        assert isinstance(container.registry.get_default(), OllamaProvider)
        with pytest.raises(ProviderNotFoundError):
            container.registry.get("echo")
    finally:
        await container.aclose()


async def test_provider_swap_is_configuration_only() -> None:
    """Same code path; only the config differs -> different default provider."""
    ollama_container = build_container(_settings(env="local", default_provider="ollama"))
    echo_container = build_container(_settings(env="local", default_provider="echo"))
    try:
        assert isinstance(ollama_container.registry.get_default(), OllamaProvider)
        assert isinstance(echo_container.registry.get_default(), EchoProvider)
    finally:
        await ollama_container.aclose()
        await echo_container.aclose()


async def test_default_provider_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """AIP__LLM__DEFAULT_PROVIDER=echo selects Echo with no code change."""
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    container = build_container()  # loads settings from the environment
    try:
        assert isinstance(container.registry.get_default(), EchoProvider)
    finally:
        await container.aclose()


def test_echo_default_in_production_fails_fast() -> None:
    """Echo is not wired in production, so selecting it aborts startup."""
    with pytest.raises(ProviderNotFoundError):
        build_container(_settings(env="production", default_provider="echo"))


async def test_aclose_closes_owned_ollama_client() -> None:
    container = build_container(_settings(env="production", default_provider="ollama"))
    ollama = container.registry.get("ollama")
    await container.aclose()
    # The owned httpx client is closed; aclose is also idempotent.
    assert ollama._client.is_closed is True  # type: ignore[attr-defined]
    await container.aclose()


def test_container_exposes_settings() -> None:
    settings = _settings(env="staging", default_provider="ollama")
    container = build_container(settings)
    assert container.settings is settings


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    """build_container configures global logging; restore defaults afterwards."""
    import structlog

    yield
    structlog.reset_defaults()
