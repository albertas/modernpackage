# Research Findings

**Scope note:** `questions.md` asks for *current (2026) external best practices* for async FastAPI
backends (FastAPI, SQLAlchemy 2.0, asyncpg, Alembic, `uv`, containers). The `modernpackage` repo
itself ships **no** FastAPI/SQLAlchemy/Alembic code — it is a `uv`-managed Python *package
scaffolder* (`modernpackage/main.py`, `modernpackage/__init__.py`; `pyproject.toml:1-90`). Findings
below are therefore sourced from authoritative external docs. The repo's
`docs/containerization.md` is the one in-repo artifact that already documents container guidance and
is cross-referenced for Q4 to align terminology and avoid duplication.

---

## Q1: How are production FastAPI applications structured today (layout, routers, settings, lifespan, DI)?

### Findings
- **Layout — two schools.** *Module-by-type* (`routers/`, `models/`, `schemas/`, `crud/`) suits
  single-domain microservices; *module-by-feature/domain* (`src/auth/{router,schemas,models,
  service,dependencies,config}.py`, `src/posts/...`) is the dominant recommendation beyond a toy.
  Source: [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices),
  [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
- **Routers.** `APIRouter(prefix=..., tags=..., dependencies=[...], responses={...})` acts as a
  "mini-FastAPI"; assemble in `main.py` via `app.include_router(...)`. Path strings must not repeat
  the prefix. Versioning nests `api/v1/`, `api/v2/` sub-routers included under prefixes
  (`settings.API_V1_STR`). Source:
  [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
  [christophergs pt.8](https://christophergs.com/tutorials/ultimate-fastapi-tutorial-pt-8-project-structure-api-versioning/).
- **Settings.** `pydantic-settings` `BaseSettings` (separate install since FastAPI 0.100), Pydantic
  v2 style via `model_config = SettingsConfigDict(env_file=".env", ...)` (not the deprecated inner
  `class Config`). Wrap instantiation in `@lru_cache` so `.env` is read once; inject via `Depends`
  for test overrides. Source:
  [FastAPI Settings](https://fastapi.tiangolo.com/advanced/settings/).
- **Lifespan.** `@asynccontextmanager async def lifespan(app)` with code before/after `yield`
  replaces `@app.on_event("startup"/"shutdown")`, **deprecated since FastAPI 0.93.0** (Feb 2023);
  the two cannot be mixed (on_event silently skipped if lifespan present). Shared resources (DB
  engine, async_sessionmaker, HTTP client) are created before `yield`, attached to `app.state`, and
  disposed after `yield` (`await engine.dispose()`). Source:
  [FastAPI Events/Lifespan](https://fastapi.tiangolo.com/advanced/events/),
  [Starlette Lifespan](https://www.starlette.io/lifespan/).
- **Dependency injection.** `Depends()` on any callable; `Annotated[T, Depends(fn)]` is the
  recommended style since 0.95.0 (older `param: T = Depends(fn)` is legacy). Module-level
  `Annotated` aliases (`DbSessionDep = Annotated[AsyncSession, Depends(get_db)]`) reduce repetition.
  DB sessions provided per-request via generator dependency (`yield`); sub-dependencies form a tree
  resolved once per request (cached unless `use_cache=False`); global/router deps via
  `dependencies=[...]`. Source:
  [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/),
  [Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).

---

## Q2: SQLAlchemy 2.0 async + asyncpg integration patterns

### Findings
- **Engine.** `create_async_engine("postgresql+asyncpg://user:pw@host:5432/db", ...)`; `+asyncpg` is
  the only async PostgreSQL dialect. `connect_args` pass verbatim to asyncpg (`timeout`,
  `command_timeout`, `server_settings`, `statement_cache_size`). Source:
  [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
- **Session.** `async_sessionmaker(engine, expire_on_commit=False)` (2.0 typed replacement for
  `sessionmaker(class_=AsyncSession)`). `expire_on_commit=False` is **required** in async: default
  post-commit expiry triggers implicit lazy I/O on attribute access → `MissingGreenlet`/
  `greenlet_spawn` error. Create the factory once at startup. Source:
  [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
  [Grinberg ch.7](https://blog.miguelgrinberg.com/post/sqlalchemy-2-in-practice---chapter-7-asynchronous-sqlalchemy).
- **Session-per-request.** Async generator dependency: `async with AsyncSessionLocal() as session:
  yield session` (commit/rollback in the dependency or the endpoint). A new session per request is
  required: identity-map isolation, one transaction per request, and `AsyncSession` "is not safe for
  use in multiple concurrent tasks." Source:
  [Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).
- **Pooling.** `create_async_engine` auto-uses `AsyncAdaptedQueuePool` (never pass
  `poolclass=QueuePool` — "not compatible with asyncio"). Params: `pool_size` (5), `max_overflow`
  (10), `pool_timeout` (30), `pool_recycle` (-1), `pool_pre_ping` (False; set True in prod to drop
  stale conns). `NullPool` for serverless/ephemeral or when an external pooler (pgBouncer) handles
  pooling. Source: [Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html).
- **pgBouncer caveat.** asyncpg caches prepared statements per connection; pgBouncer
  transaction/statement mode breaks this (`prepared statement "__asyncpg_stmt_N__" does not exist`).
  Fixes: `connect_args={"statement_cache_size": 0}`, unnamed prepared statements
  (`prepared_statement_name_func=lambda: ""`), or UUID statement names. pgBouncer 1.21+ adds
  experimental prepared-statement support. Source:
  [asyncpg FAQ](https://magicstack.github.io/asyncpg/current/faq.html),
  [SQLAlchemy disc #10246](https://github.com/sqlalchemy/sqlalchemy/discussions/10246).
- **Declarative base / models.** 2.0 replaces `declarative_base()` with `class Base(DeclarativeBase)`;
  for async add `AsyncAttrs` mixin (`await obj.awaitable_attrs.rel`). `mapped_column()` + `Mapped[T]`
  typed annotations derive SQL type/nullability from hints (`Optional[str]` → NULL). Lazy loading
  must be replaced with eager `selectinload`/`joinedload`. Source:
  [Declarative tables](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html).
- **Transactions.** `async with session.begin():` (commit on exit, rollback on error);
  `async_sessionmaker.begin()` opens+begins; autobegin is on by default so explicit `begin()` is
  optional. `async with engine.begin() as conn:` for DDL/raw SQL (`conn.run_sync(
  Base.metadata.create_all)`). `begin_nested()` = SAVEPOINT. Unit-of-work: changes batched and
  flushed before query/commit. Source:
  [Session transaction](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).

---

## Q3: Alembic configured/operated for async SQLAlchemy/asyncpg

### Findings
- **Async env setup.** Bootstrap with `alembic init -t async migrations` (async template since
  1.5.6; `pyproject_async` variant in 1.16.3). Template `env.py` uses `async_engine_from_config(...,
  poolclass=pool.NullPool)`, `asyncio.run(run_async_migrations())`, and bridges Alembic's *sync*
  migration API via `await connection.run_sync(do_run_migrations)`. `NullPool` because Alembic
  creates/disposes an engine per run. Alembic "does not provide an async API directly." URL must be
  `postgresql+asyncpg://`; commonly set in `env.py` from `os.environ` rather than hardcoded in
  `alembic.ini`. Source:
  [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html),
  [async env.py template](https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py).
- **Programmatic run.** When app already holds a connection (startup script), pass it via
  `cfg.attributes["connection"]` and `command.upgrade(cfg, "head")`; env.py reads
  `config.attributes.get("connection")`. Avoids `asyncio.run` inside a running loop
  (`RuntimeError`, [issue #1606](https://github.com/sqlalchemy/alembic/issues/1606)).
- **Autogenerate detects:** table/column add/remove, nullable changes, basic index/unique/FK
  changes, **column type changes (compare_type defaults True since 1.12.0)**. **Misses:** table &
  column *renames* (rendered as drop+add), anonymously-named constraints, CHECK constraints,
  sequences, server defaults (opt-in `compare_server_default=True`, inaccurate). "autogenerate is
  not intended to be perfect" — always review/edit. Source:
  [Autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).
- **Naming/ordering.** Revisions are partial GUIDs chained via `down_revision`. `file_template`
  controls filenames; timestamp prefix (`%%(year)d_%%(month).2d_..._%%(rev)s_%%(slug)s`) gives
  chronological ordering. Define `MetaData(naming_convention={...})` on the base so constraint names
  are deterministic and autogenerate is reproducible (rendered with `op.f()`). `revision_environment
  = true` loads env.py during `alembic revision`. Source:
  [Naming](https://alembic.sqlalchemy.org/en/latest/naming.html),
  [Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
- **Run/test.** `alembic upgrade head` (idempotent; reads `alembic_version`). Offline `--sql` renders
  DDL without connecting (async template keeps `run_migrations_offline` synchronous). CI: `alembic
  check` (since 1.9.0) fails if models drifted from migrations. Tests: "stairway" upgrade→downgrade→
  upgrade per revision; `pytest-alembic` supports async via an `alembic_engine` AsyncEngine fixture.
  Source: [Offline](https://alembic.sqlalchemy.org/en/latest/offline.html),
  [commands](https://alembic.sqlalchemy.org/en/latest/api/commands.html),
  [alembic-quickstart stairway](https://github.com/alvassin/alembic-quickstart/blob/master/tests/migrations/test_stairway.py).

---

## Q4: `uv` dependency management + reproducible builds + containerization with PostgreSQL

### Findings
- **uv deps.** `uv.lock` is a universal cross-platform TOML lockfile, **committed**, never
  hand-edited; `.venv` is git-ignored. `uv add [--dev | --group X | --optional X]` resolves +
  updates `pyproject.toml` + `uv.lock` atomically. `[dependency-groups]` (PEP 735) are **local-only**
  (excluded from built dists, not installed as package); `[project.optional-dependencies]` (extras)
  are **published** to PyPI for end users. `dev` group included by default in `uv sync`/`uv run`.
  Source: [uv dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/),
  [PEP 735](https://peps.python.org/pep-0735/).
  - *Repo cross-check:* `modernpackage/pyproject.toml:30-40` uses exactly this `[dependency-groups]
    dev = [...]` form.
- **Reproducible/CI.** `uv sync --locked` errors if lockfile stale; `--frozen` skips the check
  (fastest, for Docker/CI); `uv lock --check` verifies without installing. `uv python pin` writes
  `.python-version` (takes precedence over `requires-python`). CI caches the uv cache
  (`astral-sh/setup-uv` `enable-cache: true`, key on `uv.lock` hash) and `uv cache prune --ci`.
  Source: [sync](https://docs.astral.sh/uv/concepts/projects/sync/),
  [GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/).
- **Containerization.** Multi-stage: `COPY --from=ghcr.io/astral-sh/uv:<pin> /uv /uvx /bin/`; layer
  caching via `--mount=type=bind` of `uv.lock`+`pyproject.toml` + `uv sync --locked
  --no-install-project --no-dev`, then `COPY . /app` + `uv sync --locked --no-dev --no-editable`;
  env `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_PYTHON_DOWNLOADS=never`; runtime stage copies
  only `.venv` and sets `ENV PATH="/app/.venv/bin:$PATH"` (no uv at runtime). Source:
  [uv Docker](https://docs.astral.sh/uv/guides/integration/docker/),
  [Hynek](https://hynek.me/articles/docker-uv/).
  - *Repo cross-check:* `docs/containerization.md:66-98` already documents this exact illustrative
    Containerfile (uv pin, bind-mount phases, `UV_*` env, `.venv` on PATH); `docs/containerization.md:308-343`
    documents the App+Postgres compose stack. Align terminology to that doc.
- **Compose stack.** `db` (postgres) with `healthcheck: pg_isready -U user -d db`, named volume
  `pgdata:/var/lib/postgresql/data`; `api` with `depends_on: db: condition: service_healthy`.
  Compose only waits for *running*, not *ready* — health condition bridges the gap. Source:
  [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/). Mirrors
  `docs/containerization.md:294-343`.
- **Migrations in containers.** Recommended: a one-shot `migrate` service (`command: ["alembic",
  "upgrade", "head"]`, `restart: "no"`) gated by `db: service_healthy`, with `api` gated by
  `migrate: condition: service_completed_successfully`. Running migrations at app startup is **unsafe
  with multiple replicas** (concurrent DDL deadlock); the Alembic maintainer recommends migrations
  not be in an auto-scaled component. Alembic acquires a session-scoped advisory lock but it is not
  reliable through transaction-mode poolers; run migrations on a direct (non-pooled) connection.
  Source: [Python Speed](https://pythonspeed.com/articles/schema-migrations-server-startup/),
  [Alembic disc #1438](https://github.com/sqlalchemy/alembic/discussions/1438). Mirrors
  `docs/containerization.md:294-306` (`service_completed_successfully` for one-shot init/migration).

---

## Q5: Testing FastAPI with dependency-injection overrides

### Findings
- **`app.dependency_overrides`.** A dict mapping original callable → override callable; FastAPI
  substitutes the override (and its sub-deps) at call time. Override `get_db` with a test-session
  generator and `get_settings` (override the dependency, not the `@lru_cache` function). Clean up via
  a `yield` fixture: `app.dependency_overrides.clear()` (or `.pop(key, None)`) in teardown; `autouse`
  guarantees cleanup on failure. Source:
  [Testing dependencies](https://fastapi.tiangolo.com/advanced/testing-dependencies/),
  [SQLModel tests](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/).
- **Async clients.** `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`
  is the modern form. **httpx 0.27 deprecated** the `app=` shortcut; **0.28 removed it** → must use
  `transport=ASGITransport(app=app)`. `TestClient` (Starlette) is sync-only — it runs the app in a
  background-thread event loop, so sharing async resources from an `async` test raises "Future
  attached to a different loop." Source:
  [Async tests](https://fastapi.tiangolo.com/advanced/async-tests/),
  [httpx transports](https://www.python-httpx.org/advanced/transports/).
- **Lifespan in tests.** httpx/ASGITransport do **not** fire ASGI lifespan events; wrap with
  `LifespanManager(app)` from `asgi-lifespan` and use `manager.app` so startup resources exist.
  Source: [asgi-lifespan](https://github.com/florimondmanca/asgi-lifespan).
- **Isolated test DBs (4 patterns).** (a) `create_all`/`drop_all` per test (simplest; sometimes
  *faster* than rollback); (b) transactional rollback — open connection, `await conn.begin()`, bind
  `AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)`,
  `rollback()` after test (2.0 no longer needs event-listener savepoint restart); (c) template/
  per-test DB via `pytest-postgresql`; (d) `testcontainers-python` real Postgres (`PostgresContainer
  ("postgres:16", driver="asyncpg")`). Source:
  [SQLAlchemy external transaction](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html),
  [disc #10126](https://github.com/sqlalchemy/sqlalchemy/discussions/10126).
- **Async fixtures.** pytest-asyncio: `asyncio_mode = "auto"`; the `event_loop` fixture was
  **removed in 1.0** — use `loop_scope`. Engine fixture session-scoped (`scope="session",
  loop_scope="session"`); session fixture function-scoped sharing the session loop. Rule: share one
  loop + pool, or separate loops without sharing the pool — `poolclass=NullPool` avoids
  cross-loop reuse errors. FastAPI docs alternatively use `anyio` (`@pytest.mark.anyio` +
  `anyio_backend`). Source:
  [pytest-asyncio changelog](https://pytest-asyncio.readthedocs.io/en/latest/reference/changelog.html),
  [Async tests](https://fastapi.tiangolo.com/advanced/async-tests/).

---

## Q6: Operational health-check endpoints + liveness vs readiness

### Findings
- **Endpoint impl.** Liveness = trivial handler returning 200 (no I/O). Readiness checks deps and
  returns `JSONResponse(status_code=503, ...)` (`status.HTTP_503_SERVICE_UNAVAILABLE`) when a dep is
  down — never 200-with-`"fail"`-body (monitors read the status code). Run checks concurrently with
  `asyncio.gather`. Source:
  [Patryk Golabek](https://patrykgolabek.dev/guides/fastapi-production/health-checks/),
  [K8s probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).
- **DB check.** `async with engine.connect() as conn: await conn.execute(text("SELECT 1"))` (or
  `session.execute`), wrapped in `asyncio.timeout(2.0)` and a broad `except Exception`. The internal
  timeout must be shorter than the probe's `timeoutSeconds`. Source:
  [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
- **Probe semantics.** Liveness fail → **restart**; readiness fail → **remove from Service
  endpoints/LB** (no restart); startup → gates liveness/readiness during slow boot (migrations,
  warmup). **DB checks belong in readiness, not liveness** — a DB outage in a liveness check causes a
  cluster-wide restart loop that doesn't fix the DB. Source:
  [K8s probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/),
  [DEV.to 2026](https://dev.to/young_gao/kubernetes-health-probes-done-right-liveness-readiness-and-startup-5g7g).
- **Conventions/libraries.** Kubernetes API server uses `/livez` + `/readyz` (the `-z` suffix;
  `/healthz` deprecated since v1.16); also `/healthz/live`+`/healthz/ready`, or single `/health`.
  IETF `draft-inadarei-api-health-check-06` defines media type `application/health+json` with
  required `status: "pass"/"fail"/"warn"`. Library: `fastapi-health` (Kludex) —
  `app.add_api_route("/health", health([is_database_online]))`, 503 on any failing condition. Docker
  `HEALTHCHECK` uses a stdlib `http.client`/`urllib` probe (no curl/wget). Source:
  [K8s API health](https://kubernetes.io/docs/reference/using-api/health-checks/),
  [IETF draft-06](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-06),
  [fastapi-health](https://github.com/Kludex/fastapi-health),
  [Docker HEALTHCHECK](https://docs.docker.com/reference/dockerfile/#healthcheck).
  - *Repo cross-check:* `docs/containerization.md:242-256` already documents the stdlib `HEALTHCHECK`
    probe and `/health` returning 200/503 — align readiness terminology with it.

---

## Cross-Cutting Observations
- **Recent shifts to flag in any write-up:** FastAPI lifespan replaced `on_event` (0.93.0);
  `Annotated[..., Depends()]` since 0.95.0; pydantic-settings split out (0.100) + Pydantic v2
  `SettingsConfigDict`; SQLAlchemy 2.0 `DeclarativeBase`/`mapped_column`/`Mapped[]`/
  `async_sessionmaker` over 1.x equivalents; Alembic `compare_type` default True (1.12.0) and
  `alembic check` (1.9.0); httpx removed `app=` (0.28); pytest-asyncio removed `event_loop` fixture
  (1.0); PEP 735 `[dependency-groups]` vs published extras.
- **Recurring `+asyncpg` thread:** the `postgresql+asyncpg://` URL, `expire_on_commit=False`,
  no-lazy-load (eager loaders), NullPool for short-lived processes, and pgBouncer statement-cache
  caveats reappear across Q2/Q3/Q5/Q6.
- **Terminology already in-repo:** `docs/containerization.md` covers multi-stage uv builds,
  compose App+Postgres stacks, `service_completed_successfully` migration gating, and `/health`
  503 HEALTHCHECK — Q4 and Q6 write-ups should reference/extend it rather than restate it.

## Open Areas
- The repo has **no** FastAPI/SQLAlchemy/Alembic/test code to ground these answers; all findings are
  external best practices, not observed repo patterns. The only in-repo grounding is
  `docs/containerization.md` (container/compose/migration terminology) and `pyproject.toml`
  (`uv` + `[dependency-groups]` usage).
- `docs/architecture.md` documents the scaffolder package, not a service backend; it offers no
  FastAPI-specific patterns to align with.
- Authoritative-source coverage is strong for official docs; some operational specifics (exact CI
  cache keys, probe thresholds, multi-replica migration locking) rest partly on widely-cited
  community references rather than first-party docs.
