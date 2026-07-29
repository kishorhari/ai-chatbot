"""The composition root — the single place concrete implementations are wired.

``build_container`` is the only function in the codebase permitted to import
concrete adapters and bind them to ports (ADR-0001). It loads settings,
configures logging, builds the providers (Ollama always; Echo only in
local/test, per ADR-0004), selects the persistence backend by configuration
(ADR-0008), and assembles the conversation application services (ADR-0010).
Selecting a provider or a persistence backend is therefore purely a
configuration change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aiplatform.application.conversation.chat_service import ChatService
from aiplatform.application.conversation.context_window import ContextWindowPolicy
from aiplatform.application.conversation.conversation_service import ConversationService
from aiplatform.application.conversation.prompt_assembler import PromptAssembler
from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.conversation.transaction import TransactionBoundary
from aiplatform.application.llm.provider_registry import ProviderRegistry
from aiplatform.domain.conversation.ports import ConversationRepository
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.infrastructure.clock import SystemClock
from aiplatform.infrastructure.config.settings import (
    AppSettings,
    PersistenceBackend,
    load_settings,
)
from aiplatform.infrastructure.llm.echo.adapter import EchoProvider
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider
from aiplatform.infrastructure.logging.setup import configure_logging, get_logger
from aiplatform.infrastructure.persistence.memory.repository import (
    InMemoryConversationRepository,
)
from aiplatform.infrastructure.persistence.memory.transaction import (
    InMemoryTransactionBoundary,
)
from aiplatform.infrastructure.persistence.sqlalchemy.repository import (
    SqlAlchemyConversationRepository,
)
from aiplatform.infrastructure.persistence.sqlalchemy.session import SessionProvider
from aiplatform.infrastructure.persistence.sqlalchemy.transaction import (
    SqlAlchemyTransactionBoundary,
)

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
        chat_service: The chat-turn application service (ADR-0010).
        conversation_service: The conversation lifecycle/query service (ADR-0010).
        disposables: Wired components needing async cleanup on shutdown.
    """

    settings: AppSettings
    registry: ProviderRegistry
    chat_service: ChatService
    conversation_service: ConversationService
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
        ProviderNotFoundError: If the configured default provider is not wired.
        ValueError: If the configured persistence backend is not available yet.
    """
    resolved = settings if settings is not None else load_settings()
    configure_logging(resolved)

    providers = _build_providers(resolved)
    registry = DictProviderRegistry(providers, default_name=resolved.llm.default_provider)

    repository, transactions, persistence_disposables = _build_persistence(resolved)
    clock = SystemClock()
    context_window = ContextWindowPolicy(HeuristicTokenEstimator())
    prompt_assembler = PromptAssembler()

    chat_service = ChatService(
        repository=repository,
        clock=clock,
        provider_registry=registry,
        context_window=context_window,
        prompt_assembler=prompt_assembler,
        transactions=transactions,
    )
    conversation_service = ConversationService(
        repository=repository, clock=clock, transactions=transactions
    )

    disposables = (
        tuple(p for p in providers.values() if isinstance(p, _Closeable)) + persistence_disposables
    )

    _logger.info(
        "composition.wired",
        env=resolved.env.value,
        default_provider=resolved.llm.default_provider,
        available_providers=sorted(providers),
        persistence_backend=resolved.persistence.backend.value,
    )
    return Container(
        settings=resolved,
        registry=registry,
        chat_service=chat_service,
        conversation_service=conversation_service,
        disposables=disposables,
    )


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


def _build_persistence(
    settings: AppSettings,
) -> tuple[ConversationRepository, TransactionBoundary, tuple[_Closeable, ...]]:
    """Select the persistence backend by configuration (ADR-0008).

    Returns a matched (repository, transaction-boundary, disposables) triple —
    matched because the SQLAlchemy pair shares one session provider. The in-memory
    backend needs no disposal; the PostgreSQL backend disposes its engine on
    shutdown.
    """
    backend = settings.persistence.backend
    if backend is PersistenceBackend.MEMORY:
        return InMemoryConversationRepository(), InMemoryTransactionBoundary(), ()
    if backend is PersistenceBackend.POSTGRES:
        return _build_postgres_persistence(settings)
    raise ValueError(f"unknown persistence backend {backend.value!r}")


def _build_postgres_persistence(
    settings: AppSettings,
) -> tuple[ConversationRepository, TransactionBoundary, tuple[_Closeable, ...]]:
    """Wire the PostgreSQL repository + transaction boundary over one engine.

    The engine is created lazily here (the ``asyncpg`` driver is only needed when
    this backend is selected). Fails fast if no DSN is configured.
    """
    # Imported locally so the async engine (and its driver requirement) is only
    # touched when the postgres backend is actually selected.
    from sqlalchemy.ext.asyncio import create_async_engine

    dsn = settings.persistence.postgres.dsn
    if dsn is None:
        raise ValueError("persistence backend 'postgres' requires AIP__PERSISTENCE__POSTGRES__DSN")
    engine = create_async_engine(dsn.get_secret_value())
    provider = SessionProvider(engine)
    repository = SqlAlchemyConversationRepository(provider)
    transactions = SqlAlchemyTransactionBoundary(provider)
    return repository, transactions, (provider,)
