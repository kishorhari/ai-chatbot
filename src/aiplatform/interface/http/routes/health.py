"""Health endpoints — liveness and readiness.

* ``/health`` — liveness: always 200 while the process is up. No dependency
  checks; answers "is the process running?".
* ``/ready`` — readiness: 200 only once composition has wired a usable default
  provider (roadmap §5 exit criterion 4). Answers "can it serve requests?".

The route reads only the application ``ProviderRegistry`` port from the wired
container; it contains no business logic and no provider-specific code.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from aiplatform.application.llm.provider_registry import (
    ProviderNotFoundError,
    ProviderRegistry,
)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process is running."""
    return {"status": "alive"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe: composition completed and a default provider resolves."""
    registry = _registry(request)
    if registry is None:
        return _not_ready("composition incomplete")
    try:
        registry.get_default()
    except ProviderNotFoundError:
        return _not_ready("default provider unavailable")
    return JSONResponse({"status": "ready", "default_provider": registry.default_name})


def _registry(request: Request) -> ProviderRegistry | None:
    """Return the wired provider registry, or ``None`` before wiring completes."""
    container = getattr(request.app.state, "container", None)
    if container is None:
        return None
    registry: ProviderRegistry = container.registry
    return registry


def _not_ready(reason: str) -> JSONResponse:
    """Build a 503 readiness response with a reason."""
    return JSONResponse(
        {"status": "not_ready", "reason": reason},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
