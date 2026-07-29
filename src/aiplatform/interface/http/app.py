"""FastAPI application factory.

Assembles the HTTP delivery surface: the lifespan that wires the composition
root, the correlation-id middleware, the health and conversation routers, and
exception handlers that translate domain/application errors to HTTP status codes.
It contains **no business logic** and constructs **no providers or repositories** —
those are wired by the composition root and reached via ``app.state`` (ports only).
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from aiplatform import __version__
from aiplatform.domain.conversation.ports import ConversationNotFoundError
from aiplatform.domain.llm.errors import LLMError

from .lifespan import lifespan
from .middleware import CorrelationIdMiddleware
from .routes import conversations, health


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A ready-to-serve FastAPI app with lifespan wiring, correlation-id
        middleware, health + conversation endpoints, and error translation.
    """
    app = FastAPI(
        title="AI Platform",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(conversations.router)
    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Translate domain/application errors to HTTP responses (transport concern).

    Keeping this mapping here leaves the route handlers free of error plumbing:
    a missing conversation is 404, and a provider failure is 502 (the upstream
    model is a bad gateway from the client's perspective).
    """

    async def _not_found(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    async def _provider_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "upstream provider error", "type": type(exc).__name__},
        )

    app.add_exception_handler(ConversationNotFoundError, _not_found)
    app.add_exception_handler(LLMError, _provider_error)
