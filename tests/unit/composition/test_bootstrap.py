"""Unit tests for the bootstrap lifecycle hooks (M1.5)."""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.composition.bootstrap import bootstrap, shutdown
from aiplatform.composition.container import Container
from aiplatform.infrastructure.config.settings import AppSettings
from aiplatform.infrastructure.llm.echo.adapter import EchoProvider


def _settings() -> AppSettings:
    return AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        env="local",  # type: ignore[arg-type]
        llm={"default_provider": "echo"},
    )


async def test_bootstrap_returns_ready_container() -> None:
    container = bootstrap(_settings())
    try:
        assert isinstance(container, Container)
        assert isinstance(container.registry.get_default(), EchoProvider)
        assert container.settings.is_local
    finally:
        await shutdown(container)


async def test_shutdown_releases_resources() -> None:
    container = bootstrap(_settings())
    ollama = container.registry.get("ollama")
    await shutdown(container)
    assert ollama._client.is_closed is True  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()
