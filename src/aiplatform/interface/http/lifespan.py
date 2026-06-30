"""FastAPI lifespan — wire the composition root on startup, dispose on shutdown.

The lifespan builds the application container via the composition bootstrap hook
and stores it on ``app.state`` so routes can resolve wired dependencies (ports
only). On shutdown it releases the container's resources. The interface depends
on the composition lifecycle hooks, never on concrete adapters.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aiplatform.composition.bootstrap import bootstrap, shutdown


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the container on startup and dispose of it on shutdown.

    Readiness (``/ready``) is driven by the presence of ``app.state.container``:
    it is set only after wiring completes, and removed once shutdown begins.
    """
    container = bootstrap()
    app.state.container = container
    try:
        yield
    finally:
        app.state.container = None
        await shutdown(container)
