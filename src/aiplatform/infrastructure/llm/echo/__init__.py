"""Echo provider — the reference ``LLMProvider`` implementation (ADR-0004).

Deterministic, network-free echo of its input. Proves the port is genuinely
provider-agnostic and enables fast, offline tests of every layer above it.
Wired only in local/test environments.
"""
