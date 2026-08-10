"""The transaction-boundary port — one atomic unit of work (ADR-0008, ADR-0010).

The application service — not the repository, not delivery — owns *when* work
commits atomically. :meth:`TransactionBoundary.atomic` returns an async context
manager delimiting a single unit of work: the body runs, on clean exit the work
commits, and on **any** exception (including ``asyncio.CancelledError``) it rolls
back and the original, typed error propagates.

In M2 the boundary wraps exactly one write — the end-of-turn conversation
``save`` — because the ChatService design runs generation *outside* the
transaction, so a slow provider call never holds a transaction open. A
multi-aggregate Unit of Work is deliberately deferred (ADR-0008) until a use case
writes more than one aggregate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class TransactionBoundary(ABC):
    """Port delimiting an atomic unit of work."""

    @abstractmethod
    def atomic(self) -> AbstractAsyncContextManager[None]:
        """Return an async context manager for one atomic unit of work.

        The context manager commits the enclosed work on clean exit and rolls it
        back on any exception (including cancellation), re-raising so the caller
        sees the original, typed error unwrapped.
        """
