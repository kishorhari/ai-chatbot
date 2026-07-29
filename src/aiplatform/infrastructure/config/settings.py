"""Application configuration — the single, validated, fail-fast settings source.

All configuration is read through :class:`AppSettings`. Nothing else in the
codebase reads ``os.environ`` directly (rule 23). Validation happens at load
time, so an invalid or out-of-range value aborts startup with a clear error
rather than surfacing on the first request.

Environment binding (ADR-0002 convention):

* prefix:           ``AIP__``
* nested delimiter: ``__``  (e.g. ``AIP__OLLAMA__BASE_URL`` -> ``ollama.base_url``)

This module deliberately imports **nothing** from the logging package: settings
load *before* logging is configured, and the dependency must never reverse
(see the circular-risk analysis in the dependency matrix; enforced by
import-linter).
"""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Runtime environment. Drives logging format and provider wiring policy."""

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogFormat(StrEnum):
    """Log rendering style. ``console`` for humans locally, ``json`` otherwise."""

    CONSOLE = "console"
    JSON = "json"


class PersistenceBackend(StrEnum):
    """Selectable conversation-persistence backend (ADR-0008).

    ``postgres`` is a valid, documented value but is only wired from M2.5; the
    composition root fails fast if it is selected before then.
    """

    MEMORY = "memory"
    POSTGRES = "postgres"


class ServerSettings(BaseModel):
    """HTTP server bind configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


class LoggingSettings(BaseModel):
    """Structured-logging configuration consumed by the logging setup (M1.1-b)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.CONSOLE


class LLMSettings(BaseModel):
    """Provider-selection configuration.

    ``default_provider`` is a free string (not an enum) so that registering a new
    provider stays a composition-root concern (ADR-0002, Open/Closed) and does not
    require editing this module. The composition root validates that the named
    provider is actually registered, which keeps the "is it known?" decision where
    the knowledge lives.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_provider: str = "ollama"

    @field_validator("default_provider")
    @classmethod
    def _normalize(cls, value: str) -> str:
        """Normalise the provider key to a trimmed, lower-case token."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("default_provider must not be empty")
        return normalized


class OllamaSettings(BaseModel):
    """Ollama adapter configuration.

    Connect and request timeouts are intentionally separate: streaming responses
    can run far longer than the time allowed to establish a connection (ADR-0003).
    """

    # validate_default ensures the default base_url is run through the validator
    # below, so an invalid override *and* a broken default both fail fast.
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    base_url: str = "http://localhost:11434"
    model: str = "llama3"
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    max_connect_retries: int = Field(default=2, ge=0)

    # Reserved for authenticated/proxied Ollama deployments and future cloud
    # providers. SecretStr guarantees the value is masked in logs and reprs
    # (rule 22 / the redaction requirement the logging setup relies on).
    api_key: SecretStr | None = None

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        """Require an http(s) URL with a host; strip any trailing slash."""
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL with a host")
        return value.rstrip("/")


class PostgresSettings(BaseModel):
    """PostgreSQL connection configuration.

    ``dsn`` is the full async SQLAlchemy URL (e.g.
    ``postgresql+asyncpg://user:password@host:5432/dbname``). It is a
    :class:`SecretStr` because it embeds the password — it is never logged or
    reprinted (ADR-0008). Required only when the ``postgres`` backend is selected.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dsn: SecretStr | None = None


class PersistenceSettings(BaseModel):
    """Conversation-persistence configuration.

    Selecting the backend is a configuration change only (ADR-0008), mirroring
    provider selection.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: PersistenceBackend = PersistenceBackend.MEMORY
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)


class AppSettings(BaseSettings):
    """Root settings aggregate, populated from the environment and ``.env``.

    Construction validates every nested section; a failure raises
    ``pydantic.ValidationError`` at load time (fail-fast). ``extra='forbid'``
    rejects unknown ``AIP__*`` keys so typos surface immediately instead of being
    silently ignored.
    """

    model_config = SettingsConfigDict(
        env_prefix="AIP__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
    )

    env: Environment = Environment.LOCAL
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)

    @property
    def is_local(self) -> bool:
        """True when running in the local development environment."""
        return self.env is Environment.LOCAL

    @property
    def is_test(self) -> bool:
        """True when running under the test environment."""
        return self.env is Environment.TEST

    @property
    def is_production(self) -> bool:
        """True when running in production."""
        return self.env is Environment.PRODUCTION


def load_settings() -> AppSettings:
    """Build and validate the application settings.

    The single construction entry point used by the composition root (M1.5) and
    by tests. Kept as a plain factory rather than a cached singleton so the
    composition root owns the instance's lifetime explicitly.

    Returns:
        A fully validated :class:`AppSettings` instance.

    Raises:
        pydantic.ValidationError: If any configuration value is invalid.
    """
    return AppSettings()
