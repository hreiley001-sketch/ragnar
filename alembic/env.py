"""Alembic environment — uses RAGNAR Settings + SQLModel metadata."""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Ensure project root is on sys.path when Alembic runs as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app import models  # noqa: E402,F401  — register all tables on metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _migration_url() -> str:
    """Where migrations run.

    Alembic needs a real session (transaction pooler :6543 breaks prepared
    statements), so the Supabase cutover points migrations at the session
    pooler / direct connection via SUPABASE_MIGRATION_DB_URL (or ALEMBIC_DB_URL),
    while the app keeps using DATABASE_URL / the transaction pooler at runtime.
    Falls back to settings.database_url so local + SQLite dev is unchanged.
    """
    return (
        os.getenv("SUPABASE_MIGRATION_DB_URL")
        or os.getenv("ALEMBIC_DB_URL")
        or settings.database_url
    ).strip()


# Escape % so ConfigParser interpolation doesn't choke on %-encoded
# credentials (e.g. a URL-encoded password). get_main_option() restores it.
config.set_main_option("sqlalchemy.url", _migration_url().replace("%", "%%"))

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
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
        url=config.get_main_option("sqlalchemy.url"),
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
