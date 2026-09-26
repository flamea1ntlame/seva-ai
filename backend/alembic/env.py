import asyncio
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

import sys
import os

# Add parent directory to path so app modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.database import Base
from app.models import User, CitizenProfile, Document, Service, Application, ApplicationEvent, Consent, AuditLog

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    url = settings.SYNC_DATABASE_URL or settings.DATABASE_URL
    if "://" in url:
        scheme, rest = url.split("://", 1)
        if scheme in (
            "postgresql",
            "postgres",
            "postgresql+asyncpg",
            "postgresql+psycopg",
            "postgresql+psycopg3",
            "postgresql+psycopg2",
        ):
            return f"postgresql+psycopg2://{rest}"
    return url


def run_migrations_offline() -> None:
    url = get_url()
    is_sqlite = "sqlite" in url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
