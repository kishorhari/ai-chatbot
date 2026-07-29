"""Container wiring of the knowledge (RAG) feature toggle (M3.6)."""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.composition.container import build_container
from aiplatform.infrastructure.config.settings import AppSettings


def _settings(**knowledge: object) -> AppSettings:
    return AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        env="local",  # type: ignore[arg-type]
        llm={"default_provider": "echo"},
        knowledge=knowledge or {"enabled": False},
    )


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


async def test_disabled_wires_no_knowledge() -> None:
    container = build_container(_settings(enabled=False))
    try:
        assert container.knowledge is None
        # Chat still works — identical to M2 (Null context provider).
        created = await container.conversation_service.start_conversation(owner="u")
        result = await container.chat_service.send_message(created.id, "hello world")
        assert result.content == "hello world"  # Echo echoes; no augmentation
    finally:
        await container.aclose()


async def test_enabled_wires_knowledge_and_retrieval_round_trips() -> None:
    container = build_container(
        _settings(
            enabled=True,
            embedding={"backend": "fake", "dimension": 64},
            vector={"backend": "memory"},
        )
    )
    try:
        assert container.knowledge is not None
        result = await container.knowledge.indexing_service.index(
            source="geo.md", text="The capital of France is Paris."
        )
        assert result.chunk_count > 0
        context = await container.knowledge.retrieval_service.search("capital of France")
        assert any("Paris" in chunk.text for chunk in context.chunks)
    finally:
        await container.aclose()


def test_pgvector_backend_without_dsn_fails_fast() -> None:
    # Selecting pgvector without a configured DSN fails fast with a clear message,
    # before the pgvector driver is even imported (so it holds on a driverless box).
    with pytest.raises(ValueError, match="requires AIP__PERSISTENCE__POSTGRES__DSN"):
        build_container(_settings(enabled=True, vector={"backend": "pgvector"}))


async def test_ollama_embedding_backend_builds_without_network() -> None:
    # Constructing the Ollama embedder must not require a live server.
    container = build_container(
        _settings(enabled=True, embedding={"backend": "ollama", "model": "nomic-embed-text"})
    )
    try:
        assert container.knowledge is not None
    finally:
        await container.aclose()  # disposes the embedder's httpx client
