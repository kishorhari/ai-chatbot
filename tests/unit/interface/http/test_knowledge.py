"""Integration tests for the knowledge endpoints (M3.6).

Uses the fully wired app over the offline path (fake embedder + in-memory
vector store) with the knowledge feature enabled; a disabled app reports 503.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aiplatform.interface.http.app import create_app


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def _enable_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")
    monkeypatch.setenv("AIP__KNOWLEDGE__ENABLED", "true")
    monkeypatch.setenv("AIP__KNOWLEDGE__EMBEDDING__BACKEND", "fake")
    monkeypatch.setenv("AIP__KNOWLEDGE__EMBEDDING__DIMENSION", "128")
    monkeypatch.setenv("AIP__KNOWLEDGE__VECTOR__BACKEND", "memory")


def test_ingest_then_search_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_knowledge(monkeypatch)
    with TestClient(create_app()) as client:
        ingested = client.post(
            "/knowledge/documents",
            json={
                "source": "geo.md",
                "text": "The capital of France is Paris. Berlin is the capital of Germany.",
                "metadata": {"topic": "geography"},
            },
        )
        assert ingested.status_code == 201
        body = ingested.json()
        assert body["source"] == "geo.md"
        assert body["chunk_count"] >= 1

        found = client.post("/knowledge/search", json={"query": "capital of France", "k": 3})
        assert found.status_code == 200
        chunks = found.json()["chunks"]
        assert chunks
        assert any("Paris" in c["text"] for c in chunks)
        assert all("score" in c and "document_id" in c for c in chunks)


def test_search_with_metadata_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_knowledge(monkeypatch)
    with TestClient(create_app()) as client:
        client.post(
            "/knowledge/documents",
            json={"source": "en.md", "text": "Paris is lovely.", "metadata": {"lang": "en"}},
        )
        client.post(
            "/knowledge/documents",
            json={"source": "fr.md", "text": "Paris est belle.", "metadata": {"lang": "fr"}},
        )
        found = client.post(
            "/knowledge/search", json={"query": "Paris", "metadata": {"lang": "en"}}
        )
        assert found.status_code == 200
        assert {c["metadata"]["lang"] for c in found.json()["chunks"]} == {"en"}


def test_ingest_blank_content_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_knowledge(monkeypatch)
    with TestClient(create_app()) as client:
        response = client.post("/knowledge/documents", json={"source": "s", "text": "   \n  "})
    assert response.status_code == 422


def test_endpoints_return_503_when_knowledge_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")
    # AIP__KNOWLEDGE__ENABLED left unset -> disabled (default).
    with TestClient(create_app()) as client:
        ingest = client.post("/knowledge/documents", json={"source": "s", "text": "hi"})
        search = client.post("/knowledge/search", json={"query": "hi"})
    assert ingest.status_code == 503
    assert search.status_code == 503


def test_search_on_empty_store_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_knowledge(monkeypatch)
    with TestClient(create_app()) as client:
        found = client.post("/knowledge/search", json={"query": str(uuid.uuid4())})
    assert found.status_code == 200
    assert found.json()["chunks"] == []
