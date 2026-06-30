"""Structured logging — structlog configuration and correlation-id propagation.

Emits JSON in non-local environments and human-readable console output locally.
A per-request correlation id is injected into every record; secrets are redacted.
"""
