"""``SystemClock`` — the production implementation of the ``Clock`` port.

The application's single source of "now" (``application/clock.py``) is a port so
use cases stay deterministic; this is the one component that actually reads the
operating-system clock. It lives in infrastructure because reading the wall clock
is an external dependency, exactly like network or storage. Tests inject a fixed
clock instead.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Returns the current UTC time from the operating-system clock.

    Structurally satisfies the :class:`~aiplatform.application.clock.Clock`
    protocol (timezone-aware ``now``); no inheritance is needed.
    """

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC ``datetime``."""
        return datetime.now(UTC)
