"""Unit tests for the token-estimation seam (M2.2)."""

from __future__ import annotations

import pytest

from aiplatform.application.conversation.token_estimator import (
    HeuristicTokenEstimator,
    TokenEstimator,
)


def test_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        TokenEstimator()  # type: ignore[abstract]


def test_estimate_rounds_up_by_the_ratio() -> None:
    est = HeuristicTokenEstimator(chars_per_token=4)
    assert est.estimate("") == 0
    assert est.estimate("a") == 1  # ceil(1/4)
    assert est.estimate("abcd") == 1  # ceil(4/4)
    assert est.estimate("abcde") == 2  # ceil(5/4) — rounds up, never under-counts


def test_estimate_is_nondecreasing_in_length() -> None:
    est = HeuristicTokenEstimator()
    assert est.estimate("x" * 100) >= est.estimate("x" * 10)


def test_ratio_is_configurable() -> None:
    assert HeuristicTokenEstimator(chars_per_token=2).estimate("abcd") == 2


def test_rejects_nonpositive_ratio() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        HeuristicTokenEstimator(chars_per_token=0)
