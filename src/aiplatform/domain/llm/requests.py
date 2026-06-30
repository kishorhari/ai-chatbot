"""Request value objects — what the caller asks a provider to generate.

Immutable inputs to the ``LLMProvider`` port. Generation tuning lives in
``GenerationParams``; the conversation and routing live in ``CompletionRequest``.
Pure domain (ADR-0001): no vendor or transport concepts.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .messages import ChatMessage, Role


class GenerationParams(BaseModel):
    """Provider-agnostic generation tuning.

    Every field is optional; ``None`` means *defer to the provider's own
    default* rather than imposing one in the domain. ``seed`` enables
    reproducible output, which the contract suite relies on for determinism.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stop: tuple[str, ...] = ()
    seed: int | None = None


class CompletionRequest(BaseModel):
    """An immutable request to complete a conversation.

    Attributes:
        messages: The conversation so far; must contain at least one message.
        params: Generation tuning (defaults to provider defaults).
        model: Optional per-request model override. When ``None`` the provider
            uses its configured model, keeping model selection a configuration
            concern (ADR-0002) while still allowing an explicit override.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    messages: tuple[ChatMessage, ...] = Field(min_length=1)
    params: GenerationParams = Field(default_factory=GenerationParams)
    model: str | None = None

    @property
    def last_user_message(self) -> ChatMessage | None:
        """Return the most recent user message, or ``None`` if there is none."""
        for message in reversed(self.messages):
            if message.role is Role.USER:
                return message
        return None
