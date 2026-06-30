"""Integration tests for the FastAPI app: health, readiness, correlation (M1.6).

Uses Starlette's TestClient. Entering the client as a context manager runs the
lifespan (composition wiring); the readiness probe reflects that.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from aiplatform.interface.http.app import create_app
from aiplatform.interface.http.routes.health import ready


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in local env with quiet logging so bootstrap is deterministic."""
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def test_health_is_always_alive() -> None:
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_returns_200_after_wiring() -> None:
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["default_provider"] == "ollama"


def test_correlation_id_is_echoed_on_response() -> None:
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Correlation-ID": "trace-123"})
    assert response.headers["x-correlation-id"] == "trace-123"


def test_correlation_id_is_generated_when_absent() -> None:
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.headers.get("x-correlation-id")


async def test_ready_is_503_before_wiring() -> None:
    """Directly exercise the readiness route with an un-wired app state."""

    class _State:
        container = None

    class _App:
        state = _State()

    request = Request({"type": "http", "headers": [], "app": _App()})
    result = await ready(request)
    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
