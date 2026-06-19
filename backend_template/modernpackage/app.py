"""FastAPI application factory with async engine lifespan management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from modernpackage.db import create_engine
from modernpackage.health import router as health_router
from sqlalchemy.ext.asyncio import async_sessionmaker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create engine + session factory on startup; dispose engine on shutdown."""
    engine = create_engine()
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(lifespan=lifespan)
    app.include_router(health_router)
    return app
