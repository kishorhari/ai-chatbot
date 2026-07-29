"""Unit test for the SystemClock (M2.4)."""

from __future__ import annotations

from aiplatform.application.clock import Clock
from aiplatform.infrastructure.clock import SystemClock


def test_system_clock_returns_timezone_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    offset = now.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


def test_system_clock_satisfies_clock_protocol() -> None:
    assert isinstance(SystemClock(), Clock)  # runtime_checkable structural conformance
