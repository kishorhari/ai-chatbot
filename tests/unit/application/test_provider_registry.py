"""Unit tests for the ProviderRegistry port (M1.2-c)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from aiplatform.application.llm.provider_registry import (
    ProviderNotFoundError,
    ProviderRegistry,
)
from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.errors import LLMError
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk


class _StubProvider(LLMProvider):
    def __init__(self, name: str) -> None:
        self._name = name

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta="", is_final=True)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model=self._name,
            supports_streaming=True,
            supports_system_prompt=False,
            reports_token_usage=False,
        )


class _DictRegistry(ProviderRegistry):
    """Tiny test double standing in for the M1.5 concrete registry."""

    def __init__(self, providers: dict[str, LLMProvider], default: str) -> None:
        self._providers = providers
        self._default = default

    @property
    def default_name(self) -> str:
        return self._default

    def get(self, name: str) -> LLMProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderNotFoundError(f"no provider registered as {name!r}") from exc


def _registry() -> _DictRegistry:
    return _DictRegistry({"echo": _StubProvider("echo"), "ollama": _StubProvider("ollama")}, "echo")


def test_registry_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ProviderRegistry()  # type: ignore[abstract]


def test_get_returns_named_provider() -> None:
    assert _registry().get("ollama").capabilities().model == "ollama"


def test_get_default_uses_default_name() -> None:
    assert _registry().get_default().capabilities().model == "echo"


def test_get_unknown_raises_provider_not_found() -> None:
    with pytest.raises(ProviderNotFoundError):
        _registry().get("nope")


def test_provider_not_found_is_an_llm_error_and_non_retryable() -> None:
    error = ProviderNotFoundError("missing")
    assert isinstance(error, LLMError)
    assert error.retryable is False


def test_get_default_propagates_when_default_missing() -> None:
    registry = _DictRegistry({"echo": _StubProvider("echo")}, default="ollama")
    with pytest.raises(ProviderNotFoundError):
        registry.get_default()
