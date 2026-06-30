"""Unit tests for EchoProvider specifics beyond the shared contract (M1.3)."""

from __future__ import annotations

import pytest

from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import FinishReason
from aiplatform.infrastructure.llm.echo.adapter import EchoProvider


def _request(*messages: ChatMessage) -> CompletionRequest:
    return CompletionRequest(messages=messages)


async def _collect_text(provider: EchoProvider, request: CompletionRequest) -> str:
    return "".join([chunk.delta async for chunk in provider.stream_chat(request)])


async def test_echoes_last_user_message_verbatim() -> None:
    text = "Hello there,  general   kenobi"  # irregular spacing must round-trip
    echoed = await _collect_text(EchoProvider(), _request(ChatMessage.user(text)))
    assert echoed == text


async def test_echoes_the_most_recent_user_message() -> None:
    request = _request(
        ChatMessage.user("first"),
        ChatMessage.assistant("reply"),
        ChatMessage.user("second"),
    )
    assert await _collect_text(EchoProvider(), request) == "second"


async def test_empty_when_no_user_message() -> None:
    request = _request(ChatMessage.system("only system"))
    provider = EchoProvider()
    chunks = [chunk async for chunk in provider.stream_chat(request)]
    assert await _collect_text(provider, request) == ""
    assert len(chunks) == 1
    assert chunks[0].is_final is True


async def test_is_deterministic() -> None:
    request = _request(ChatMessage.user("same input"))
    provider = EchoProvider()
    first = await _collect_text(provider, request)
    second = await _collect_text(provider, request)
    assert first == second == "same input"


async def test_terminal_chunk_reports_stub_usage() -> None:
    request = _request(ChatMessage.user("one two three"))
    chunks = [chunk async for chunk in EchoProvider().stream_chat(request)]
    terminal = chunks[-1]
    assert terminal.finish_reason is FinishReason.STOP
    assert terminal.usage is not None
    assert terminal.usage.completion_tokens == 3


def test_model_defaults_and_is_configurable() -> None:
    assert EchoProvider().capabilities().model == "echo"
    assert EchoProvider(model="echo-v2").capabilities().model == "echo-v2"
    assert EchoProvider.NAME == "echo"


def test_capabilities_declare_stub_behaviour() -> None:
    caps = EchoProvider().capabilities()
    assert caps.supports_streaming is True
    assert caps.supports_system_prompt is False
    assert caps.reports_token_usage is False


async def test_complete_chat_aggregates_echo() -> None:
    request = _request(ChatMessage.user("aggregate me"))
    result = await EchoProvider().complete_chat(request)
    assert result.text == "aggregate me"
    assert result.model == "echo"
    assert result.finish_reason is FinishReason.STOP


@pytest.mark.parametrize("text", ["a", "a b", "  leading", "trailing  ", "multi\nline"])
async def test_tokenization_round_trips(text: str) -> None:
    assert await _collect_text(EchoProvider(), _request(ChatMessage.user(text))) == text
