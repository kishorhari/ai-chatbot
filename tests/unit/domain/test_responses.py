"""Unit tests for response value objects (M1.2-a)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.domain.llm.responses import (
    CompletionChunk,
    CompletionResult,
    FinishReason,
    TokenUsage,
)


def test_total_tokens_is_derived() -> None:
    usage = TokenUsage(prompt_tokens=3, completion_tokens=4)
    assert usage.total_tokens == 7


def test_token_usage_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=-1, completion_tokens=0)


def test_token_usage_empty() -> None:
    usage = TokenUsage.empty()
    assert usage.total_tokens == 0


def test_non_final_chunk_may_not_carry_terminal_fields() -> None:
    with pytest.raises(ValueError, match="non-final chunk"):
        CompletionChunk(delta="x", is_final=False, finish_reason=FinishReason.STOP)
    with pytest.raises(ValueError, match="non-final chunk"):
        CompletionChunk(delta="x", is_final=False, usage=TokenUsage.empty())


def test_final_chunk_may_carry_terminal_fields() -> None:
    chunk = CompletionChunk(
        delta="",
        is_final=True,
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(prompt_tokens=1, completion_tokens=2),
    )
    assert chunk.is_final
    assert chunk.finish_reason is FinishReason.STOP


def test_chunk_is_immutable() -> None:
    chunk = CompletionChunk(delta="a")
    with pytest.raises(AttributeError):
        chunk.delta = "b"  # type: ignore[misc]


def test_from_chunks_concatenates_deltas_and_takes_terminal_metadata() -> None:
    chunks = [
        CompletionChunk(delta="Hel"),
        CompletionChunk(delta="lo"),
        CompletionChunk(
            delta="!",
            is_final=True,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(prompt_tokens=2, completion_tokens=3),
        ),
    ]
    result = CompletionResult.from_chunks(chunks, model="echo")
    assert result.text == "Hello!"
    assert result.model == "echo"
    assert result.finish_reason is FinishReason.STOP
    assert result.usage.total_tokens == 5


def test_from_chunks_requires_a_final_chunk() -> None:
    with pytest.raises(ValueError, match="no final chunk"):
        CompletionResult.from_chunks([CompletionChunk(delta="x")], model="echo")


def test_result_defaults_to_empty_usage() -> None:
    result = CompletionResult(text="hi", model="echo")
    assert result.usage.total_tokens == 0
    assert result.finish_reason is None
