"""Structured logging configuration (structlog).

Configures a single, process-wide logging pipeline driven entirely by
:class:`AppSettings`:

* **Format** — ``json`` (machine-readable) outside local, ``console`` (human
  readable) locally, per ``settings.logging.format``.
* **Level** — from ``settings.logging.level``.
* **Correlation id** — injected into every record from the request-scoped
  context variable (see :mod:`.context`).
* **Secret redaction** — any :class:`pydantic.SecretStr` value is masked before
  rendering, so a secret can never reach the log sink (rule 22). This also keeps
  the JSON renderer from failing on a non-serialisable type.
* **Sink** — stdout only; log routing/aggregation is the platform's concern.

The output stream is an injected dependency (default stdout) so the pipeline is
unit-testable without capturing process file descriptors.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

import structlog
from pydantic import SecretStr
from structlog.typing import EventDict, Processor, WrappedLogger

from aiplatform.infrastructure.config.settings import AppSettings, LogFormat

from .context import CORRELATION_ID_FIELD, get_correlation_id

_LEVEL_NAME_TO_INT = logging.getLevelNamesMapping()


def _add_correlation_id(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject the current correlation id into the record, if one is bound."""
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        event_dict.setdefault(CORRELATION_ID_FIELD, correlation_id)
    return event_dict


def _redact_secrets(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """Replace any ``SecretStr`` value with its masked string form."""
    for key, value in event_dict.items():
        if isinstance(value, SecretStr):
            event_dict[key] = str(value)
    return event_dict


def _build_processors(log_format: LogFormat) -> list[Processor]:
    """Assemble the processor chain terminating in the format-specific renderer."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redact_secrets,
    ]
    if log_format is LogFormat.JSON:
        return [*shared, structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
    # ConsoleRenderer formats exceptions itself; colours disabled for determinism.
    return [*shared, structlog.dev.ConsoleRenderer(colors=False)]


def configure_logging(settings: AppSettings, *, stream: TextIO | None = None) -> None:
    """Configure the global structlog pipeline from application settings.

    Idempotent: calling it again reconfigures the pipeline. Intended to be called
    once, early, by the composition root (M1.5).

    Args:
        settings: Validated application settings supplying level and format.
        stream: Output sink; defaults to ``sys.stdout``. Injected for testing.
    """
    output = stream if stream is not None else sys.stdout
    level = _LEVEL_NAME_TO_INT[settings.logging.level.value]

    structlog.configure(
        processors=_build_processors(settings.logging.format),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    """Return a bound logger.

    Args:
        name: Optional logger name (recorded as ``logger`` in the record).

    Returns:
        A structlog logger honouring the configured pipeline.
    """
    return structlog.get_logger(name)
