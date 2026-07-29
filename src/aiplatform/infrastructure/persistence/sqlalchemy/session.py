"""Async session/transaction management shared by the repository and boundary.

The SQLAlchemy transaction boundary and repository must operate on the **same**
session inside an ``atomic()`` scope (ADR-0008: session-per-scope). This provider
owns the engine and session factory and coordinates that sharing through a
context variable:

* :meth:`transaction` opens one session, begins a transaction, and publishes it on
  the context variable for the duration of the scope — committing on clean exit
  and rolling back on any exception.
* :meth:`session` yields the ambient transactional session when one is active
  (so a repository write inside ``atomic()`` joins that transaction), or otherwise
  opens its own short session+transaction for a standalone read or write.

Using a context variable keeps the sharing implicit and async-safe without
threading a session through every call signature.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class SessionProvider:
    """Owns the async engine and coordinates session/transaction scoping."""

    def __init__(self, engine: AsyncEngine) -> None:
        """Build a session factory over ``engine``."""
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        self._current: ContextVar[AsyncSession | None] = ContextVar(
            "sqlalchemy_current_session", default=None
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Delimit one atomic unit of work (used by the transaction boundary).

        Commits on clean exit; rolls back on any exception (including
        cancellation). Nested use joins the outer transaction.
        """
        if self._current.get() is not None:
            yield  # already inside a transaction; join it
            return
        async with self._sessionmaker() as session:
            token = self._current.set(session)
            try:
                async with session.begin():
                    yield
            finally:
                self._current.reset(token)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session for one repository operation.

        Inside an ``atomic()`` scope this is the ambient transactional session
        (the boundary owns the commit); otherwise it is a fresh session whose
        transaction commits when the block exits cleanly.
        """
        ambient = self._current.get()
        if ambient is not None:
            yield ambient
            return
        async with self._sessionmaker() as session, session.begin():
            yield session

    async def aclose(self) -> None:
        """Dispose of the engine and its connection pool (shutdown)."""
        await self._engine.dispose()
