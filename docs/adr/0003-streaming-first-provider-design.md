# ADR-0003: Streaming-First Provider Design

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0002 (Provider Abstraction)

## Context

Streaming responses are a committed feature (roadmap Step 7), but the provider
port is being designed now (Step 2). The classic failure mode is to define a
synchronous `generate(prompt) -> str` contract, then discover at the streaming
step that streaming forces an async-iterator return type — forcing a refactor of
the port, every caller, and the "how do I persist a response that arrives in
chunks?" logic all at once.

Streaming is the *superset* of non-streaming: a full response is simply a
collected stream. Designing for the superset now costs little and removes a
guaranteed future refactor.

## Decision

Make **streaming the canonical method** of the `LLMProvider` port, with
non-streaming derived:

- `stream_chat(request) -> AsyncIterator[CompletionChunk]` is the contract every
  adapter must implement. It yields chunks terminating in exactly one
  `is_final=True`, must be **cancellable** (release upstream connection on
  consumer cancellation), and raises only `LLMError` subtypes.
- `complete_chat(request) -> CompletionResult` is a **default-derived** method
  that consumes `stream_chat` and concatenates deltas. An adapter MAY override it
  to use a cheaper one-shot endpoint.

Consequently, Step 7 (SSE) becomes a pure *transport* concern over an already
streaming core — no core change required.

## Consequences

**Positive**
- No core rewrite when streaming transport is added; the seam was correct from day one.
- Every adapter is streaming-capable by construction; impossible to forget.
- Cancellation is a first-class part of the contract, which the Step-7 client-disconnect
  path will rely on.

**Negative / Costs**
- A hypothetical non-streaming-only provider must emit its full response as a
  single terminal chunk — slightly awkward. Theoretical today (Ollama streams natively).
- Slightly more complex contract than a plain `-> str` method; mitigated by the
  derived `complete_chat` convenience.

## Alternatives Considered

- **Synchronous-first (`-> str`), add streaming later** — the exact refactor trap
  we are avoiding. Rejected.
- **Two first-class methods (`stream` + `complete`), neither derived** — duplicates
  the contract and invites divergent behavior between the two paths. Rejected in
  favor of one canonical method + derived convenience with an optional override.

## Trade-offs Accepted

We accept a marginally more complex port contract and a theoretical awkwardness
for non-streaming providers in exchange for eliminating a guaranteed future
refactor and making streaming a transport detail.
