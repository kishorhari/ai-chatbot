"""Integration tests for the conversation endpoints (M2.4).

Uses Starlette's TestClient against the fully wired app (Echo backend), verifying
the create → append → fetch flow and the error translations.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aiplatform.interface.http.app import create_app


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def test_create_append_fetch_flow() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/conversations", json={"owner": "alice", "system_prompt": "Be brief."}
        )
        assert created.status_code == 201
        body = created.json()
        cid = body["id"]
        assert body["owner"] == "alice"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "system"

        turn = client.post(f"/conversations/{cid}/messages", json={"text": "hello world"})
        assert turn.status_code == 201
        turn_body = turn.json()
        assert turn_body["conversation_id"] == cid
        assert turn_body["content"] == "hello world"  # Echo echoes
        assert turn_body["usage"]["total_tokens"] >= 0

        fetched = client.get(f"/conversations/{cid}")
        assert fetched.status_code == 200
        messages = fetched.json()["messages"]
        assert [m["role"] for m in messages] == ["system", "user", "assistant"]
        assert messages[-1]["content"] == "hello world"
        assert [m["sequence"] for m in messages] == [0, 1, 2]


def test_fetch_unknown_conversation_returns_404() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/conversations/{uuid.uuid4()}")
    assert response.status_code == 404


def test_malformed_conversation_id_returns_400() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/conversations/not-a-uuid")
    assert response.status_code == 400


def test_send_message_to_unknown_conversation_returns_404() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/conversations/{uuid.uuid4()}/messages", json={"text": "hi"})
    assert response.status_code == 404


def test_create_requires_owner() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/conversations", json={})
    assert response.status_code == 422  # pydantic validation


def test_send_message_requires_text() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/conversations", json={"owner": "alice"})
        cid = created.json()["id"]
        response = client.post(f"/conversations/{cid}/messages", json={})
    assert response.status_code == 422
