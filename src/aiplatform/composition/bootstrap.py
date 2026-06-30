"""Application lifecycle entry point over the composition root.

``bootstrap`` and ``shutdown`` are the startup/teardown hooks the delivery
surfaces (the FastAPI lifespan in M1.6 and the CLI probe) call, so those
surfaces depend on this thin lifecycle module rather than on the container's
internals. ``bootstrap`` produces a ready-to-use container; ``shutdown`` releases
its resources.
"""

from __future__ import annotations

from aiplatform.infrastructure.config.settings import AppSettings
from aiplatform.infrastructure.logging.setup import get_logger

from .container import Container, build_container

_logger = get_logger("aiplatform.composition")


def bootstrap(settings: AppSettings | None = None) -> Container:
    """Build the application container and announce readiness.

    Args:
        settings: Optional pre-loaded settings (loaded from the environment when
            omitted); forwarded to :func:`build_container`.

    Returns:
        A fully wired, ready-to-serve :class:`Container`.
    """
    container = build_container(settings)
    _logger.info(
        "composition.bootstrap_complete",
        env=container.settings.env.value,
        default_provider=container.registry.default_name,
    )
    return container


async def shutdown(container: Container) -> None:
    """Release the container's resources during application teardown.

    Args:
        container: The container returned by :func:`bootstrap`.
    """
    await container.aclose()
    _logger.info("composition.shutdown_complete")
