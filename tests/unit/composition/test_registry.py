"""Unit tests for the concrete DictProviderRegistry (M1.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from aiplatform.application.llm.provider_registry import ProviderNotFoundError
from aiplatform.composition.registry import DictProviderRegistry
from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk


class _Stub(LLMProvider):
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


def _registry(default: str = "echo") -> DictProviderRegistry:
    return DictProviderRegistry(
        {"echo": _Stub("echo"), "ollama": _Stub("ollama")}, default_name=default
    )


def test_get_returns_named_provider() -> None:
    assert _registry().get("ollama").capabilities().model == "ollama"


def test_get_default_uses_configured_default() -> None:
    assert _registry(default="ollama").get_default().capabilities().model == "ollama"


def test_names_are_sorted() -> None:
    assert _registry().names == ("echo", "ollama")


def test_unknown_name_raises() -> None:
    with pytest.raises(ProviderNotFoundError):
        _registry().get("missing")


def test_missing_default_fails_fast_at_construction() -> None:
    with pytest.raises(ProviderNotFoundError):
        DictProviderRegistry({"ollama": _Stub("ollama")}, default_name="echo")


def test_empty_registry_fails_fast() -> None:
    with pytest.raises(ProviderNotFoundError):
        DictProviderRegistry({}, default_name="echo")
