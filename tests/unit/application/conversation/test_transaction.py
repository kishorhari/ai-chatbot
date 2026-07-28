"""Unit tests for the transaction-boundary port and in-memory impl (M2.3)."""

from __future__ import annotations

import asyncio

import pytest

from aiplatform.application.conversation.transaction import TransactionBoundary
from aiplatform.infrastructure.persistence.memory.transaction import InMemoryTransactionBoundary


def test_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        TransactionBoundary()  # type: ignore[abstract]


async def test_atomic_scope_runs_the_body() -> None:
    boundary = InMemoryTransactionBoundary()
    ran = False
    async with boundary.atomic():
        ran = True
    assert ran


async def test_atomic_scope_propagates_exceptions() -> None:
    boundary = InMemoryTransactionBoundary()
    with pytest.raises(ValueError, match="boom"):
        async with boundary.atomic():
            raise ValueError("boom")


async def test_atomic_scope_propagates_cancellation() -> None:
    boundary = InMemoryTransactionBoundary()
    with pytest.raises(asyncio.CancelledError):
        async with boundary.atomic():
            raise asyncio.CancelledError
