"""Unit tests for context-window selection (M2.2).

A fake estimator (one token per character, zero overhead/reservation unless
stated) makes the token arithmetic explicit and decouples these tests from the
heuristic estimator's rounding.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from aiplatform.application.conversation.context_window import ContextWindowPolicy
from aiplatform.application.conversation.token_estimator import TokenEstimator
from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.llm.messages import Role

_WHEN = datetime(2026, 1, 1, tzinfo=UTC)


class _CharCountEstimator(TokenEstimator):
    """One token per character — makes budget arithmetic exact in tests."""

    def estimate(self, text: str) -> int:
        return len(text)


def _history(*specs: tuple[str, str]) -> tuple[Message, ...]:
    """Build an ordered history from (role, content) specs via the aggregate."""
    convo = Conversation.start(owner="u", created_at=_WHEN)
    for role, content in specs:
        if role == "system":
            convo.append_system(content, created_at=_WHEN)
        elif role == "user":
            convo.append_user(content, created_at=_WHEN)
        else:
            convo.append_assistant(content, created_at=_WHEN)
    return convo.messages


def _policy(**overrides: int) -> ContextWindowPolicy:
    kwargs: dict[str, int] = {"response_reservation_tokens": 0, "per_message_overhead_tokens": 0}
    kwargs.update(overrides)
    return ContextWindowPolicy(_CharCountEstimator(), **kwargs)


def _contents(messages: Sequence[Message]) -> list[str]:
    return [m.content for m in messages]


def test_rejects_negative_reservation() -> None:
    with pytest.raises(ValueError, match="response_reservation_tokens"):
        ContextWindowPolicy(_CharCountEstimator(), response_reservation_tokens=-1)


def test_rejects_negative_overhead() -> None:
    with pytest.raises(ValueError, match="per_message_overhead_tokens"):
        ContextWindowPolicy(_CharCountEstimator(), per_message_overhead_tokens=-1)


def test_empty_history_returns_empty() -> None:
    assert _policy().select((), max_context_tokens=100) == ()


def test_no_budget_returns_all_messages() -> None:
    history = _history(("system", "S"), ("user", "AAAA"), ("assistant", "BBBB"))
    assert _policy().select(history, max_context_tokens=None) == history


def test_returns_all_when_within_budget() -> None:
    history = _history(("system", "S"), ("user", "AA"), ("assistant", "BBB"))
    # total cost = 1 + 2 + 3 = 6
    assert _policy().select(history, max_context_tokens=100) == history


def test_drops_oldest_and_keeps_system_plus_recent() -> None:
    history = _history(("system", "S"), ("user", "AA"), ("assistant", "BBB"), ("user", "CCCC"))
    # costs: S=1, AA=2, BBB=3, CCCC=4; budget=8 -> keep S(1)+BBB(3)+CCCC(4)=8, drop AA
    selected = _policy().select(history, max_context_tokens=8)
    assert _contents(selected) == ["S", "BBB", "CCCC"]


def test_system_message_is_always_retained() -> None:
    history = _history(("system", "SYSTEM"), ("user", "AAAA"), ("user", "BBBB"))
    selected = _policy().select(history, max_context_tokens=5)  # tight
    assert selected[0].role is Role.SYSTEM


def test_never_exceeds_budget_for_normal_case() -> None:
    history = _history(("system", "S"), ("user", "AA"), ("assistant", "BBB"), ("user", "CCCC"))
    budget = 8
    selected = _policy().select(history, max_context_tokens=budget)
    assert sum(len(m.content) for m in selected) <= budget


def test_reservation_reduces_the_effective_budget() -> None:
    history = _history(("user", "AAAA"), ("user", "BBBB"))  # costs 4, 4
    # max=8, reservation=4 -> budget=4 -> only the newest (BBBB) fits
    selected = _policy(response_reservation_tokens=4).select(history, max_context_tokens=8)
    assert _contents(selected) == ["BBBB"]


def test_per_message_overhead_is_charged() -> None:
    history = _history(("user", "AA"), ("user", "BB"))  # content 2 each
    # overhead=3 -> each message costs 5; budget=6 -> only one fits
    selected = _policy(per_message_overhead_tokens=3).select(history, max_context_tokens=6)
    assert _contents(selected) == ["BB"]


def test_preserves_original_order() -> None:
    history = _history(("user", "A"), ("assistant", "B"), ("user", "C"))
    selected = _policy().select(history, max_context_tokens=100)
    assert _contents(selected) == ["A", "B", "C"]


def test_guarantees_at_least_the_newest_message() -> None:
    history = _history(("user", "XXXX"))  # cost 4, no system
    selected = _policy().select(history, max_context_tokens=2)  # nothing fits
    assert _contents(selected) == ["XXXX"]  # newest returned despite over budget
