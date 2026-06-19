"""Async SQLAlchemy engine, session factory, and FastAPI session dependency."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated, cast

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Default targets the compose `db` service; overridden via env in real deploys.
_DEFAULT_DATABASE_URL = 'postgresql+asyncpg://appuser:secret@db:5432/appdb'

# Deterministic constraint names so Alembic autogenerate stays reproducible.
_NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base carrying the shared, deterministic metadata."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


def database_url() -> str:
    """Return the configured database URL (env `DATABASE_URL` or compose default)."""
    return os.environ.get('DATABASE_URL') or _DEFAULT_DATABASE_URL


def create_engine() -> AsyncEngine:
    """Create the async engine (lazy — opens no connection until first use)."""
    return create_async_engine(database_url())


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield one `AsyncSession` per request from the app-state session factory."""
    sessionmaker = cast(
        'async_sessionmaker[AsyncSession]', request.app.state.sessionmaker
    )
    async with sessionmaker() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
