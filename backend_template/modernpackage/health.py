"""Kubernetes-style liveness and readiness probes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter()

_READINESS_TIMEOUT_SECONDS = 2.0


async def database_ready(request: Request) -> bool:
    """Return True when a `SELECT 1` succeeds within the readiness timeout."""
    engine: AsyncEngine = request.app.state.engine
    try:
        async with asyncio.timeout(_READINESS_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text('SELECT 1'))
    except Exception:  # noqa: BLE001 - any failure means not-ready
        return False
    return True


@router.get('/livez')
async def livez() -> dict[str, str]:
    """Liveness probe — never touches the database."""
    return {'status': 'pass'}


@router.get('/readyz')
async def readyz(
    ready: Annotated[bool, Depends(database_ready)],
) -> JSONResponse | dict[str, str]:
    """Readiness probe — 200 when the DB answers, 503 otherwise."""
    if not ready:
        return JSONResponse(
            {'status': 'fail'},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return {'status': 'pass'}
