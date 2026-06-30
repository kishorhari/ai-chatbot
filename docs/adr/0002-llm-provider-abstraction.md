# ADR-0002: LLM Provider Abstraction

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), ADR-0003 (Streaming-First), ADR-0004 (Echo Provider)

## Context

The platform must support multiple LLM providers over its lifetime. Ollama is
the only provider today, but cloud providers (Anthropic, OpenAI-compatible
endpoints, etc.) are expected. Chat, memory, RAG, and agents will all sit on top
of model invocation. If any of those features call a vendor SDK directly, the
provider becomes a hard dependency that metastasizes across the codebase — the
single most expensive mistake we can make this early.

## Decision

Define a **provider-agnostic port `LLMProvider` in the domain layer**, and place
all vendor-specific code in **infrastructure adapters**. Every feature depends on
the port; nothing above infrastructure imports a vendor SDK or `httpx`.

- The port speaks in **domain value objects** (`ChatMessage`, `CompletionRequest`,
  `CompletionChunk`, `CompletionResult`, `ProviderCapabilities`), never vendor
  payload shapes.
- Adapters map domain objects ↔ vendor API and map all transport/vendor failures
  into a **domain `LLMError` hierarchy**. No `httpx`/`asyncio`/`json` exception
  escapes an adapter.
- A thin **`ProviderRegistry`** (application port) resolves a provider by name or
  returns the configured default. Today it is a dict populated by the composition
  root with one Ollama entry (plus Echo for tests).

## Consequences

**Positive**
- Adding a provider is "write an adapter + register one line" — Open/Closed.
- Selecting a provider is a config change (`AIP__LLM__DEFAULT_PROVIDER`).
- Business logic is shielded from vendor breaking changes and quirks.
- The domain error taxonomy lets callers make retry/HTTP-status decisions without
  string-matching vendor messages.

**Negative / Costs**
- A mapping layer must be written and maintained per adapter.
- The abstraction risks leaking vendor concepts if designed carelessly; we guard
  against this with the Echo provider and a shared contract test (ADR-0004).

## Alternatives Considered

- **Call the vendor SDK directly in services** — least code now, maximal coupling
  later. Rejected outright.
- **Thin pass-through wrapper only** — would still leak vendor request/response
  shapes into callers. Rejected; we need true domain types.
- **A framework abstraction (e.g. LangChain) as the seam** — adopts a large,
  fast-moving dependency as our core boundary, surrenders control of the contract,
  and obscures the learning goal. Rejected. We may *use* such libraries behind an
  adapter later, but they will never *be* our port.

## Trade-offs Accepted

We accept the cost of writing and maintaining per-adapter mapping code in
exchange for vendor independence, testability, and a stable internal contract.
