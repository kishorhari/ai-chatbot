"""Context-window selection (ADR-0009).

Selects which conversation messages fit the model's context budget *before* a
request is assembled. The strategy is deterministic: always keep a leading system
message, then include the most recent messages, dropping the oldest that do not
fit — recency wins, because the latest turn matters most.

A single concrete strategy for now, not a port: per the project's
no-speculative-abstraction rule (and the ADR-0010 stance that we do not add
interfaces without a second implementation), a policy *port* is extracted only if
a genuinely different strategy appears (e.g. summarizing memory, M3+). This is a
**pure** component — no I/O, recall, persistence, or provider call — configured
with a :class:`TokenEstimator` and two budget margins.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role

from .token_estimator import TokenEstimator


class ContextWindowPolicy:
    """Chooses the messages that fit a model's context budget.

    The budget is ``max_context_tokens - response_reservation_tokens``; the
    reservation leaves room for the model's reply. Each message is charged its
    estimated content tokens plus a fixed per-message overhead (role/framing).
    """

    def __init__(
        self,
        estimator: TokenEstimator,
        *,
        response_reservation_tokens: int = 256,
        per_message_overhead_tokens: int = 4,
    ) -> None:
        """Configure the policy.

        Args:
            estimator: How message token costs are estimated.
            response_reservation_tokens: Tokens held back from the context budget
                for the model's response. Must be non-negative.
            per_message_overhead_tokens: Fixed tokens added per message for
                role/formatting framing. Must be non-negative.

        Raises:
            ValueError: If either margin is negative.
        """
        if response_reservation_tokens < 0:
            raise ValueError("response_reservation_tokens must be non-negative")
        if per_message_overhead_tokens < 0:
            raise ValueError("per_message_overhead_tokens must be non-negative")
        self._estimator = estimator
        self._response_reservation_tokens = response_reservation_tokens
        self._per_message_overhead_tokens = per_message_overhead_tokens

    def select(
        self, messages: Sequence[Message], *, max_context_tokens: int | None
    ) -> tuple[Message, ...]:
        """Return the windowed subset of ``messages`` that fits the budget.

        Behaviour:

        * An empty history returns empty.
        * When ``max_context_tokens`` is ``None`` (unknown budget), no windowing
          is applied and every message is returned in order.
        * Otherwise a leading system message is always kept, then the most recent
          messages are included while they fit; older messages that do not fit are
          dropped. Original order is preserved.

        The estimated total never exceeds the budget, with one documented
        exception: if the mandatory minimum (a lone message, or a system message)
        already exceeds the budget — a misconfiguration — that single message is
        still returned, because a request must contain at least one message.

        Args:
            messages: The full conversation history, in order.
            max_context_tokens: The model's context window, or ``None`` if unknown.

        Returns:
            The selected messages, in their original order.
        """
        if not messages:
            return ()
        if max_context_tokens is None:
            return tuple(messages)

        budget = max_context_tokens - self._response_reservation_tokens
        has_system = messages[0].role is Role.SYSTEM
        system = messages[0] if has_system else None
        body = list(messages[1:]) if has_system else list(messages)

        remaining = budget - (self._cost(system) if system is not None else 0)
        kept: list[Message] = []
        for message in reversed(body):
            cost = self._cost(message)
            if cost <= remaining:
                kept.append(message)
                remaining -= cost
            else:
                break  # oldest-first: this message and everything older is dropped
        kept.reverse()

        result = ([system] if system is not None else []) + kept
        if not result:
            # A request must be non-empty: return the most recent message even if
            # it alone exceeds the budget (documented, degenerate/misconfig case).
            result = [messages[-1]]
        return tuple(result)

    def _cost(self, message: Message) -> int:
        """Estimated token cost of a message, including per-message overhead."""
        return self._estimator.estimate(message.content) + self._per_message_overhead_tokens
