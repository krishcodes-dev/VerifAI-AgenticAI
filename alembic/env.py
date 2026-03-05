"""
alembic/env.py — Alembic migration environment configuration.

Reads DATABASE_URL from the application's Settings (via .env),
so migrations always target the same database the app uses.
Supports both offline (SQL dump) and online (live connection) modes.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Ensure the project root is on sys.path ──────────────────────────────────
# Allows `from app.models import Base` to resolve when running alembic from
# the project root directory.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Load application settings ────────────────────────────────────────────────
# Import Settings before importing models so the .env file is loaded first.
from app.config import get_settings
settings = get_settings()

# ── Import ALL models via Base so autogenerate sees them ────────────────────
# Importing Base automatically registers all mapped subclasses (User,
# Transaction, Device, etc.) with the metadata.
from app.models import Base  # noqa: F401 — side-effects matter here

# ── Alembic config ───────────────────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url from alembic.ini with the value from .env.
# This ensures a single source of truth for the connection string.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic which metadata to compare against for autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline mode: emit migration SQL to stdout without a live DB connection.
    Useful for generating SQL scripts for DBAs or CI/CD review.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the live database and apply migrations directly.
    This is the default mode used when running `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
