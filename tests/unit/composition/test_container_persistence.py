"""Container wiring for persistence + conversation services (M2.4)."""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.application.conversation.chat_service import ChatService
from aiplatform.application.conversation.conversation_service import ConversationService
from aiplatform.composition.container import build_container
from aiplatform.infrastructure.config.settings import AppSettings


def _settings(**kwargs: object) -> AppSettings:
    return AppSettings(_env_file=None, env="local", **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


async def test_container_wires_conversation_services() -> None:
    container = build_container(_settings())
    try:
        assert isinstance(container.chat_service, ChatService)
        assert isinstance(container.conversation_service, ConversationService)
    finally:
        await container.aclose()


def test_postgres_backend_without_dsn_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    # The fail-fast precondition is that no DSN is configured. CI exports
    # AIP__PERSISTENCE__POSTGRES__DSN for the real-database suites, and
    # pydantic-settings still reads os.environ even with _env_file=None, so remove
    # it explicitly here rather than assuming the environment is clean.
    monkeypatch.delenv("AIP__PERSISTENCE__POSTGRES__DSN", raising=False)
    with pytest.raises(ValueError, match="requires AIP__PERSISTENCE__POSTGRES__DSN"):
        build_container(_settings(persistence={"backend": "postgres"}))


async def test_services_share_one_repository() -> None:
    """A conversation created via one service is visible through the other."""
    container = build_container(_settings(llm={"default_provider": "echo"}))
    try:
        created = await container.conversation_service.start_conversation(owner="x")
        fetched = await container.conversation_service.get_conversation(created.id)
        assert fetched.id == created.id
    finally:
        await container.aclose()


async def test_chat_turn_through_container_persists_via_shared_repository() -> None:
    """End-to-end through the container against Echo: create → chat → fetch."""
    container = build_container(_settings(llm={"default_provider": "echo"}))
    try:
        created = await container.conversation_service.start_conversation(
            owner="x", system_prompt="Sys"
        )
        result = await container.chat_service.send_message(created.id, "hello world")
        assert result.content == "hello world"  # Echo echoes the user message

        fetched = await container.conversation_service.get_conversation(created.id)
        roles = [m.role.value for m in fetched.messages]
        assert roles == ["system", "user", "assistant"]
        assert fetched.messages[-1].content == "hello world"
    finally:
        await container.aclose()
