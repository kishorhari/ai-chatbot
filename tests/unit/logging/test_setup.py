"""Unit tests for the structlog setup (M1.1-b).

Verifies the testing-strategy requirements for ``setup.py``: the correlation-id
field is injected, SecretStr values are redacted, JSON output is well-formed, and
the configured level filters records. The output stream is injected as an
in-memory buffer so no process file descriptors need capturing.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from pydantic import SecretStr

from aiplatform.infrastructure.config.settings import AppSettings, LogFormat, LogLevel
from aiplatform.infrastructure.logging.context import correlation_id_scope
from aiplatform.infrastructure.logging.setup import configure_logging, get_logger


def _settings(*, level: LogLevel = LogLevel.INFO, fmt: LogFormat = LogFormat.JSON) -> AppSettings:
    return AppSettings(
        _env_file=None,  # type: ignore[call-arg]
        logging={"level": level, "format": fmt},
    )


def _configure_to_buffer(**kwargs: Any) -> io.StringIO:
    buffer = io.StringIO()
    configure_logging(_settings(**kwargs), stream=buffer)
    return buffer


def _last_json_record(buffer: io.StringIO) -> dict[str, Any]:
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert lines, "expected at least one log record"
    return json.loads(lines[-1])


def test_json_record_is_well_formed_with_level_and_event() -> None:
    buffer = _configure_to_buffer()
    get_logger("test").info("hello", user="alice")

    record = _last_json_record(buffer)
    assert record["event"] == "hello"
    assert record["level"] == "info"
    assert record["user"] == "alice"
    assert "timestamp" in record


def test_correlation_id_is_injected_within_scope() -> None:
    buffer = _configure_to_buffer()
    with correlation_id_scope("req-42"):
        get_logger().info("in-scope")

    assert _last_json_record(buffer)["correlation_id"] == "req-42"


def test_correlation_id_absent_outside_scope() -> None:
    buffer = _configure_to_buffer()
    get_logger().info("no-scope")

    assert "correlation_id" not in _last_json_record(buffer)


def test_secret_value_is_redacted() -> None:
    buffer = _configure_to_buffer()
    get_logger().info("auth", api_key=SecretStr("super-secret-token"))

    raw = buffer.getvalue()
    assert "super-secret-token" not in raw
    record = _last_json_record(buffer)
    assert record["api_key"] == "**********"


def test_level_filters_below_threshold() -> None:
    buffer = _configure_to_buffer(level=LogLevel.WARNING)
    logger = get_logger()
    logger.info("suppressed")
    logger.warning("emitted")

    output = buffer.getvalue()
    assert "suppressed" not in output
    assert "emitted" in output


def test_console_format_renders_without_error() -> None:
    buffer = _configure_to_buffer(fmt=LogFormat.CONSOLE)
    get_logger().info("console-event", key="value")

    output = buffer.getvalue()
    assert "console-event" in output
    assert "value" in output


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    """Restore structlog defaults after each test to avoid cross-test bleed."""
    import structlog

    yield
    structlog.reset_defaults()
