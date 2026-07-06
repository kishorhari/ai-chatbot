"""Unit tests for the Clock port seam (reserved ahead of M2.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.application.clock import Clock


class _FixedClock:
    """A minimal conforming test double — structural, no inheritance."""

    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when


def test_conforming_object_satisfies_the_protocol() -> None:
    clock: Clock = _FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    assert isinstance(clock, Clock)
    assert clock.now().tzinfo is not None


def test_object_without_now_does_not_satisfy_the_protocol() -> None:
    assert not isinstance(object(), Clock)
