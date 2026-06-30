"""Run the shared provider contract suite against EchoProvider (M1.3).

Echo passing this identical suite (and, in M1.4, Ollama passing it too) is the
executable proof that the ``LLMProvider`` abstraction is real (ADR-0004).
"""

from __future__ import annotations

import pytest
from provider_contract import LLMProviderContract

from aiplatform.infrastructure.llm.echo.adapter import EchoProvider


class TestEchoContract(LLMProviderContract):
    """EchoProvider must satisfy every LLMProvider invariant."""

    @pytest.fixture
    def provider(self) -> EchoProvider:
        return EchoProvider()
