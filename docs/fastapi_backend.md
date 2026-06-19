# modernpackage — FastAPI Backend

[overview.md](overview.md)

When scaffolded with the `--backend` flag (or `--fastapi` alias), `modernpackage` generates a 
complete, production-ready async FastAPI service with async SQLAlchemy 2.0 + asyncpg, 
Kubernetes-style health probes, Alembic async migrations, and Docker containerization. 
This document describes the generated backend template structure, application patterns, 
and development workflow for generated backend packages. For containerization details, see [containerization.md](containerization.md).

## Application Structure & DI

### Layout and Routing

FastAPI applications follow two common patterns for module organization. For single-domain
services with limited scope, the **module-by-type** pattern groups files by responsibility:
`routers/`, `models/`, `schemas/`, `crud/`. Beyond a toy project, the **module-by-feature**
pattern (e.g., `src/auth/{router,schemas,models,service,dependencies,config}.py`) is the
dominant recommendation, as it co-locates related logic and scales better as features grow
(per [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) and
[Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)).

**APIRouter** is the building block for nested endpoints. Create routers with
`APIRouter(prefix=..., tags=..., dependencies=[...])` to group related endpoints,
then assemble them via `app.include_router(...)`. Using a settings constant like
`settings.API_V1_STR = "/api/v1"` allows versioning routes consistently across the app.

### Settings and Configuration

Use **pydantic-settings** `BaseSettings` (a separate install since FastAPI 0.100) for
configuration. Define settings with `model_config = SettingsConfigDict(env_file=".env")`,
which is the Pydantic v2 replacement for the inner `class Config` pattern. Wrap the settings
function in `@lru_cache` to read the `.env` file only once, and inject it via `Depends`
so tests can override it:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")  # Pydantic v2; NOT inner class Config
    database_url: str
    api_v1_str: str = "/api/v1"

@lru_cache
def get_settings() -> Settings:
    return Settings()  # .env read once
```

### Lifespan and Application State

**Lifespan** is the modern async-context-manager approach to managing application startup
and shutdown (since FastAPI 0.93.0). Define an `@asynccontextmanager async def lifespan(app)`
function: resources are created before the `yield` statement, attached to `app.state`, and
disposed after the yield. This replaces the deprecated `@app.on_event("startup"/"shutdown")`
pattern:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: create resources
    engine = create_async_engine(get_settings().database_url)
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    yield
    # shutdown: dispose resources
    await engine.dispose()  # after yield: tear down

app = FastAPI(lifespan=lifespan)
```

### Dependency Injection

**Annotated** is the modern DI idiom (since FastAPI 0.95.0). Define module-level type aliases
combining a type and its dependency resolver:

```python
from typing import Annotated
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db(request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session

DbSessionDep = Annotated[AsyncSession, Depends(get_db)]

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: DbSessionDep):
    # db is an AsyncSession, resolved via the Depends callable
    ...
```

### Anti-patterns to Avoid

- **`@app.on_event("startup"/"shutdown")`** — deprecated since FastAPI 0.93.0 (Feb 2023);
  silently skipped if a `lifespan` is present and cannot be mixed. Use `@asynccontextmanager`
  lifespan instead.
- **`param: T = Depends(fn)` legacy DI style** — prefer `Annotated[T, Depends(fn)]` since 0.95.0
  for clarity and better tooling support.
- **Pydantic inner `class Config`** — use `SettingsConfigDict` instead.

---

## SQLAlchemy 2.0 Async + asyncpg

### Engine and Connection Pool

The **async engine** uses PostgreSQL's native async dialect via asyncpg. Create it with
`create_async_engine("postgresql+asyncpg://user:pw@host:5432/db")`. The `+asyncpg` suffix
is the only async PostgreSQL dialect supported by SQLAlchemy 2.0 (per the
[SQLAlchemy asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)).
Connection-string arguments are passed verbatim to asyncpg via `connect_args` — for example,
`connect_args={"statement_cache_size": 0}` when running behind pgBouncer in transaction or
statement mode (which breaks asyncpg's per-connection prepared-statement cache; pgBouncer
1.21+ has experimental support).

**Pooling strategy** depends on the deployment pattern. By default, `create_async_engine`
uses `AsyncAdaptedQueuePool` — **never** pass `poolclass=QueuePool` directly, as it is
not compatible with asyncio. In production, enable `pool_pre_ping=True` to detect stale
connections. For serverless or ephemeral deployments behind an external connection pooler,
use `poolclass=NullPool` to avoid connection caching:

```python
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Standard deployment
engine = create_async_engine("postgresql+asyncpg://...", pool_pre_ping=True)

# Behind external pooler (pgBouncer, Neon, Supabase, etc.)
engine = create_async_engine("postgresql+asyncpg://...", poolclass=pool.NullPool)

# Behind pgBouncer in transaction/statement mode (statement cache breaks)
engine = create_async_engine(
    "postgresql+asyncpg://...",
    connect_args={"statement_cache_size": 0}
)
```

### Async Session Factory

**async_sessionmaker** is the 2.0 typed replacement for `sessionmaker(class_=AsyncSession)`.
The critical configuration is `expire_on_commit=False` — the default `True` causes implicit
lazy I/O after commit, which triggers `MissingGreenlet` or `greenlet_spawn` errors in async
contexts:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)  # REQUIRED for async
```

### Session-per-Request Dependency

Each request gets its own session via an async-generator dependency. FastAPI calls the
generator once per request, yields the session to the endpoint, then runs cleanup on the
way out:

```python
from collections.abc import AsyncIterator

async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
        # Commit or rollback happens here (implicit or explicit in the endpoint)
```

**Important:** `AsyncSession` is **not safe for use in multiple concurrent tasks**.
Each async request gets exactly one session to avoid cross-request contamination.

### Model Definition

SQLAlchemy 2.0 models use `class Base(DeclarativeBase)` (replacing `declarative_base()`)
and the `AsyncAttrs` mixin for awaitable relationship accessors. Use `Mapped[T]` type hints
and `mapped_column()` to define columns — the type annotation automatically infers `NOT NULL`
constraints:

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)  # NOT NULL from Mapped[str]
    name: Mapped[str]
```

**Lazy loading is not viable in async contexts.** Use `selectinload()` or `joinedload()` to
eagerly load relationships:

```python
from sqlalchemy.orm import selectinload
from sqlalchemy import select

# Eager load in the query
stmt = select(User).options(selectinload(User.posts)).where(User.id == user_id)
user = await db.scalar(stmt)
```

### Anti-patterns to Avoid

- **`sessionmaker(class_=AsyncSession)`** — use `async_sessionmaker` instead.
- **`declarative_base()`** — use `class Base(DeclarativeBase)` instead.
- **`poolclass=QueuePool` for async** — causes incompatibility errors; use the default
  `AsyncAdaptedQueuePool` or `NullPool` for serverless.
- **Default `expire_on_commit=True` in async** — causes `MissingGreenlet` errors; always
  set `expire_on_commit=False`.

---

## Alembic (Async Migrations)

### Async Environment Setup

Use the **async template** since Alembic 1.5.6: `alembic init -t async migrations`.
The `env.py` bridge runs Alembic's sync migration API on an async connection via
`await connection.run_sync(do_run_migrations)`, because Alembic does not provide an async API
directly (per the [Alembic asyncio docs](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)).
Always use `NullPool` for the migration engine — Alembic creates and disposes an
engine per run, so connection pooling is counterproductive:

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

Set the database URL in `env.py` from `os.environ` (e.g., `os.environ["DATABASE_URL"]`)
rather than hardcoding it in `alembic.ini`, so it can be injected at runtime or via CI/CD
secrets.

### Programmatic Migration Execution

For advanced use cases (e.g., running migrations from within an async context), pass an
existing async connection via `cfg.attributes["connection"]` to avoid nested `asyncio.run()`
calls:

```python
async def run_migrations_programmatic(db_url: str):
    engine = create_async_engine(db_url, poolclass=pool.NullPool)
    async with engine.connect() as conn:
        cfg = Config("alembic.ini")
        cfg.attributes["connection"] = conn
        # Alembic will use the provided connection instead of creating one
        command.upgrade(cfg, "head")
    await engine.dispose()
```

### Autogenerate Limitations

Autogenerate (`alembic revision --autogenerate`) detects table/column add/remove, nullable,
basic indexes/unique/foreign-key constraints, and **column type changes** (compare_type defaults
`True` since Alembic 1.12.0). It **misses** column renames (appears as drop+add), anonymously-named
or CHECK constraints, sequences, and server defaults — "not intended to be perfect." Always
review autogenerated migrations and rewrite when needed.

### Naming Convention

Define `MetaData(naming_convention={...})` on the declarative base so constraint names are
deterministic and autogenerate produces reproducible migrations:

```python
from sqlalchemy import MetaData

naming_convention = {
    "ix": "ix_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)
```

### Migration Commands

- **`alembic upgrade head`** — idempotent; reads the `alembic_version` table and applies
  pending migrations.
- **`alembic revision --autogenerate -m "message"`** — generates a new migration by comparing
  models to the database schema.
- **`alembic check`** (since Alembic 1.9.0) — fails CI if any model has drifted from the latest
  migration; run this before deployment to catch untracked schema changes.

These commands should be wrapped as `just migrate`, `just makemigration`, and
`just migration-check` recipes in the scaffolder (exact recipe wording deferred).

### Anti-patterns to Avoid

- Running Alembic with a connection pool that persists across commands — use `NullPool`.
- Relying on autogenerate to catch renames, CHECK constraints, or server defaults — review
  and hand-edit when needed.

---

## Dependencies & Containerization (uv)

### Dependency Management with uv

**uv.lock** is a committed, never-hand-edited universal lockfile that ensures reproducible
builds across all platforms. `.venv` is git-ignored and rebuilt on each machine. Use
`uv add [--dev | --group X | --optional X]` to update `pyproject.toml` and `uv.lock`
atomically.

**PEP 735 dependency groups** (`[dependency-groups]`) are **local-only** — excluded from
built distributions. **PEP 621 optional dependencies** (`[project.optional-dependencies]`)
are **published** to PyPI. The `dev` group is typically installed by default in development.
This repo already uses the PEP 735 form — see `pyproject.toml:27-37` (`[dependency-groups] dev = [...]`).

### Reproducible and CI Workflows

- **`uv sync --locked`** — errors if the lockfile is stale, ensuring CI always uses a fresh
  lock.
- **`uv sync --frozen`** — skips the freshness check (fastest for Docker/CI), installing
  straight from the lockfile without verifying dependencies are current.
- **`uv lock --check`** — verifies the lockfile is up-to-date without installing.

### Container Integration

For containerization, consult [containerization.md](containerization.md) for:
- **Multi-stage Containerfile** — see *Example Containerfile* for the `uv` build pipeline,
  bind-mount caching strategy, and `UV_*` environment variables.
- **App + Postgres Compose Stack** — see *Example: App + Postgres Stack* for the
  service-dependency order and `service_completed_successfully` health-check gating.
- **Startup Ordering** — see *Startup Ordering* for ensuring migrations run before the app.

### Multi-Replica Migration Safety

When multiple app replicas run concurrently, **never run migrations at app startup** — concurrent
DDL causes deadlocks. Instead:

1. **Create a one-shot `migrate` service** in `compose.yml` that runs `alembic upgrade head`
   and exits.
2. **Make the app service depend on `migrate`** via `service_completed_successfully`.
3. **Run on a direct, non-pooled connection** — Alembic's advisory lock is unreliable through
   transaction-mode poolers like pgBouncer. Use `poolclass=NullPool` and pass the database URL
   directly, bypassing any pooler.

This pattern ensures migrations run exactly once before the app starts, preventing replica
contention and deadlock.

---

## Testing with DI Overrides

### Dependency Overrides

**`app.dependency_overrides`** is a dict mapping the original callable to a test override.
To test endpoints that depend on `get_db` or `get_settings`, override them:

```python
@pytest.fixture(autouse=True)
def _override_db():
    async def test_get_db() -> AsyncIterator[AsyncSession]:
        # Use a test session (in-memory DB, transaction rollback, etc.)
        async with test_sessionmaker() as session:
            yield session
    
    app.dependency_overrides[get_db] = test_get_db
    yield
    app.dependency_overrides.clear()  # teardown even on failure
```

**Note:** Override the dependency (the function called by `Depends`), not the `@lru_cache`
settings function itself. Override `get_settings` (the resolver), not the cached `Settings`
instance.

### Async HTTP Clients

**httpx.AsyncClient** is the modern choice for testing async apps. Since httpx **0.27**, the
`app=` shortcut is deprecated; **0.28 removed it entirely**. Use `ASGITransport` instead:

```python
from httpx import ASGITransport, AsyncClient

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)  # NOT the removed app= shortcut (httpx 0.28)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

**Avoid** Starlette's `TestClient` for async resource sharing — it runs in a background thread
and cannot safely share async resources like database sessions ("Future attached to a different loop" errors).

### Lifespan in Tests

By default, `ASGITransport` does not fire the lifespan events. Wrap it with `LifespanManager`
from `asgi-lifespan` to ensure startup/shutdown run:

```python
from asgi_lifespan import LifespanManager

@pytest.fixture
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
```

### Isolated Test Databases

Four common patterns for test isolation:

1. **Create/drop per test** — simplest but slow: `await Base.metadata.create_all(engine)` before
   each test, then drop. Useful for quick unit tests.
2. **Transactional rollback** — wrap the test session in a savepoint and rollback at the end:
   ```python
   AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
   ```
   Fast and clean, but requires a dedicated test connection.
3. **Per-test database** — `pytest-postgresql` plugin spawns a fresh DB per test. Slower but
   closest to production.
4. **testcontainers-python** — spin up a PostgreSQL container per test suite:
   ```python
   from testcontainers.postgres import PostgresContainer
   with PostgresContainer("postgres:16", driver="asyncpg") as postgres:
       db_url = postgres.get_connection_url()
   ```

### Async Fixtures

pytest-asyncio simplifies async test writing. Set `asyncio_mode = "auto"` in `pyproject.toml`
to auto-detect and run async functions. The `event_loop` fixture was **removed in 1.0** —
use `loop_scope` instead to share a single event loop across tests. To avoid cross-loop reuse
errors, either share one loop and a single connection pool, or use `NullPool` (per Phase 3).

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Anti-patterns to Avoid

- **httpx `app=` shortcut** (removed in 0.28) — use `transport=ASGITransport(app=app)` instead.
- **Starlette `TestClient` for async resource sharing** — causes "Future attached to a different loop"
  errors. Use `ASGITransport` + `AsyncClient`.
- **pytest-asyncio `event_loop` fixture** (removed in 1.0) — use `loop_scope` instead.

---

## Health Checks

### Probe Semantics

Understanding Kubernetes probe semantics is critical:

- **Liveness** failure → **restart** the container. Use for: app is hung/stuck.
- **Readiness** failure → **remove from Service endpoints** (no restart). Use for: app is temporarily unavailable (slow boot, DB connection lost).
- **Startup** → gates liveness/readiness until the app finishes initialization.

**Critically: DB connectivity checks belong in readiness, not liveness.** A DB outage will cause
a cluster-wide restart loop that does not fix the database. Reserve liveness for detecting hung
processes that can be restarted; use readiness to signal temporary unavailability.

### Endpoint Implementation

**Liveness** should be trivial and never touch the DB — just return a 200 status:

```python
@app.get("/livez")
async def livez():
    return {"status": "pass"}
```

**Readiness** checks dependencies and returns `status_code=503` (HTTP 503 Service Unavailable)
on failure. **Never** return 200 with a `{"status": "fail"}` body — monitors read the status code,
not the body. Run multiple checks concurrently with `asyncio.gather`:

```python
import asyncio
from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import text

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

### Database Connectivity Check

Use `SELECT 1` as the database health signal. Wrap it in `asyncio.timeout()` and a broad
`except Exception` to catch all failures (network, timeout, auth, query errors). Set the
internal timeout **shorter than the probe's `timeoutSeconds`** to give the probe a chance to
record the failure cleanly.

### Standards and Conventions

- **K8s endpoints**: Use `/livez` and `/readyz` (`-z` suffix). `/healthz` is deprecated since
  Kubernetes v1.16.
- **IETF draft standard**: Media type `application/health+json` with status field `"pass"`,
  `"fail"`, or `"warn"` (per [draft-inadarei-api-health-check-06](https://datatracker.ietf.org/doc/draft-inadarei-api-health-check/)).
- **Managed library**: [fastapi-health](https://github.com/AlexeyFitlov/fastapi-health) provides
  composable health checks if you need structured probe composition.

### Container and Compose Integration

For the container-level health check and compose service orchestration, consult
[containerization.md](containerization.md) → *Healthchecks* for the stdlib `HEALTHCHECK`
instruction and how to align readiness terminology between the app and the container.
