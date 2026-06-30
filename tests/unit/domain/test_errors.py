"""Unit tests for the LLM error taxonomy (M1.2-b)."""

from __future__ import annotations

import pytest

from aiplatform.domain.llm.errors import (
    LLMAuthenticationError,
    LLMError,
    LLMModelError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)

_ALL_SUBTYPES = [
    LLMTransportError,
    LLMTimeoutError,
    LLMProtocolError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMModelError,
]


@pytest.mark.parametrize("subtype", _ALL_SUBTYPES)
def test_every_subtype_is_an_llm_error(subtype: type[LLMError]) -> None:
    """All failures can be caught uniformly via the base class."""
    with pytest.raises(LLMError):
        raise subtype("boom")


@pytest.mark.parametrize(
    ("subtype", "expected_retryable"),
    [
        (LLMTransportError, True),
        (LLMTimeoutError, True),
        (LLMRateLimitError, True),
        (LLMProtocolError, False),
        (LLMAuthenticationError, False),
        (LLMModelError, False),
    ],
)
def test_default_retry_disposition(subtype: type[LLMError], expected_retryable: bool) -> None:
    assert subtype("x").retryable is expected_retryable


def test_base_error_is_non_retryable_by_default() -> None:
    assert LLMError("unexpected").retryable is False


def test_retryable_can_be_overridden_per_instance() -> None:
    # A normally-transient error judged non-retryable in a specific situation.
    assert LLMTimeoutError("x", retryable=False).retryable is False
    # And vice versa.
    assert LLMProtocolError("x", retryable=True).retryable is True


def test_cause_is_preserved_and_chained() -> None:
    original = ValueError("vendor-specific failure")
    error = LLMTransportError("could not connect", cause=original)
    assert error.cause is original
    assert error.__cause__ is original


def test_raise_from_sets_cause_chain() -> None:
    original = OSError("connection reset")
    try:
        try:
            raise original
        except OSError as exc:
            raise LLMTransportError("transport failed", cause=exc) from exc
    except LLMTransportError as error:
        assert error.__cause__ is original
        assert error.cause is original


def test_message_is_accessible() -> None:
    error = LLMModelError("unknown model 'foo'")
    assert error.message == "unknown model 'foo'"
    assert str(error) == "unknown model 'foo'"


def test_rate_limit_carries_retry_after() -> None:
    error = LLMRateLimitError("slow down", retry_after=2.5)
    assert error.retry_after == 2.5
    assert error.retryable is True


def test_rate_limit_retry_after_defaults_to_none() -> None:
    assert LLMRateLimitError("throttled").retry_after is None


def test_repr_includes_retryable() -> None:
    text = repr(LLMTimeoutError("timed out"))
    assert "LLMTimeoutError" in text
    assert "retryable=True" in text
