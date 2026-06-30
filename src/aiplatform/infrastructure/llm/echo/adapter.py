"""Echo provider — the reference ``LLMProvider`` implementation (ADR-0004).

``EchoProvider`` streams back a deterministic, token-by-token echo of the last
user message. It performs **no network I/O**, reports stub capabilities and
token usage, and exists to:

* prove the port is genuinely provider-agnostic (two passing implementations),
* enable fast, offline, deterministic tests of every layer above the provider.

It is wired only in local/test environments (the composition root, M1.5).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import ClassVar

from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk, FinishReason, TokenUsage

# Splits text into alternating runs of whitespace and non-whitespace, so that
# "".join(tokens) reconstructs the original input exactly (round-trip safe).
_TOKEN_PATTERN = re.compile(r"\s+|\S+")


class EchoProvider(LLMProvider):
    """A deterministic, offline provider that echoes the last user message.

    Args:
        model: The model identifier reported by this provider.
    """

    #: Registry key under which the composition root registers this provider.
    NAME: ClassVar[str] = "echo"

    def __init__(self, model: str = "echo") -> None:
        """Initialise the provider with the model identifier it reports."""
        self._model = model

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        """Stream the last user message back, one token at a time.

        Yields each token (word or whitespace run) as a non-final chunk, then a
        single terminal chunk carrying stub usage and a ``STOP`` finish reason.
        Always yields at least the terminal chunk, even for empty input.
        """
        text = self._text_to_echo(request)
        tokens = _TOKEN_PATTERN.findall(text)
        word_count = sum(1 for token in tokens if not token.isspace())

        for token in tokens:
            yield CompletionChunk(delta=token)
        yield CompletionChunk(
            delta="",
            is_final=True,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(prompt_tokens=word_count, completion_tokens=word_count),
        )

    def capabilities(self) -> ProviderCapabilities:
        """Return stub capabilities (pure, no I/O).

        Echo streams but ignores the system prompt and does not report real token
        usage, and so declares those honestly.
        """
        return ProviderCapabilities(
            model=self._model,
            supports_streaming=True,
            supports_system_prompt=False,
            reports_token_usage=False,
            max_context_tokens=None,
        )

    @staticmethod
    def _text_to_echo(request: CompletionRequest) -> str:
        """Return the text to echo: the last user message, or empty if none."""
        last_user = request.last_user_message
        return last_user.content if last_user is not None else ""
