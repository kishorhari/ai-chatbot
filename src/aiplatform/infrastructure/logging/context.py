"""Correlation-id propagation via a context variable.

A correlation id ties every log record produced while handling a single request
(or CLI invocation) to that request. It lives in a :class:`contextvars.ContextVar`
so it propagates automatically across ``await`` boundaries and stays isolated
between concurrent tasks — no thread-locals, no manual plumbing through call
signatures.

This module is pure standard library (rule 22 / dependency matrix): it imports
nothing else from the project and must stay that way so it can be used by the
logging setup without creating a cycle.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

#: Key under which the correlation id is emitted in structured log records.
CORRELATION_ID_FIELD = "correlation_id"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def generate_correlation_id() -> str:
    """Return a new, unique correlation id (a 32-char hex token)."""
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    """Return the correlation id bound to the current context, or ``None``."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> Token[str | None]:
    """Bind a correlation id to the current context.

    Args:
        correlation_id: The value to bind.

    Returns:
        A reset token; pass it to :func:`reset_correlation_id` to restore the
        previous value.
    """
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation id to the value captured in ``token``."""
    _correlation_id.reset(token)


@contextmanager
def correlation_id_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of a ``with`` block.

    Generates a fresh id when none is supplied, then restores the previous
    context value on exit (even if the block raises).

    Args:
        correlation_id: An explicit id to bind; a new one is generated if omitted.

    Yields:
        The correlation id that was bound.
    """
    cid = correlation_id or generate_correlation_id()
    token = set_correlation_id(cid)
    try:
        yield cid
    finally:
        reset_correlation_id(token)
