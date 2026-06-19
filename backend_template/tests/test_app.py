from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self, cast

from fastapi.testclient import TestClient
from modernpackage.app import create_app
from modernpackage.db import create_engine, get_db
from modernpackage.health import database_ready
from sqlalchemy.ext.asyncio import async_sessionmaker

if TYPE_CHECKING:
    from fastapi import Request


class _FakeConnection:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        if self._fail:
            raise RuntimeError('db down')


class _FakeEngine:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    def connect(self) -> _FakeConnection:
        return _FakeConnection(fail=self._fail)


def _request_with_engine(*, fail: bool) -> Request:
    state = SimpleNamespace(engine=_FakeEngine(fail=fail))
    return cast('Request', SimpleNamespace(app=SimpleNamespace(state=state)))


def test_livez_returns_pass() -> None:
    with TestClient(create_app()) as client:
        response = client.get('/livez')
    assert response.status_code == 200
    assert response.json() == {'status': 'pass'}


def test_readyz_pass_when_database_ready() -> None:
    app = create_app()
    app.dependency_overrides[database_ready] = lambda: True
    with TestClient(app) as client:
        response = client.get('/readyz')
    assert response.status_code == 200
    assert response.json() == {'status': 'pass'}


def test_readyz_fail_when_database_unavailable() -> None:
    app = create_app()
    app.dependency_overrides[database_ready] = lambda: False
    with TestClient(app) as client:
        response = client.get('/readyz')
    assert response.status_code == 503
    assert response.json() == {'status': 'fail'}


def test_database_ready_true_on_successful_select() -> None:
    assert asyncio.run(database_ready(_request_with_engine(fail=False))) is True


def test_database_ready_false_on_error() -> None:
    assert asyncio.run(database_ready(_request_with_engine(fail=True))) is False


def test_get_db_yields_session() -> None:
    async def _run() -> object:
        engine = create_engine()
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        request = cast(
            'Request',
            SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
                sessionmaker=sessionmaker,
            ))),
        )
        generator = get_db(request)
        session = await anext(generator)
        await generator.aclose()
        await engine.dispose()
        return session

    assert asyncio.run(_run()) is not None
