"""Prompt assembly — a pure ``CompletionRequest`` builder (ADR-0009, ADR-0010).

Given already-resolved (windowed) conversation messages and generation params,
produce a ``CompletionRequest``. This is the single place stored ``Message``
history is mapped onto the transport ``ChatMessage``, and the single place prompt
invariants (non-empty, at most one system message, and only as the first message)
are enforced before a request reaches a provider.

It is a **pure builder** (ADR-0010): no recall, no persistence, no provider call,
no transaction, and no windowing. The application service selects the window (via
:class:`ContextWindowPolicy`) and hands the resolved messages here; keeping
assembly free of orchestration is the boundary ADR-0010 protects.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import ChatMessage, Role
from aiplatform.domain.llm.requests import CompletionRequest, GenerationParams


class PromptAssembler:
    """Builds a ``CompletionRequest`` from resolved conversation messages."""

    def assemble(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        params: GenerationParams | None = None,
    ) -> CompletionRequest:
        """Map resolved messages onto a provider request.

        Args:
            messages: The already-resolved (windowed) conversation messages, in
                order. Must be non-empty.
            model: Optional per-request model override; ``None`` defers to the
                provider's configured model (M1 semantics).
            params: Generation tuning; defaults to the provider's own defaults.

        Returns:
            A :class:`CompletionRequest` whose messages are the transport
            ``ChatMessage`` projection of the inputs.

        Raises:
            ValueError: If ``messages`` is empty, or a system message appears
                anywhere other than the first position.
        """
        if not messages:
            raise ValueError("cannot assemble a request from an empty message list")
        self._validate_system_placement(messages)
        chat_messages = tuple(ChatMessage(role=m.role, content=m.content) for m in messages)
        return CompletionRequest(
            messages=chat_messages,
            model=model,
            params=params if params is not None else GenerationParams(),
        )

    @staticmethod
    def _validate_system_placement(messages: Sequence[Message]) -> None:
        """Enforce that a system message, if any, is only the first message."""
        for index, message in enumerate(messages):
            if message.role is Role.SYSTEM and index != 0:
                raise ValueError("a system message may only be the first message")
