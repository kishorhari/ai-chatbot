"""Unit tests for the provider capability descriptor (M1.2-a)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.domain.llm.capabilities import ProviderCapabilities


def test_capabilities_are_explicit() -> None:
    caps = ProviderCapabilities(
        model="llama3",
        supports_streaming=True,
        supports_system_prompt=True,
        reports_token_usage=False,
        max_context_tokens=8192,
    )
    assert caps.model == "llama3"
    assert caps.supports_streaming
    assert caps.max_context_tokens == 8192


def test_feature_flags_are_required() -> None:
    with pytest.raises(ValidationError):
        ProviderCapabilities(model="m", supports_streaming=True)  # type: ignore[call-arg]


def test_model_is_required_and_non_empty() -> None:
    with pytest.raises(ValidationError):
        ProviderCapabilities(  # type: ignore[call-arg]
            supports_streaming=True,
            supports_system_prompt=False,
            reports_token_usage=False,
        )
    with pytest.raises(ValidationError):
        ProviderCapabilities(
            model="",
            supports_streaming=True,
            supports_system_prompt=False,
            reports_token_usage=False,
        )


def test_max_context_tokens_optional_but_positive() -> None:
    caps = ProviderCapabilities(
        model="m",
        supports_streaming=True,
        supports_system_prompt=False,
        reports_token_usage=False,
    )
    assert caps.max_context_tokens is None

    with pytest.raises(ValidationError):
        ProviderCapabilities(
            model="m",
            supports_streaming=True,
            supports_system_prompt=False,
            reports_token_usage=False,
            max_context_tokens=0,
        )


def test_capabilities_are_immutable() -> None:
    caps = ProviderCapabilities(
        model="m",
        supports_streaming=True,
        supports_system_prompt=True,
        reports_token_usage=True,
    )
    with pytest.raises(ValidationError):
        caps.supports_streaming = False  # type: ignore[misc]
