# Implementation Plan

## Overview

Add a single new reference page, `docs/fastapi_backend.md`, documenting current (2026)
best practices for building a production-grade async FastAPI backend (app structure/DI,
SQLAlchemy 2.0 async + asyncpg, async Alembic, `uv` deps + containerization, DI-override
testing, health checks), and register it in the `docs/overview.md` index. Docs only — no
backend code, `Containerfile`, `compose.yml`, or scaffolder changes.

## Assumptions & Resolved Questions

- **Line-number corrections from the structure outline.** The structure/design cited
  `pyproject.toml:30-40` and `docs/overview.md:19-29`; the live files put the
  `[dependency-groups] dev = [...]` block at **`pyproject.toml:27-37`** and the
  "Documentation Files" table at **`docs/overview.md:21-29`** (header rows 21–22, data
  rows 23–29). This plan uses the verified numbers. If the files shift before
  implementation, re-grep (`grep -n 'dependency-groups' pyproject.toml`,
  `grep -n 'Documentation Files' docs/overview.md`) and use the current values.
- **Containerization cross-ref anchors (verified live):** Example Containerfile
  `docs/containerization.md:66-106`; Healthchecks `docs/containerization.md:241-256`;
  Startup Ordering `docs/containerization.md:294-306`; App + Postgres stack
  `docs/containerization.md:308+`. Cross-references in the page name these sections by
  title (e.g. "see `docs/containerization.md` → *Example: App + Postgres Stack*") rather
  than hard line numbers, so they survive edits to that doc.
- **New overview row placement.** Insert the `fastapi_backend.md` row immediately after
  the `containerization.md` row (`docs/overview.md:27`), before the `README.md` row
  (line 28). Topical adjacency (both are forward-looking backend/infra docs).
- **No markdown linter exists.** `just check` runs Python gates only; it is unaffected by
  a docs-only change. Phase verification is therefore `grep`/`test`/`head`-based. `just
  check` is run once at the end purely to confirm nothing Python-side regressed.
- **Snippets are illustrative, minimal, and not executed.** Per design decision 4, only
  load-bearing easy-to-get-wrong idioms get fenced ```python``` examples; they are
  reference templates, never run or imported.
- **Every technical claim is traceable.** Each section carries the inline external named
  links already present in `research.md` and a `research.md:NN-MM` pointer in prose where
  a claim is non-obvious. In-repo references use `file:line`.

---

## Phase 1: Page skeleton + index registration

### Changes

#### 1. Create the page skeleton
**File**: `docs/fastapi_backend.md`
**Action**: create

Mirror the house-style of `docs/containerization.md:1-9` exactly: H1 on line 1, blank
line 2, backlink on line 3, blank line 4, forward-looking paragraph, then the six empty
section headers.

```markdown
# modernpackage — FastAPI Backend

[overview.md](overview.md)

`modernpackage` ships no FastAPI, SQLAlchemy, or Alembic code today (the repo is a
`uv`-managed package scaffolder, not a service). This document is a forward-looking
reference for building a production-grade async FastAPI backend, to prepare for a future
`--backend`/`--fastapi` scaffolder option. All code below is an illustrative template,
not a committed file. For container, compose, and migration-gating mechanics this page
cross-references [containerization.md](containerization.md) rather than restating them.

## Application Structure & DI

## SQLAlchemy 2.0 Async + asyncpg

## Alembic (Async Migrations)

## Dependencies & Containerization (uv)

## Testing with DI Overrides

## Health Checks
```

#### 2. Register the page in the docs index
**File**: `docs/overview.md`
**Action**: modify — insert one row after line 27 (the `containerization.md` row),
matching the existing `| [file](file) | **bold**: description. |` cell format.

```markdown
| [fastapi_backend.md](fastapi_backend.md) | **FastAPI backend**: async app structure & DI, SQLAlchemy 2.0 + asyncpg, async Alembic, uv deps, DI-override testing, health checks. Forward-looking reference. |
```

### Verification
#### Automated
- [x] `test -f docs/fastapi_backend.md` (exit 0)
- [x] `head -1 docs/fastapi_backend.md` == `# modernpackage — FastAPI Backend`
- [x] `sed -n '3p' docs/fastapi_backend.md` == `[overview.md](overview.md)`
- [x] `[ "$(grep -c '^## ' docs/fastapi_backend.md)" -eq 6 ]` (exactly six section headers)
- [x] `grep -q 'fastapi_backend.md' docs/overview.md`

#### Manual
- [x] `grep -q 'ships no FastAPI' docs/fastapi_backend.md` (forward-looking note present)
- [x] `grep -c 'fastapi_backend.md' docs/overview.md` returns `1` (single index row, no dup)
- [x] `git status --porcelain` lists only `docs/fastapi_backend.md` (new) and
  `docs/overview.md` (modified)

---

## Phase 2: Application Structure & DI section

Fills `## Application Structure & DI`. Sources: `research.md:13-46` (Q1).

### Changes

#### 1. Prose + idioms under `## Application Structure & DI`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover, in order:
- **Layout — two schools.** Module-by-type (`routers/`, `models/`, `schemas/`, `crud/`)
  for single-domain services; module-by-feature
  (`src/auth/{router,schemas,models,service,dependencies,config}.py`) as the dominant
  recommendation beyond a toy (`research.md:16-20`). Cite
  [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) and
  [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
- **Routers.** `APIRouter(prefix=..., tags=..., dependencies=[...])` as a "mini-FastAPI",
  assembled via `app.include_router(...)`; `api/v1` nesting under `settings.API_V1_STR`
  (`research.md:21-26`).
- **Settings.** `pydantic-settings` `BaseSettings` (separate install since FastAPI 0.100),
  `model_config = SettingsConfigDict(env_file=".env")`, wrapped in `@lru_cache`; inject
  via `Depends` for test overrides (`research.md:27-31`).
- **Lifespan.** `@asynccontextmanager async def lifespan(app)` — resources created before
  `yield`, attached to `app.state`, disposed after (`await engine.dispose()`).
- **DI.** `Annotated[T, Depends(fn)]` with module-level aliases.

Load-bearing snippet (lifespan + settings + DI alias):

```python
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")  # Pydantic v2; NOT inner class Config
    database_url: str

@lru_cache
def get_settings() -> Settings:
    return Settings()  # .env read once

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(get_settings().database_url)
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    yield
    await engine.dispose()  # after yield: tear down

app = FastAPI(lifespan=lifespan)

async def get_db(request) -> AsyncSession:  # full body in the SQLAlchemy section
    async with request.app.state.sessionmaker() as session:
        yield session

DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
```

#### 2. Explicit anti-pattern callouts
**File**: `docs/fastapi_backend.md`
**Action**: modify — add an "Avoid" list in this section:
- `@app.on_event("startup"/"shutdown")` — **deprecated since FastAPI 0.93.0** (Feb 2023);
  silently skipped if a `lifespan` is present, cannot be mixed (`research.md:32-38`).
- `param: T = Depends(fn)` legacy DI style — prefer `Annotated[...]` (**since 0.95.0**)
  (`research.md:39-41`).
- pydantic inner `class Config` — use `SettingsConfigDict` (`research.md:27-29`).

### Verification
#### Automated
- [x] `grep -q 'lifespan' docs/fastapi_backend.md`
- [x] `grep -q 'Annotated' docs/fastapi_backend.md`
- [x] `grep -q 'on_event' docs/fastapi_backend.md` (present as a flagged anti-pattern)
- [x] `grep -q '0.93.0' docs/fastapi_backend.md && grep -q '0.95.0' docs/fastapi_backend.md`
- [x] `[ "$(grep -c 'fastapi.tiangolo.com' docs/fastapi_backend.md)" -ge 1 ]`

#### Manual
- [x] `grep -q 'SettingsConfigDict' docs/fastapi_backend.md` and
  `grep -q 'lru_cache' docs/fastapi_backend.md`
- [x] `grep -q 'await engine.dispose()' docs/fastapi_backend.md` (after-yield teardown shown)
- [x] Section is non-empty: `awk '/^## Application Structure & DI/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Phase 3: SQLAlchemy 2.0 Async + asyncpg section

Fills `## SQLAlchemy 2.0 Async + asyncpg`. Sources: `research.md:50-91` (Q2). Establishes
the `+asyncpg` cross-cutting thread that Phases 4–7 back-reference (`research.md:258-260`).

### Changes

#### 1. Prose + idioms under `## SQLAlchemy 2.0 Async + asyncpg`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover:
- **Engine.** `create_async_engine("postgresql+asyncpg://...")` — `+asyncpg` is the only
  async PostgreSQL dialect; `connect_args` pass verbatim to asyncpg (`research.md:53-56`).
- **Session factory.** `async_sessionmaker(engine, expire_on_commit=False)` — the 2.0
  typed replacement for `sessionmaker(class_=AsyncSession)`. `expire_on_commit=False` is
  **required**: default post-commit expiry triggers implicit lazy I/O →
  `MissingGreenlet`/`greenlet_spawn` (`research.md:57-62`).
- **Session-per-request.** Async-generator dependency (full `get_db` body); a new session
  per request — `AsyncSession` "is not safe for use in multiple concurrent tasks"
  (`research.md:63-67`).
- **Pooling.** `create_async_engine` auto-uses `AsyncAdaptedQueuePool` — **never** pass
  `poolclass=QueuePool` ("not compatible with asyncio"); `pool_pre_ping=True` in prod;
  `NullPool` for serverless/ephemeral or behind an external pooler (`research.md:68-72`).
- **pgBouncer caveat.** asyncpg per-connection prepared-statement cache breaks under
  pgBouncer transaction/statement mode (`prepared statement "__asyncpg_stmt_N__" does not
  exist`); fix with `connect_args={"statement_cache_size": 0}` or unnamed statements;
  pgBouncer 1.21+ has experimental support (`research.md:73-79`).
- **Models.** `class Base(DeclarativeBase)` (replaces `declarative_base()`), `AsyncAttrs`
  mixin for `await obj.awaitable_attrs.rel`, `mapped_column()` + `Mapped[T]`; eager
  `selectinload`/`joinedload` instead of lazy loading (`research.md:80-84`).

Load-bearing snippet (`get_db` + factory + base):

```python
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_async_engine("postgresql+asyncpg://user:pw@host:5432/db", pool_pre_ping=True)
# Behind pgBouncer txn/statement mode: connect_args={"statement_cache_size": 0}
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)  # required for async

async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session  # commit/rollback in the endpoint or here

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)  # NOT NULL from Mapped[str]
```

#### 2. Anti-pattern callouts
**File**: `docs/fastapi_backend.md`
**Action**: modify — add "Avoid" list:
- `sessionmaker(class_=AsyncSession)` → use `async_sessionmaker` (`research.md:57-58`).
- `declarative_base()` → use `class Base(DeclarativeBase)` (`research.md:80-81`).
- `poolclass=QueuePool` for async (`research.md:68-69`).
- Default `expire_on_commit=True` in async (`research.md:58-60`).

### Verification
#### Automated
- [x] `grep -q 'postgresql+asyncpg' docs/fastapi_backend.md`
- [x] `grep -q 'expire_on_commit=False' docs/fastapi_backend.md`
- [x] `grep -q 'DeclarativeBase' docs/fastapi_backend.md`
- [x] `grep -q 'statement_cache_size' docs/fastapi_backend.md`
- [x] `[ "$(grep -c 'docs.sqlalchemy.org' docs/fastapi_backend.md)" -ge 1 ]`

#### Manual
- [x] `grep -q 'async_sessionmaker' docs/fastapi_backend.md` and
  `grep -q 'MissingGreenlet' docs/fastapi_backend.md` (rationale present)
- [x] `grep -q 'AsyncAdaptedQueuePool' docs/fastapi_backend.md` and
  `grep -q 'NullPool' docs/fastapi_backend.md`
- [x] Section non-empty:
  `awk '/^## SQLAlchemy 2.0 Async/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Phase 4: Alembic (Async Migrations) section

Fills `## Alembic (Async Migrations)`. Sources: `research.md:94-129` (Q3).

### Changes

#### 1. Prose + idioms under `## Alembic (Async Migrations)`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover:
- **Async env.py bridge.** `alembic init -t async migrations` (async template since 1.5.6);
  `env.py` uses `async_engine_from_config(..., poolclass=pool.NullPool)` (`NullPool`
  because Alembic creates/disposes an engine per run) and bridges Alembic's *sync*
  migration API via `await connection.run_sync(do_run_migrations)`. Alembic "does not
  provide an async API directly." URL is `postgresql+asyncpg://`, set in `env.py` from
  `os.environ` rather than hardcoded in `alembic.ini` — **back-reference the `+asyncpg`
  thread (Phase 3)** (`research.md:97-105`).
- **Programmatic run** (optional): pass an existing connection via
  `cfg.attributes["connection"]` to avoid `asyncio.run` inside a running loop
  (`research.md:106-109`).
- **Autogenerate caveats.** Detects table/column add/remove, nullable, basic
  index/unique/FK, and **column type changes (`compare_type` defaults True since 1.12.0)**.
  **Misses** renames (drop+add), anonymously-named/CHECK constraints, sequences, server
  defaults — "not intended to be perfect", always review (`research.md:110-115`).
- **Naming convention.** Define `MetaData(naming_convention={...})` on the base so
  constraint names are deterministic and autogenerate reproducible (`research.md:116-122`).
- **Commands.** `alembic upgrade head` (idempotent, reads `alembic_version`),
  autogenerate, and `alembic check` (**since 1.9.0**) to fail CI on model drift
  (`research.md:123-129`).
- **Justfile note (deferred).** State these commands should become `just migrate` /
  `just makemigration` / `just migration-check` recipes in the scaffolder; exact recipe
  wording deferred (`research.md` Q3; design decision 7).

Load-bearing snippet (async env.py bridge):

```python
# migrations/env.py (async template)
import asyncio, os
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    config_section = context.config.get_section(context.config.config_ini_section)
    config_section["sqlalchemy.url"] = os.environ["DATABASE_URL"]  # postgresql+asyncpg://...
    engine = async_engine_from_config(config_section, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)  # sync API bridged onto async conn
    await engine.dispose()

asyncio.run(run_async_migrations())
```

### Verification
#### Automated
- [x] `grep -q 'run_sync' docs/fastapi_backend.md`
- [x] `grep -q 'alembic check' docs/fastapi_backend.md`
- [x] `grep -q 'NullPool' docs/fastapi_backend.md`
- [x] `grep -q '1.12.0' docs/fastapi_backend.md && grep -q '1.9.0' docs/fastapi_backend.md`
- [x] `[ "$(grep -c 'alembic.sqlalchemy.org' docs/fastapi_backend.md)" -ge 1 ]`

#### Manual
- [x] `grep -q 'async_engine_from_config' docs/fastapi_backend.md`
- [x] `grep -q 'just migrate' docs/fastapi_backend.md` (deferred-Justfile note present)
- [x] `grep -q 'compare_type' docs/fastapi_backend.md`
- [x] Section non-empty:
  `awk '/^## Alembic/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Phase 5: Dependencies & Containerization (uv) section

Fills `## Dependencies & Containerization (uv)`. Sources: `research.md:133-174` (Q4).
**Cross-references** `docs/containerization.md` instead of restating build/compose/health
mechanics (design decision 3); adds only the backend-specific migration-replica layer.

### Changes

#### 1. Prose under `## Dependencies & Containerization (uv)`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover:
- **uv deps.** `uv.lock` is a committed, never-hand-edited universal lockfile; `.venv` is
  git-ignored. `uv add [--dev | --group X | --optional X]` updates `pyproject.toml` +
  `uv.lock` atomically (`research.md:136-141`).
- **PEP 735 groups vs extras.** `[dependency-groups]` (PEP 735) are **local-only**
  (excluded from built dists); `[project.optional-dependencies]` (extras) are **published**
  to PyPI. `dev` group installed by default. **In-repo cite:** this repo already uses the
  `[dependency-groups] dev = [...]` form at **`pyproject.toml:27-37`** (`research.md:143-144`).
- **Reproducible/CI.** `uv sync --locked` errors on a stale lockfile; `--frozen` skips the
  check (fastest, for Docker/CI); `uv lock --check` verifies without installing
  (`research.md:145-150`).
- **Cross-reference, don't restate.** Link `docs/containerization.md` for: the multi-stage
  `uv` Containerfile (→ *Example Containerfile*), the App+Postgres compose stack (→
  *Example: App + Postgres Stack*), and `service_completed_successfully` migration gating
  (→ *Startup Ordering*) (`research.md:151-174`; `docs/containerization.md:66-106`,
  `:294-306`, `:308+`).
- **Backend-only layer to add here:** multi-replica migration safety — run migrations in a
  **one-shot `migrate` service**, *not* at app startup (concurrent DDL deadlock with
  multiple replicas); the Alembic advisory lock is unreliable through transaction-mode
  poolers, so run migrations on a **direct, non-pooled** connection (`research.md:166-174`).

Reference the in-repo grouping form with a `file:line` cite:

```markdown
This repo already uses the PEP 735 form — see `pyproject.toml:27-37`
(`[dependency-groups] dev = [...]`).
```

### Verification
#### Automated
- [x] `grep -q 'containerization.md' docs/fastapi_backend.md` (cross-ref present)
- [x] `grep -q 'dependency-groups' docs/fastapi_backend.md`
- [x] `grep -q 'pyproject.toml:' docs/fastapi_backend.md` (a `file:line` cite is present)
- [x] `grep -q 'uv.lock' docs/fastapi_backend.md`
- [x] `grep -q 'service_completed_successfully' docs/fastapi_backend.md`

#### Manual
- [x] The cited line range exists and is the dependency-groups block:
  `sed -n '27,37p' pyproject.toml | grep -q 'dev = \['`
- [x] `grep -q 'one-shot' docs/fastapi_backend.md` and `grep -q 'replica' docs/fastapi_backend.md`
  (multi-replica migration-safety note present)
- [x] `grep -q 'non-pooled' docs/fastapi_backend.md` or `grep -q 'direct' docs/fastapi_backend.md`
- [x] Section non-empty:
  `awk '/^## Dependencies & Containerization/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Phase 6: Testing with DI Overrides section

Fills `## Testing with DI Overrides`. Sources: `research.md:178-213` (Q5).
Back-references the `expire_on_commit=False` / `NullPool` thread (Phase 3).

### Changes

#### 1. Prose + idioms under `## Testing with DI Overrides`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover:
- **`app.dependency_overrides`.** Dict mapping original callable → override; override
  `get_db` with a test-session generator and `get_settings` (override the dependency, not
  the `@lru_cache` function). Clean up via a `yield`/`autouse` fixture calling
  `app.dependency_overrides.clear()` (`research.md:181-187`).
- **Async clients.** `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`
  is the modern form. httpx **0.27 deprecated** the `app=` shortcut, **0.28 removed it**.
  Starlette `TestClient` is sync-only (background-thread loop → "Future attached to a
  different loop" when sharing async resources) (`research.md:188-194`).
- **Lifespan in tests.** ASGITransport does not fire lifespan; wrap with
  `LifespanManager(app)` from `asgi-lifespan` (`research.md:195-197`).
- **Isolated test DBs (4 patterns).** (a) `create_all`/`drop_all` per test; (b)
  transactional rollback with
  `AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)`;
  (c) per-test DB via `pytest-postgresql`; (d) `testcontainers-python`
  (`PostgresContainer("postgres:16", driver="asyncpg")`) (`research.md:198-205`).
- **Async fixtures.** pytest-asyncio `asyncio_mode = "auto"`; the `event_loop` fixture was
  **removed in 1.0** — use `loop_scope`. Share one loop + pool, or use `NullPool` to avoid
  cross-loop reuse errors — **back-reference Phase 3** (`research.md:206-213`).

Load-bearing snippet (override + async client):

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.fixture(autouse=True)
def _override_db():
    app.dependency_overrides[get_db] = _test_get_db  # test-session generator
    yield
    app.dependency_overrides.clear()  # teardown even on failure

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)  # NOT the removed app= shortcut (httpx 0.28)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

#### 2. Anti-pattern callouts
**File**: `docs/fastapi_backend.md`
**Action**: modify — add "Avoid" list:
- httpx `app=` shortcut (removed **0.28**) → `transport=ASGITransport(app=app)`.
- Starlette `TestClient` for async resource sharing (`research.md:191-194`).
- pytest-asyncio `event_loop` fixture (removed **1.0**) → `loop_scope` (`research.md:206-208`).

### Verification
#### Automated
- [x] `grep -q 'dependency_overrides' docs/fastapi_backend.md`
- [x] `grep -q 'ASGITransport' docs/fastapi_backend.md`
- [x] `grep -q 'loop_scope' docs/fastapi_backend.md`
- [x] `grep -q '0.28' docs/fastapi_backend.md && grep -q '1.0' docs/fastapi_backend.md`

#### Manual
- [x] `grep -q 'LifespanManager' docs/fastapi_backend.md` (lifespan-in-tests note present)
- [x] `grep -q '.clear()' docs/fastapi_backend.md` (override teardown shown)
- [x] `grep -q 'testcontainers' docs/fastapi_backend.md` (isolated-DB patterns covered)
- [x] Section non-empty:
  `awk '/^## Testing with DI Overrides/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Phase 7: Health Checks section

Fills `## Health Checks`. Sources: `research.md:217-247` (Q6). Lead with
readiness-vs-liveness semantics (design decision 6), then the concrete impl, then the
container cross-ref.

### Changes

#### 1. Prose + idioms under `## Health Checks`
**File**: `docs/fastapi_backend.md`
**Action**: modify

Cover, in order:
- **Probe semantics first.** Liveness fail → **restart**; readiness fail → **remove from
  Service endpoints/LB** (no restart); startup → gates the others during slow boot. **DB
  checks belong in readiness, not liveness** — a DB outage in a liveness check causes a
  cluster-wide restart loop that does not fix the DB (`research.md:230-235`).
- **Endpoint impl.** Liveness = trivial 200 handler, no I/O. Readiness checks deps and
  returns `JSONResponse(status_code=503, ...)` (`status.HTTP_503_SERVICE_UNAVAILABLE`) on
  failure — never 200-with-`"fail"`-body (monitors read the status code); run multiple
  checks with `asyncio.gather` (`research.md:220-225`).
- **DB check.** `await conn.execute(text("SELECT 1"))` wrapped in `asyncio.timeout(2.0)`
  and a broad `except Exception`; internal timeout shorter than the probe's
  `timeoutSeconds` (`research.md:226-229`).
- **Conventions.** K8s `/livez` + `/readyz` (`-z` suffix; `/healthz` deprecated since
  v1.16); IETF `draft-inadarei-api-health-check-06` media type `application/health+json`
  (`status: "pass"/"fail"/"warn"`); library `fastapi-health` (`research.md:236-244`).
- **Cross-reference** `docs/containerization.md` → *Healthchecks* for the stdlib
  `HEALTHCHECK` probe and `/health` 200/503 (`research.md:246-247`;
  `docs/containerization.md:241-256`) — align readiness terminology with it, don't restate.

Load-bearing snippet (readiness):

```python
import asyncio
from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import text

@app.get("/livez")
async def livez():
    return {"status": "pass"}  # liveness: no I/O, never touches the DB

@app.get("/readyz")
async def readyz():
    try:
        async with asyncio.timeout(2.0):  # shorter than the probe's timeoutSeconds
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "fail"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return {"status": "pass"}
```

### Verification
#### Automated
- [x] `grep -q 'SELECT 1' docs/fastapi_backend.md`
- [x] `grep -q 'readiness' docs/fastapi_backend.md && grep -q 'liveness' docs/fastapi_backend.md`
- [x] `grep -q '503' docs/fastapi_backend.md`
- [x] `grep -q 'containerization.md' docs/fastapi_backend.md` (HEALTHCHECK cross-ref)

#### Manual
- [x] `grep -q 'restart loop' docs/fastapi_backend.md` (liveness-DB rationale present)
- [x] `grep -q 'asyncio.timeout' docs/fastapi_backend.md`
- [x] `grep -q '/readyz' docs/fastapi_backend.md` and `grep -q '/livez' docs/fastapi_backend.md`
- [x] `grep -q 'application/health+json' docs/fastapi_backend.md`
- [x] Section non-empty:
  `awk '/^## Health Checks/{f=1;next}/^## /{f=0}f' docs/fastapi_backend.md | grep -q '[^[:space:]]'`

---

## Final Verification (all phases)

#### Automated
- [ ] All six sections non-empty (no empty `##` followed immediately by another `##`):
  run the six `awk ... | grep -q` section checks above; all exit 0.
- [ ] External citations present:
  `[ "$(grep -c '://' docs/fastapi_backend.md)" -ge 6 ]` (≥1 per section, in practice more).
- [ ] Index row intact: `grep -q 'fastapi_backend.md' docs/overview.md` and table still
  parses (`grep -c '^| \[' docs/overview.md` increased by exactly 1 vs. pre-change count).
- [ ] `just check` passes (docs-only change must not regress Python gates).

#### Manual
- [ ] Scope guard — only the two doc files changed, no backend/container files added:
  `git status --porcelain` shows exactly `?? docs/fastapi_backend.md` and
  ` M docs/overview.md`; **no** `Containerfile`, `compose.yml`, `*.py`, or
  `modernpackage/` changes.
- [ ] Release pins all present:
  `for v in 0.93.0 0.95.0 0.100 1.12.0 1.9.0 0.28 1.0; do grep -q "$v" docs/fastapi_backend.md || echo "MISSING $v"; done`
  prints nothing.
- [ ] House-style intact: `head -1` is the H1, line 3 is the backlink, forward-looking
  paragraph present (`grep -q 'ships no FastAPI' docs/fastapi_backend.md`).
- [ ] No duplicate of `docs/containerization.md` content — the page references it by
  section title and adds only the backend-specific migration/readiness layer (spot-check
  that no multi-stage Containerfile or compose YAML block was pasted in:
  `grep -q 'FROM ghcr.io/astral-sh/uv' docs/fastapi_backend.md` should return **non-zero**
  / no match).
