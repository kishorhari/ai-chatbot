"""Concrete, dict-backed implementation of the ``ProviderRegistry`` port.

Lives in the composition layer (per the approved file plan): it is assembled by
the composition root from already-built providers and holds them for lookup. It
imports only the application port and the domain error taxonomy — never a
concrete provider — so the registry stays agnostic of which providers exist.

Fail-fast: the configured default must be present at construction, so a
misconfigured default aborts startup rather than failing on first use (roadmap
§5 exit criterion 3).
"""

from __future__ import annotations

from collections.abc import Mapping

from aiplatform.application.llm.provider_registry import (
    ProviderNotFoundError,
    ProviderRegistry,
)
from aiplatform.domain.llm.ports import LLMProvider


class DictProviderRegistry(ProviderRegistry):
    """A registry backed by an in-memory mapping of name to provider.

    Args:
        providers: The registered providers, keyed by their registry name.
        default_name: The provider returned by ``get_default``.

    Raises:
        ProviderNotFoundError: If ``default_name`` is not among ``providers``.
    """

    def __init__(self, providers: Mapping[str, LLMProvider], *, default_name: str) -> None:
        """Store the providers and validate that the default is registered."""
        self._providers: dict[str, LLMProvider] = dict(providers)
        if default_name not in self._providers:
            raise ProviderNotFoundError(
                f"default provider {default_name!r} is not registered; "
                f"available: {sorted(self._providers)}"
            )
        self._default_name = default_name

    @property
    def default_name(self) -> str:
        """Name of the configured default provider."""
        return self._default_name

    @property
    def names(self) -> tuple[str, ...]:
        """The registered provider names, sorted (useful for readiness/diagnostics)."""
        return tuple(sorted(self._providers))

    def get(self, name: str) -> LLMProvider:
        """Return the provider registered under ``name``.

        Raises:
            ProviderNotFoundError: If no provider is registered under ``name``.
        """
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"no provider registered as {name!r}; available: {self.names}"
            ) from exc
