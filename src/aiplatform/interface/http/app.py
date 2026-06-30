"""FastAPI application factory.

Assembles the HTTP delivery surface: the lifespan that wires the composition
root, the correlation-id middleware, and the health router. It contains **no
business logic** and constructs **no providers** — those are wired by the
composition root and reached via ``app.state`` (ports only).
"""

from __future__ import annotations

from fastapi import FastAPI

from aiplatform import __version__

from .lifespan import lifespan
from .middleware import CorrelationIdMiddleware
from .routes import health


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A ready-to-serve FastAPI app with lifespan wiring, correlation-id
        middleware, and health endpoints mounted.
    """
    app = FastAPI(
        title="AI Platform",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    return app
