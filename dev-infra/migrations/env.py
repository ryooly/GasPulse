"""Alembic migration environment.

Wires Alembic to the project's shared SQLAlchemy ``Base`` metadata so migrations
are generated from the real ORM models (``app.models``). The database URL comes
from ``DATABASE_URL`` (defaulting to the docker-compose Postgres).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Project root = parents[2] of .../dev-infra/migrations/env.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401,E402  (imports register every model on Base)
from db.base import Base  # noqa: E402

DEFAULT_URL = "postgresql+psycopg://gaspulse:gaspulse@127.0.0.1:5433/gaspulse"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_URL)

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
