"""In-memory transaction boundary (ADR-0008).

The in-memory ``ConversationRepository`` makes each ``save`` a single atomic
write, and the ChatService places that ``save`` as the sole, last statement inside
the ``atomic()`` scope. There is therefore nothing to buffer or roll back here: the
scope is a thin, correct pass-through — the body runs, and any exception simply
propagates with storage left unchanged (the failing ``save`` never mutated it).

Real transactional isolation and rollback across multiple writes arrive with the
PostgreSQL boundary (M2.5), where a session/transaction genuinely spans the write.
The port exists so ChatService is persistence-agnostic today, per ADR-0008's
no-speculative-Unit-of-Work stance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiplatform.application.conversation.transaction import TransactionBoundary


class InMemoryTransactionBoundary(TransactionBoundary):
    """A trivial, correct atomic scope for the in-memory backend."""

    @asynccontextmanager
    async def atomic(self) -> AsyncIterator[None]:
        """Yield control; commit on clean exit, propagate on error.

        No buffering is required: the in-memory repository's ``save`` is itself
        atomic and is the only write in the scope, so a failure leaves storage
        unchanged and the exception propagates unwrapped.
        """
        yield
