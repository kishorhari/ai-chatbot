"""The ``Clock`` port — the application's single source of "now".

Time is an external dependency. The conversation domain never reads the system
clock: its entities receive timestamps as explicit, timezone-aware values
(ADR-0007). This port is the seam through which the application layer will obtain
those values once it begins assembling and persisting conversations (M2.3) — so
use cases stay deterministic and testable. Production wiring will supply a system
clock (infrastructure); tests supply a fixed one.

The seam is reserved now, ahead of its first consumer, so the application layer
never has to reach for ``datetime.now()`` directly.

Modelled as a ``Protocol`` rather than the ABC used by the larger ports
(``LLMProvider``, ``ProviderRegistry``): a clock is a trivial, single-method
structural contract, and a Protocol lets lightweight test doubles conform without
inheritance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """A source of the current time.

    Contract:

    * :meth:`now` returns a **timezone-aware** ``datetime`` — never naive; the
      conversation domain rejects naive timestamps.
    * Implementations SHOULD return the time in UTC.
    * :meth:`now` performs no blocking I/O.
    """

    def now(self) -> datetime:
        """Return the current, timezone-aware time."""
        ...
