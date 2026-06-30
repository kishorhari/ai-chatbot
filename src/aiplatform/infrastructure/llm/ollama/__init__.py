"""Ollama provider — the first real ``LLMProvider`` adapter.

Streams over async httpx against a local Ollama server, mapping requests and
responses to/from domain value objects and faults to the ``LLMError`` taxonomy.
"""
