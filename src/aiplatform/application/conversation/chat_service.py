"""ChatService — the conversation chat use case (M2.3, ADR-0010).

A stateless application service that orchestrates one chat turn and nothing else:

    load → append user → window → assemble → generate → append assistant
         → persist atomically → return.

Design (approved in the M2.3 architecture review):

* **Generation runs outside the transaction.** ``complete_chat`` is slow and
  cancellable; no transaction is ever held open across it.
* **A single atomic persistence** at the end saves the aggregate — which now
  carries both the user and the assistant message — so they persist together or
  not at all.
* **Typed collaborator errors propagate unwrapped.** The service adds no error
  handling of its own beyond the transactional guarantee. ``ConversationNotFound``,
  the ``LLMError`` taxonomy, and repository errors are translated at the edges
  (delivery -> HTTP, adapters -> domain errors), never re-wrapped here.
* **Stateless.** All per-request state lives in locals; the service and every
  collaborator are shared singletons.

It depends only on ports and pure collaborators (ADR-0010): no concrete adapter,
``httpx``, SQLAlchemy, or framework import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aiplatform.application.clock import Clock
from aiplatform.application.llm.provider_registry import ProviderRegistry
from aiplatform.domain.conversation.ids import ConversationId, MessageId
from aiplatform.domain.conversation.ports import ConversationRepository
from aiplatform.domain.llm.responses import FinishReason, TokenUsage

from .context_window import ContextWindowPolicy
from .prompt_assembler import PromptAssembler
from .transaction import TransactionBoundary


@dataclass(frozen=True, slots=True)
class ChatResult:
    """The outcome of one chat turn — an application DTO for delivery.

    Immutable and free of domain aggregates: a caller receives exactly what it
    needs to render the assistant's reply without reaching into the conversation.

    Attributes:
        conversation_id: The conversation the turn belongs to.
        message_id: Identity of the persisted assistant message.
        content: The assistant reply text.
        model: The model that produced the reply.
        usage: Token accounting for the reply (zero when the provider reports none).
        finish_reason: Why generation stopped, if reported.
        created_at: When the assistant message was recorded.
    """

    conversation_id: ConversationId
    message_id: MessageId
    content: str
    model: str
    usage: TokenUsage
    finish_reason: FinishReason | None
    created_at: datetime


class ChatService:
    """Orchestrates a single chat turn against an existing conversation."""

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        clock: Clock,
        provider_registry: ProviderRegistry,
        context_window: ContextWindowPolicy,
        prompt_assembler: PromptAssembler,
        transactions: TransactionBoundary,
    ) -> None:
        """Inject collaborators; store no per-request state."""
        self._repository = repository
        self._clock = clock
        self._provider_registry = provider_registry
        self._context_window = context_window
        self._prompt_assembler = prompt_assembler
        self._transactions = transactions

    async def send_message(
        self, conversation_id: ConversationId, text: str, *, model: str | None = None
    ) -> ChatResult:
        """Run one chat turn: append the user message, generate, and persist.

        Args:
            conversation_id: The conversation to continue.
            text: The user's message text.
            model: Optional per-request model override; ``None`` uses the
                provider's configured model.

        Returns:
            A :class:`ChatResult` describing the persisted assistant reply.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
            LLMError: Any generation failure, unwrapped (e.g. timeout, rate limit).
            RepositoryError: If persistence fails; the turn is rolled back and
                nothing is written.
        """
        conversation = await self._repository.get(conversation_id)
        conversation.append_user(text, created_at=self._clock.now())

        provider = self._provider_registry.get_default()
        capabilities = provider.capabilities()
        windowed = self._context_window.select(
            conversation.messages, max_context_tokens=capabilities.max_context_tokens
        )
        request = self._prompt_assembler.assemble(windowed, model=model)

        # Generation runs OUTSIDE the transaction: it is slow and cancellable, and
        # holding a transaction across it would pin a connection and extend locks.
        result = await provider.complete_chat(request)

        assistant = conversation.append_assistant(
            result.text, created_at=self._clock.now(), usage=result.usage
        )

        # Single atomic persistence: the aggregate carries both new messages, so
        # the user turn and the assistant reply commit together or not at all.
        async with self._transactions.atomic():
            await self._repository.save(conversation)

        return ChatResult(
            conversation_id=conversation.id,
            message_id=assistant.id,
            content=assistant.content,
            model=result.model,
            usage=result.usage,
            finish_reason=result.finish_reason,
            created_at=assistant.created_at,
        )
