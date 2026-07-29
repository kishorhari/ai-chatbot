"""Alembic migration environment (async, ADR-0008).

The database URL comes from the application ``Settings``
(``AIP__PERSISTENCE__POSTGRES__DSN``) — no credentials live in ``alembic.ini`` —
and the target schema is the SQLAlchemy models' metadata, so autogenerate stays in
sync with the ORM.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from aiplatform.infrastructure.config.settings import load_settings
from aiplatform.infrastructure.persistence.sqlalchemy.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    dsn = load_settings().persistence.postgres.dsn
    if dsn is None:
        raise RuntimeError("AIP__PERSISTENCE__POSTGRES__DSN is required to run migrations")
    return dsn.get_secret_value()


def run_migrations_offline() -> None:
    """Emit migration SQL without a live database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Apply migrations against the configured async database."""
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
