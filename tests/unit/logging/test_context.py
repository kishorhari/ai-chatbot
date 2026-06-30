"""Unit tests for correlation-id context propagation (M1.1-b)."""

from __future__ import annotations

from aiplatform.infrastructure.logging.context import (
    correlation_id_scope,
    generate_correlation_id,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


def test_default_is_none() -> None:
    assert get_correlation_id() is None


def test_generate_returns_unique_hex_tokens() -> None:
    first = generate_correlation_id()
    second = generate_correlation_id()
    assert first != second
    assert len(first) == 32
    assert int(first, 16) >= 0  # valid hex


def test_set_and_reset_restores_previous_value() -> None:
    assert get_correlation_id() is None
    token = set_correlation_id("abc123")
    assert get_correlation_id() == "abc123"
    reset_correlation_id(token)
    assert get_correlation_id() is None


def test_scope_binds_then_clears() -> None:
    with correlation_id_scope("req-1") as cid:
        assert cid == "req-1"
        assert get_correlation_id() == "req-1"
    assert get_correlation_id() is None


def test_scope_generates_id_when_absent() -> None:
    with correlation_id_scope() as cid:
        assert cid
        assert get_correlation_id() == cid


def test_scope_clears_even_on_exception() -> None:
    try:
        with correlation_id_scope("req-err"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert get_correlation_id() is None


def test_nested_scopes_restore_outer_value() -> None:
    with correlation_id_scope("outer"):
        with correlation_id_scope("inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"
    assert get_correlation_id() is None
