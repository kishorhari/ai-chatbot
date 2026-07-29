"""SQLAlchemy transaction boundary (ADR-0008).

Implements the application ``TransactionBoundary`` port over a shared
:class:`SessionProvider`: ``atomic()`` opens one session/transaction that the
repository joins for the duration of the scope, committing on clean exit and
rolling back on any exception. This is a genuine transaction — unlike the
in-memory pass-through — so a mid-scope failure leaves no partial write.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from aiplatform.application.conversation.transaction import TransactionBoundary

from .session import SessionProvider


class SqlAlchemyTransactionBoundary(TransactionBoundary):
    """Session-per-scope atomic boundary backed by SQLAlchemy."""

    def __init__(self, provider: SessionProvider) -> None:
        """Store the session provider (shared with the repository)."""
        self._provider = provider

    def atomic(self) -> AbstractAsyncContextManager[None]:
        """Return the shared provider's transaction scope."""
        return self._provider.transaction()
