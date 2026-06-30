"""The ``ProviderRegistry`` port — provider resolution by name or default.

An application-layer port (it orchestrates provider selection, a use-case
concern) that depends only on the domain (``LLMProvider`` and the error
taxonomy). The concrete, dict-backed implementation is built by the composition
root (M1.5), which is also where the available providers and the default are
chosen by configuration (ADR-0002). Selecting a provider is therefore a
configuration change, never a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiplatform.domain.llm.errors import LLMError
from aiplatform.domain.llm.ports import LLMProvider


class ProviderNotFoundError(LLMError):
    """Raised when no provider is registered under the requested name.

    A configuration/lookup failure, so non-retryable (inherited from
    ``LLMError``). Subclassing ``LLMError`` lets callers handle provider
    resolution failures alongside generation failures via a single ``except``.
    """


class ProviderRegistry(ABC):
    """Abstract port that resolves ``LLMProvider`` instances.

    Kept intentionally small (ADR-0002): look a provider up by name, or fetch the
    configured default. The concrete implementation owns the registered set.
    """

    @property
    @abstractmethod
    def default_name(self) -> str:
        """Name of the provider used when no explicit name is requested."""

    @abstractmethod
    def get(self, name: str) -> LLMProvider:
        """Return the provider registered under ``name``.

        Args:
            name: The provider's registered key.

        Returns:
            The matching provider.

        Raises:
            ProviderNotFoundError: If no provider is registered under ``name``.
        """

    def get_default(self) -> LLMProvider:
        """Return the configured default provider.

        Derived from :attr:`default_name` and :meth:`get`, so the resolution rule
        lives in exactly one place (rule 21).

        Returns:
            The default provider.

        Raises:
            ProviderNotFoundError: If the configured default is not registered.
        """
        return self.get(self.default_name)
