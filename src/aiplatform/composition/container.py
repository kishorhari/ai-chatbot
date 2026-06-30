"""The composition root — the single place concrete implementations are wired.

``build_container`` is the only function in the codebase permitted to import
concrete adapters and bind them to ports (ADR-0001). It loads settings,
configures logging, builds the providers (Ollama always; Echo only in
local/test, per ADR-0004), and assembles the registry with the configured
default. Selecting a provider is therefore purely a configuration change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aiplatform.application.llm.provider_registry import ProviderRegistry
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.infrastructure.config.settings import AppSettings, load_settings
from aiplatform.infrastructure.llm.echo.adapter import EchoProvider
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider
from aiplatform.infrastructure.logging.setup import configure_logging, get_logger

from .registry import DictProviderRegistry

_logger = get_logger("aiplatform.composition")


@runtime_checkable
class _Closeable(Protocol):
    """Anything owning resources that must be released on shutdown."""

    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Container:
    """The wired object graph produced by the composition root.

    Attributes:
        settings: The validated application settings.
        registry: The provider registry (a port; concrete type hidden).
        disposables: Wired components needing async cleanup on shutdown.
    """

    settings: AppSettings
    registry: ProviderRegistry
    disposables: tuple[_Closeable, ...]

    async def aclose(self) -> None:
        """Release every disposable component (e.g. provider HTTP clients)."""
        for disposable in self.disposables:
            await disposable.aclose()


def build_container(settings: AppSettings | None = None) -> Container:
    """Build the fully wired application container.

    Args:
        settings: Pre-loaded settings; loaded from the environment when omitted.
            Injectable so tests can wire a container without environment mutation.

    Returns:
        A wired :class:`Container`.

    Raises:
        ProviderNotFoundError: If the configured default provider is not wired
            (e.g. ``default_provider=echo`` outside local/test). Fails fast.
    """
    resolved = settings if settings is not None else load_settings()
    configure_logging(resolved)

    providers = _build_providers(resolved)
    registry = DictProviderRegistry(providers, default_name=resolved.llm.default_provider)
    disposables = tuple(p for p in providers.values() if isinstance(p, _Closeable))

    _logger.info(
        "composition.providers_wired",
        env=resolved.env.value,
        default_provider=resolved.llm.default_provider,
        available=sorted(providers),
    )
    return Container(settings=resolved, registry=registry, disposables=disposables)


def _build_providers(settings: AppSettings) -> dict[str, LLMProvider]:
    """Construct the providers available in the current environment.

    Ollama is always wired; Echo is added only in local/test (ADR-0004) so it can
    never be selected accidentally in production.
    """
    providers: dict[str, LLMProvider] = {
        OllamaProvider.NAME: OllamaProvider(settings.ollama),
    }
    if settings.is_local or settings.is_test:
        providers[EchoProvider.NAME] = EchoProvider()
    return providers
