"""Alembic async migration environment (bridges sync migration API onto async)."""

import asyncio
import os

from alembic import context
from modernpackage.db import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    config_section = context.config.get_section(
        context.config.config_ini_section, {}
    )
    config_section['sqlalchemy.url'] = os.environ['DATABASE_URL']
    engine = async_engine_from_config(config_section, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
