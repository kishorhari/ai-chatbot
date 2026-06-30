"""Unit tests for request value objects (M1.2-a)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest, GenerationParams


def test_generation_params_default_to_provider_defaults() -> None:
    params = GenerationParams()
    assert params.temperature is None
    assert params.top_p is None
    assert params.max_tokens is None
    assert params.stop == ()
    assert params.seed is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"top_p": 0.0},
        {"top_p": 1.1},
        {"max_tokens": 0},
    ],
)
def test_generation_params_reject_out_of_range(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        GenerationParams(**kwargs)


def test_request_requires_at_least_one_message() -> None:
    with pytest.raises(ValidationError):
        CompletionRequest(messages=())


def test_request_coerces_message_list_to_tuple() -> None:
    request = CompletionRequest(messages=[ChatMessage.user("hi")])
    assert isinstance(request.messages, tuple)


def test_request_is_immutable() -> None:
    request = CompletionRequest(messages=(ChatMessage.user("hi"),))
    with pytest.raises(ValidationError):
        request.model = "other"  # type: ignore[misc]


def test_last_user_message_returns_most_recent_user_turn() -> None:
    request = CompletionRequest(
        messages=(
            ChatMessage.system("be brief"),
            ChatMessage.user("first"),
            ChatMessage.assistant("reply"),
            ChatMessage.user("second"),
        )
    )
    last = request.last_user_message
    assert last is not None
    assert last.content == "second"


def test_last_user_message_is_none_without_user_turn() -> None:
    request = CompletionRequest(messages=(ChatMessage.system("only system"),))
    assert request.last_user_message is None
