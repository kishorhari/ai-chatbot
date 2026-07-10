"""Token estimation seam for context-window budgeting (ADR-0009).

Windowing needs to know, cheaply and *conservatively*, how many tokens a piece of
text will cost. Exact per-provider tokenization is deliberately deferred behind
this port (ADR-0009); the default is a character-based heuristic that rounds up,
so an estimate never falls below the true count for the modelled ratio — the
budget-safe direction.

Defined as an ABC (like the other genuine seams — ``LLMProvider``,
``ConversationRepository``): a second implementation (an exact tokenizer) is
foreseeable, and the composition root chooses which to wire.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from math import ceil


class TokenEstimator(ABC):
    """Estimates the token cost of a piece of text."""

    @abstractmethod
    def estimate(self, text: str) -> int:
        """Return an estimated, non-negative token count for ``text``."""


class HeuristicTokenEstimator(TokenEstimator):
    """Character-count heuristic (~``chars_per_token`` characters per token).

    Rounds up (``ceil``), so estimates never fall below the true count for the
    modelled ratio — the conservative direction for budget safety (ADR-0009).
    English text averages roughly four characters per token, which the default
    reflects. An exact per-provider tokenizer can replace this behind the port
    when accuracy demonstrably matters.
    """

    def __init__(self, chars_per_token: float = 4.0) -> None:
        """Configure the characters-per-token ratio.

        Args:
            chars_per_token: Average characters modelled per token; must be
                positive.

        Raises:
            ValueError: If ``chars_per_token`` is not positive.
        """
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self._chars_per_token = chars_per_token

    def estimate(self, text: str) -> int:
        """Return ``ceil(len(text) / chars_per_token)``."""
        return ceil(len(text) / self._chars_per_token)
