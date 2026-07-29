"""PromptEnricher — inject retrieved context into a turn's messages (ADR-0015).

A **pure** component (no I/O, retrieval, persistence, or provider call): given the
windowed conversation messages and a ``RetrievedContext``, it returns an augmented,
**ephemeral** message sequence for the request only — the conversation aggregate is
never touched.

Invariants it upholds:

* **Single leading system message.** Retrieved passages are merged into the
  existing leading system message (or a synthetic one is prepended when none
  exists), never added as a second system message (ADR-0007/0009).
* **Budget safety.** The injected context is capped so the estimated prompt never
  exceeds ``max_context_tokens`` (when known), packing highest-scoring passages
  first and dropping the rest. Token costs are measured with the M2
  ``TokenEstimator``.

Being pure and deterministic, it is trivially unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiplatform.application.conversation.token_estimator import TokenEstimator
from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.knowledge.retrieval import RetrievedContext
from aiplatform.domain.llm.messages import Role

_PREAMBLE = "Use the following retrieved context to answer the user's question:"


class PromptEnricher:
    """Merges retrieved context into a turn's leading system message."""

    def __init__(self, estimator: TokenEstimator, *, context_token_budget: int = 1024) -> None:
        """Configure the maximum tokens of context to inject.

        Raises:
            ValueError: If ``context_token_budget`` is negative.
        """
        if context_token_budget < 0:
            raise ValueError("context_token_budget must be non-negative")
        self._estimator = estimator
        self._budget = context_token_budget

    def enrich(
        self,
        messages: Sequence[Message],
        context: RetrievedContext,
        *,
        max_context_tokens: int | None = None,
    ) -> tuple[Message, ...]:
        """Return the messages with a context block merged into the system message.

        Returns the messages unchanged when there is no context or no budget for it.
        """
        ordered = tuple(messages)
        if context.is_empty:
            return ordered

        budget = self._resolve_budget(ordered, max_context_tokens)
        block = self._build_block(context, budget)
        if not block:
            return ordered
        return self._inject(ordered, block)

    def _resolve_budget(self, messages: Sequence[Message], max_context_tokens: int | None) -> int:
        """Cap the context budget so the estimated prompt stays within the window."""
        if max_context_tokens is None:
            return self._budget
        used = sum(self._estimator.estimate(message.content) for message in messages)
        return max(0, min(self._budget, max_context_tokens - used))

    def _build_block(self, context: RetrievedContext, budget: int) -> str:
        """Pack highest-scoring passages into a context block within ``budget``."""
        if budget <= 0:
            return ""
        selected: list[str] = []
        used = self._estimator.estimate(_PREAMBLE)
        for chunk in context.chunks:  # already ordered by descending score
            cost = self._estimator.estimate(chunk.text)
            if used + cost > budget:
                continue  # skip this passage; a smaller lower-ranked one may fit
            selected.append(chunk.text)
            used += cost
        if not selected:
            return ""
        return _PREAMBLE + "\n\n" + "\n\n".join(selected)

    @staticmethod
    def _inject(messages: tuple[Message, ...], block: str) -> tuple[Message, ...]:
        """Merge ``block`` into the leading system message, or prepend a new one.

        The augmented system message reuses an existing system message's identity
        and timestamp when present; otherwise a synthetic one borrows a timestamp
        from the first message (the assembler reads only role and content, so the
        synthetic id/time are inert).
        """
        first = messages[0]
        if first.role is Role.SYSTEM:
            merged = Message(
                id=first.id,
                role=Role.SYSTEM,
                content=f"{first.content}\n\n{block}",
                sequence=first.sequence,
                created_at=first.created_at,
                usage=first.usage,
            )
            return (merged, *messages[1:])
        synthetic = Message(
            id=MessageId.generate(),
            role=Role.SYSTEM,
            content=block,
            sequence=0,
            created_at=first.created_at,
        )
        return (synthetic, *messages)
