# ADR-0004: Echo Provider as Reference Implementation

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0002 (Provider Abstraction), ADR-0003 (Streaming-First)

## Context

An abstraction is only proven when it has more than one implementation. With a
single Ollama adapter, the `LLMProvider` port could silently become
"Ollama-shaped" — leaking vendor concepts that only surface painfully when the
second provider is added. We also need to develop and test every layer above the
provider (chat, memory, prompt assembly) without depending on a running Ollama
instance, and CI must run fast and offline.

## Decision

Ship a second `LLMProvider` implementation, **`EchoProvider`**, from day one. It
streams back a deterministic transformation of its input (e.g. echoes the last
user message token-by-token), reports stub `capabilities()` and `TokenUsage`,
and performs **no network I/O**.

Both `OllamaProvider` and `EchoProvider` must pass the **same provider contract
test suite**. That shared suite is the operational definition of "the abstraction
is real."

`EchoProvider` is wired by the composition root only in `local`/`test`
environments and is selectable via `AIP__LLM__DEFAULT_PROVIDER=echo`.

## Consequences

**Positive**
- Proves the port is genuinely provider-agnostic (two passing implementations).
- Enables fast, offline, deterministic tests of every layer above the provider.
- Unblocks Step-3 chat development before Ollama is configured.
- Acts as living documentation of the minimum a provider must do.

**Negative / Costs**
- A small amount of non-production code to maintain. Judged clearly worth it.
- Must be gated out of production wiring to avoid accidental use.

## Alternatives Considered

- **Mocks / stubs in tests only** — they assert against our *assumptions* about
  the port, not a real implementation, and do nothing to prove the abstraction
  isn't Ollama-shaped. Rejected as the primary mechanism (mocks may still appear
  in narrow unit tests).
- **Recorded fixtures / VCR-style replay of Ollama responses** — useful for
  integration realism but couples tests to recorded vendor payloads and does not
  provide a second independent implementation. Deferred as an optional
  integration aid, not a substitute.

## Trade-offs Accepted

We accept maintaining a small non-production provider in exchange for a
continuous, executable proof that the abstraction holds and a fast offline test
path for the entire stack above the provider.
