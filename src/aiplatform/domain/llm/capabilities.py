"""Provider capability descriptor.

A pure, immutable declaration of what a provider supports. Returned by the
port's ``capabilities()`` method, which must perform no I/O (ADR-0003 / the
contract suite): the value is static metadata, not a runtime probe.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderCapabilities(BaseModel):
    """What an ``LLMProvider`` implementation can do.

    Feature flags are required (no defaults) so every adapter declares its
    capabilities honestly rather than inheriting an optimistic default.

    ``model`` is provider *metadata* (the default model identifier), kept here
    rather than on the port: the port exposes capabilities and operations, not
    implementation metadata. The derived ``complete_chat`` reads it to label a
    result when the request does not override the model.

    Attributes:
        model: The provider's default model identifier.
        supports_streaming: Whether the provider streams incrementally.
        supports_system_prompt: Whether a system role is honoured.
        reports_token_usage: Whether token counts are real (vs. stubbed zero).
        max_context_tokens: The context window size, if known; ``None`` when
            unspecified.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = Field(min_length=1)
    supports_streaming: bool
    supports_system_prompt: bool
    reports_token_usage: bool
    max_context_tokens: int | None = Field(default=None, gt=0)
