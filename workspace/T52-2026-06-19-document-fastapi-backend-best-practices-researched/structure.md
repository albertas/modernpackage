# Structure Outline

## Approach

Write one new reference page, `docs/fastapi_backend.md`, in the fixed docs
house-style (H1 `# modernpackage — FastAPI Backend`, `[overview.md](overview.md)`
backlink on line 3, forward-looking "ships no backend code today" note), with six
sections mapped 1:1 to the six research questions. Cross-reference
`docs/containerization.md` for container/compose/migration/health mechanics instead
of restating them. Every technical claim traces to a `research.md` finding;
version-sensitive claims are pinned to the release that introduced them.

**Note on slicing:** this task has no database/service/API/UI layers to cross. The
honest vertical unit here is a *complete doc section* — prose + load-bearing snippet
+ external and `file:line` citations — that a reader can consume end-to-end and that
an agent can verify by grepping for the required idioms, cites, and cross-refs. The
skeleton phase ships first so that if any later section is dropped, the page still
exists, is house-style-correct, and is reachable from the docs index.

---

## Phase 1: Page skeleton + index registration

Create `docs/fastapi_backend.md` with the H1, backlink, forward-looking paragraph,
and the six empty `##` section headers; add the page to the `docs/overview.md`
"Documentation Files" table. After this phase the page exists, is house-style-valid,
and is navigable from the index.

**Files**: `docs/fastapi_backend.md` (new), `docs/overview.md`
**Key changes**:
- H1 line 1: `# modernpackage — FastAPI Backend`
- Line 3: `[overview.md](overview.md)`
- Forward-looking note mirroring `docs/containerization.md:1-9` ("ships no backend
  code today … illustrative templates, not committed files")
- Six headers: `## Application Structure & DI`, `## SQLAlchemy 2.0 Async + asyncpg`,
  `## Alembic (Async Migrations)`, `## Dependencies & Containerization (uv)`,
  `## Testing with DI Overrides`, `## Health Checks`
- New row in table at `docs/overview.md:19-29`:
  `| [fastapi_backend.md](fastapi_backend.md) | **FastAPI backend**: … |`

**Verify**: `test -f docs/fastapi_backend.md`; `head -3 docs/fastapi_backend.md`
shows the H1 on line 1 and the backlink on line 3; `grep -c '^## ' docs/fastapi_backend.md`
returns `6`; `grep -q 'fastapi_backend.md' docs/overview.md`.

---

## Phase 2: Application Structure & DI section

Document layout (module-by-feature vs module-by-type), `APIRouter` assembly,
`pydantic-settings` with `@lru_cache`, the `lifespan` context manager on `app.state`,
and `Annotated[..., Depends()]` DI. Flag deprecated `on_event`/legacy `Depends`/inner
`class Config`.

**Files**: `docs/fastapi_backend.md`
**Key changes** (idioms the section must show):
- `@asynccontextmanager async def lifespan(app)` with create-before-`yield`,
  `await engine.dispose()` after-`yield`
- `DbSessionDep = Annotated[AsyncSession, Depends(get_db)]`
- `model_config = SettingsConfigDict(env_file=".env")` + `@lru_cache`
- Explicit "avoid" callouts: `@app.on_event(...)` (deprecated 0.93.0),
  `param: T = Depends(fn)`, inner `class Config`

**Verify**: `grep -q 'lifespan' docs/fastapi_backend.md`;
`grep -q 'Annotated' docs/fastapi_backend.md`;
`grep -q 'on_event' docs/fastapi_backend.md` (present as a flagged anti-pattern);
section contains `0.93.0` and `0.95.0` release pins;
`grep -c 'fastapi.tiangolo.com' docs/fastapi_backend.md` ≥ 1.

---

## Phase 3: SQLAlchemy 2.0 Async + asyncpg section

Document `create_async_engine("postgresql+asyncpg://…")`,
`async_sessionmaker(expire_on_commit=False)`, the `get_db` async-generator dependency,
`AsyncAdaptedQueuePool` (never `poolclass=QueuePool`), `NullPool` for short-lived
processes, the pgBouncer `statement_cache_size=0` caveat, and `DeclarativeBase` /
`mapped_column` / `Mapped[]`. Establishes the `+asyncpg` cross-cutting thread that
Phases 4–7 back-reference.

**Files**: `docs/fastapi_backend.md`
**Key changes** (idioms the section must show):
- `create_async_engine("postgresql+asyncpg://...")`
- `async_sessionmaker(engine, expire_on_commit=False)` with the `MissingGreenlet`
  rationale
- `async def get_db() -> AsyncIterator[AsyncSession]: async with ... yield session`
- `class Base(DeclarativeBase)` + `mapped_column()` / `Mapped[T]`
- Flagged: `sessionmaker(class_=AsyncSession)`, `declarative_base()`,
  `poolclass=QueuePool`, default `expire_on_commit=True`

**Verify**: `grep -q 'postgresql+asyncpg' docs/fastapi_backend.md`;
`grep -q 'expire_on_commit=False' docs/fastapi_backend.md`;
`grep -q 'DeclarativeBase' docs/fastapi_backend.md`;
`grep -q 'statement_cache_size' docs/fastapi_backend.md`;
`grep -c 'docs.sqlalchemy.org' docs/fastapi_backend.md` ≥ 1.

---

## Phase 4: Alembic (Async Migrations) section

Document the async `env.py` bridge (`async_engine_from_config(..., poolclass=NullPool)`,
`await connection.run_sync(do_run_migrations)`), URL from `os.environ`, autogenerate
caveats (`compare_type` default True since 1.12.0; misses renames/CHECK/server-defaults),
the `migrate` commands, and a note that they should become `just migrate` /
`just makemigration` / `just migration-check` recipes (deferred to scaffolder).

**Files**: `docs/fastapi_backend.md`
**Key changes** (idioms the section must show):
- `await connection.run_sync(do_run_migrations)` async bridge
- `async_engine_from_config(..., poolclass=pool.NullPool)`
- Commands: `alembic upgrade head`, `alembic check`, autogenerate
- Back-reference to the `+asyncpg` URL thread (Phase 3)

**Verify**: `grep -q 'run_sync' docs/fastapi_backend.md`;
`grep -q 'alembic check' docs/fastapi_backend.md`;
`grep -q 'NullPool' docs/fastapi_backend.md`;
section contains release pins `1.12.0` and `1.9.0`;
`grep -c 'alembic.sqlalchemy.org' docs/fastapi_backend.md` ≥ 1.

---

## Phase 5: Dependencies & Containerization (uv) section

Document `uv.lock` (committed) vs `.venv` (ignored), `uv add`, PEP 735
`[dependency-groups]` vs published extras, `uv sync --locked`/`--frozen`, and
**cross-reference** `docs/containerization.md` for the multi-stage build, App+Postgres
compose stack, and `service_completed_successfully` migration gating rather than
restating them. Add the backend-only layer: multi-replica migration safety (one-shot
`migrate` service; not at app startup; direct non-pooled connection).

**Files**: `docs/fastapi_backend.md`
**Key changes**:
- `pyproject.toml:30-40` `file:line` cite for the `[dependency-groups] dev` form
- Cross-ref links to `docs/containerization.md` (build / compose / migration sections)
- Multi-replica migration-safety note (one-shot `migrate`, advisory-lock caveat)

**Verify**: `grep -q 'containerization.md' docs/fastapi_backend.md` (cross-ref present);
`grep -q 'dependency-groups' docs/fastapi_backend.md`;
`grep -q 'pyproject.toml:' docs/fastapi_backend.md` (`file:line` cite);
`grep -q 'uv.lock' docs/fastapi_backend.md`;
`grep -q 'service_completed_successfully' docs/fastapi_backend.md`.

---

## Phase 6: Testing with DI Overrides section

Document `app.dependency_overrides`, the modern
`httpx.AsyncClient(transport=ASGITransport(app=app))` (flag removed `app=` shortcut in
0.28), `LifespanManager` for lifespan in tests, the four isolated-test-DB patterns, and
pytest-asyncio `loop_scope` (flag removed `event_loop` fixture in 1.0).

**Files**: `docs/fastapi_backend.md`
**Key changes** (idioms the section must show):
- `app.dependency_overrides[get_db] = ...` + `clear()` teardown
- `ASGITransport(app=app)`; flagged: httpx `app=` shortcut, Starlette `TestClient`
  for async
- `loop_scope`; flagged: removed `event_loop` fixture
- Back-reference to `expire_on_commit=False` / `NullPool` thread (Phase 3)

**Verify**: `grep -q 'dependency_overrides' docs/fastapi_backend.md`;
`grep -q 'ASGITransport' docs/fastapi_backend.md`;
`grep -q 'loop_scope' docs/fastapi_backend.md`;
section contains release pins `0.28` and `1.0`.

---

## Phase 7: Health Checks section

Lead with readiness-vs-liveness semantics and the "DB check belongs in readiness, not
liveness" rule, then the concrete `SELECT 1` + `asyncio.timeout` impl returning 503,
then a cross-reference to the existing `docs/containerization.md` stdlib `HEALTHCHECK`
probe. Note `/livez` + `/readyz` conventions and the IETF `application/health+json`
media type.

**Files**: `docs/fastapi_backend.md`
**Key changes** (idioms the section must show):
- Readiness `await conn.execute(text("SELECT 1"))` inside `asyncio.timeout(2.0)`,
  returning `status.HTTP_503_SERVICE_UNAVAILABLE`
- Explicit "DB check in readiness, not liveness" rule with restart-loop rationale
- Cross-ref to `docs/containerization.md` `HEALTHCHECK` / `/health`

**Verify**: `grep -q 'SELECT 1' docs/fastapi_backend.md`;
`grep -q 'readiness' docs/fastapi_backend.md` and `grep -q 'liveness' docs/fastapi_backend.md`;
`grep -q '503' docs/fastapi_backend.md`;
`grep -q 'containerization.md' docs/fastapi_backend.md` (HEALTHCHECK cross-ref).

---

## Testing Checkpoints

After each phase the following should hold (useful for resuming if context resets):

- **P1**: `docs/fastapi_backend.md` exists; H1 on line 1, backlink on line 3, six `##`
  headers; row added to `docs/overview.md` table.
- **P2**: Structure/DI section shows `lifespan` + `Annotated[..., Depends()]`; flags
  `on_event`; pins 0.93.0 / 0.95.0.
- **P3**: SQLAlchemy section shows `postgresql+asyncpg`, `expire_on_commit=False`,
  `DeclarativeBase`, pgBouncer caveat; `+asyncpg` thread established.
- **P4**: Alembic section shows `run_sync` bridge, `NullPool`, `alembic check`; pins
  1.12.0 / 1.9.0; Justfile-target note present.
- **P5**: uv section cross-refs `containerization.md`, cites `pyproject.toml:30-40`,
  covers `dependency-groups` and multi-replica migration safety.
- **P6**: Testing section shows `dependency_overrides`, `ASGITransport`, `loop_scope`;
  flags httpx `app=` (0.28) and `event_loop` (1.0).
- **P7**: Health section leads with readiness-vs-liveness, shows `SELECT 1` + 503,
  cross-refs `containerization.md` HEALTHCHECK.
- **Final (all phases)**: every section non-empty; `grep -c '://' docs/fastapi_backend.md`
  confirms external citations present; no `Containerfile`/`compose.yml`/backend code
  files added (`git status --porcelain` shows only the two doc files changed).
