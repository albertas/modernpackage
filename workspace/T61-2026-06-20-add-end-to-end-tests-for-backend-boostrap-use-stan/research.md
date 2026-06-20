# Research Findings

## Q1: How are end-to-end tests located, marked, discovered? What changes if they lived in a separate top-level dir?

### Findings
- **Marker definition**: `e2e` marker registered in `pyproject.toml:35-36` — `"e2e: tests that perform real external calls (network/subprocess/fs)"`.
- **Default exclusion**: `pyproject.toml:30` `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`. The default run *excludes* e2e tests and enforces 95% coverage on `modernpackage`.
- **norecursedirs**: `pyproject.toml:31` `norecursedirs = ["backend_template", "frontend_template"]` — pytest does not collect tests inside the template dirs.
- **Test file location**: e2e tests live in `tests/test_e2e.py`; each test is decorated `@pytest.mark.e2e` (`tests/test_e2e.py:122,189,248,325,424`).
- **Justfile recipes**:
  - `Justfile:14-15` `test *args: sync` → `uv run pytest -n "$(nproc --ignore=1)" {{args}}` (regular run; inherits `addopts`, so e2e excluded).
  - `Justfile:17-18` `test-e2e *args: sync` → `uv run pytest -m e2e --no-cov {{args}}` (selects only e2e, disables coverage).
- **`-m e2e` overrides** the `-m 'not e2e'` in `addopts` (last `-m` wins in pytest); `--no-cov` disables the coverage gate so external-call tests aren't penalized for low `modernpackage` coverage.
- **`check` chain**: `Justfile:53` runs `... test audit` — i.e. the *regular* `test` (e2e excluded). e2e is never part of `just check`.
- **If e2e tests moved to a separate top-level dir** (e.g. `tests_e2e/`): pytest discovers any dir not in `norecursedirs`, so a new top-level dir would be auto-collected by the default `test` run too — and since the default `addopts` carries `-m 'not e2e'`, marker filtering (not directory) is what keeps them out. `--cov=modernpackage` is package-scoped, not path-scoped, so coverage targeting is unaffected by test location. The `test-e2e` recipe selects purely by marker (`-m e2e`), so it would still find them wherever they live. Moving them would not require config changes *as long as* they keep the `@pytest.mark.e2e` marker; only if the marker were dropped would a path-based selector be needed.

## Q2: How does an existing e2e test scaffold a backend-only app and bring it up against a real database?

### Findings
- **Backend-only check test**: `test_scaffolded_backend_package_passes_check` (`tests/test_e2e.py:189-245`) scaffolds but does NOT bring up a DB; it only runs `just check`.
- **The real-stack test is fullstack**: `test_fullstack_package_runs_end_to_end` (`tests/test_e2e.py:424-550`) is the only test that brings the stack up against a real database. There is no backend-only "runs end-to-end" test currently.
- **Scaffold flow** (both tests):
  1. `git clone REPO_ROOT → destination` (`test_e2e.py:199` / `451`) — clones committed local checkout.
  2. `main._write_package_metadata(...)` (`main.py:446`) writes author/license/etc.
  3. `main._strip_scaffolding(destination)` (`main.py:643`) removes scaffolder CLI/tests/docs.
  4. Backend injection:
     - backend-only test calls `main._add_backend(destination)` (`main.py:995`) then manual `git add -A` (`test_e2e.py:211-212`).
     - fullstack test calls `main._inject_templates(destination, fullstack=True)` (`main.py:982`), which calls `_add_backend` + `_add_frontend` + `_stage_injected_files` (internal `git add -A`).
  5. `just init module_name` (`test_e2e.py:215-220` / `465-470`) renames the `modernpackage` token everywhere and makes the initial commit.
- **`_add_backend`** (`main.py:995-1007`): `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)`, then `_append_backend_dependencies` and `_append_backend_recipes`. `_BACKEND_TEMPLATE_DIR` resolves to repo `backend_template/` (`main.py` ~556). `compose.yml`, `Containerfile`, `.dockerignore`, `alembic.ini`, `migrations/` land at package root (`destination`), since copytree targets `package_path`.
- **Bringing the stack up** (`test_e2e.py:475-477`): inside `try/finally`, `_run([*compose, 'up', '-d', '--wait', '--build'], cwd=destination)`. `compose` is the detected command (Q7). `--wait` blocks until healthchecks pass.
- **compose.yml services** (`backend_template/compose.yml`):
  - `db` (`:23-36`): `postgres:17`, env `appuser/secret/appdb`, healthcheck `pg_isready -U appuser -d appdb` (interval 10s, timeout 5s, retries 5, start_period 30s), volume `pgdata`.
  - `migrate` (`:15-22`): `build: .`, `command: ["alembic", "upgrade", "head"]`, `DATABASE_URL=postgresql+asyncpg://appuser:secret@db:5432/appdb`, `depends_on: db (service_healthy)`.
  - `app` (`:4-14`): `build: .`, port `127.0.0.1:8000:8000`, same `DATABASE_URL`, `depends_on: db (service_healthy)` AND `migrate (service_completed_successfully)`.
- **Readiness awaited via** `--wait`, which waits for the app's `HEALTHCHECK` (`Containerfile:24-25`, hits `/readyz`). Because `app` depends on `migrate` completing and `db` healthy, `--wait` returning success proves DB up + migrations applied + app ready.

## Q3: How is health/readiness implemented and exercised? How does it verify DB connectivity?

### Findings
- **Probes** in `backend_template/modernpackage/health.py`:
  - `livez` (`:31-34`): returns `{'status':'pass'}`, never touches DB.
  - `readyz` (`:37-46`): depends on `database_ready`; returns 200 `{'status':'pass'}` or sets 503 `{'status':'fail'}`.
  - `database_ready` (`:19-28`): reads `engine = request.app.state.engine`, runs `SELECT 1` inside `asyncio.timeout(2.0)` (`_READINESS_TIMEOUT_SECONDS`, `:16`); any exception → `False` (`except Exception` with `# noqa: BLE001`).
- **Engine/session wiring**:
  - `app.py:18-27` lifespan creates `engine = create_engine()` on startup, stores `app.state.engine` and `app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)`; disposes engine on shutdown.
  - `db.py:46-48` `create_engine()` → `create_async_engine(database_url())`; lazy, opens no connection until first use.
  - `db.py:41-43` `database_url()` → env `DATABASE_URL` or `_DEFAULT_DATABASE_URL` (`postgresql+asyncpg://appuser:secret@db:5432/appdb`, `:23`).
  - `db.py:51-57` `get_db` yields one `AsyncSession` per request from `app.state.sessionmaker`; `DbSessionDep` alias `:60`.
  - `create_app()` (`app.py:30-34`) builds FastAPI with lifespan and `include_router(health_router)`.
- **Host-side HTTP assertions** (`test_e2e.py:481-486`): after `compose up --wait`, `_http_get('http://127.0.0.1:8000/livez')` asserts 200 + `'pass'` in body; `_http_get('.../readyz')` asserts 200.
- **In-process unit tests** (`backend_template/tests/test_app.py`): `TestClient` + `dependency_overrides[database_ready]` for pass/fail (`:53-68`); `_FakeEngine/_FakeConnection` drive `database_ready` true/false (`:18-43,71-76`); `test_get_db_yields_session` (`:79-99`).

## Q4: How is Alembic configured? How does autogeneration discover the schema? What DATABASE_URL at migration time?

### Findings
- **`backend_template/migrations/env.py`** (async-only, no offline branch):
  - `target_metadata = Base.metadata` (`:12`), importing `Base` from `modernpackage.db` (`:7`).
  - `run_async_migrations` (`:25-33`): reads config section, sets `config_section['sqlalchemy.url'] = os.environ['DATABASE_URL']` (`:29`) — **fails hard (KeyError) if `DATABASE_URL` unset**; builds `async_engine_from_config(..., poolclass=pool.NullPool)`.
  - `do_run_migrations` (`:15-22`): `context.configure(connection=..., target_metadata=target_metadata, compare_type=True)`. `compare_type=True` enables type-change detection in autogenerate.
  - Module runs `asyncio.run(run_async_migrations())` at import (`:36`).
- **alembic.ini** (`backend_template/alembic.ini`): `script_location = migrations` (`:4`), `prepend_sys_path = .` (`:5`), `path_separator = os` (`:6`). URL intentionally NOT set here — injected from `$DATABASE_URL` in env.py (`:1-2` comment).
- **DATABASE_URL at migration time**: provided by the `migrate` compose service env (`compose.yml:18-19`) = `postgresql+asyncpg://appuser:secret@db:5432/appdb`.
- **Declarative Base / metadata** (`db.py:35-38`): `class Base(AsyncAttrs, DeclarativeBase)` with `metadata = MetaData(naming_convention=_NAMING_CONVENTION)`.
- **Naming convention** (`db.py:26-32`): `ix_%(column_0_name)s`, `uq_%(table_name)s_%(column_0_name)s`, `ck_%(table_name)s_%(constraint_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, `pk_%(table_name)s` — deterministic constraint names so autogenerate is reproducible.
- **Migration template** `migrations/script.py.mako`: standard `upgrade()/downgrade()` skeleton with typed `revision`/`down_revision` vars.

## Q5: What Justfile targets does the generated backend package expose for migrations? Where defined, exact commands?

### Findings
- Defined in `main.py:579-588` as `_BACKEND_RECIPES`, appended to the generated package's Justfile by `_append_backend_recipes` (`main.py:912-925`, called from `_add_backend` `main.py:1007`):
  - `migrate: sync` → `uv run alembic upgrade head` (`main.py:580-581`)
  - `makemigration message: sync` → `uv run alembic revision --autogenerate -m "{{message}}"` (`main.py:583-584`)
  - `migration-check: sync` → `uv run alembic check` (`main.py:586-587`)
- All depend on `sync` (`uv sync`). These are NOT added to the `check` chain — comment `main.py:576-578` notes they need a live database.
- e2e assertions confirm presence: `test_e2e.py:234-235` asserts `'migrate: sync'` and `'makemigration'` in the generated Justfile.

## Q6: How are tables/models defined and registered with shared metadata? Existing examples?

### Findings
- **Shared metadata** is `Base.metadata` (`db.py:35-38`); any model subclassing `Base` registers automatically. `env.py:12` points `target_metadata` at it for autogenerate.
- **No example table/model exists.** `grep` for `Mapped|mapped_column|__tablename__|Table(` across `backend_template/` returns nothing. The only files in `backend_template/modernpackage/` are `app.py`, `db.py`, `health.py`.
- **No migration versions exist**: `backend_template/migrations/versions/` contains only `.gitkeep` (empty).
- A new table would follow the SQLAlchemy 2.0 declarative pattern: subclass `Base`, define `__tablename__` and `Mapped[...]`/`mapped_column(...)` columns. The convention infrastructure (naming convention, `AsyncAttrs`, deterministic metadata) is in place but unused by any concrete model.

## Q7: What patterns do existing e2e tests use for skip guards, compose detection, HTTP probing, teardown?

### Findings
- **Required-tool skip guard**: `REQUIRED_TOOLS = ('git','just','uv')` (`test_e2e.py:31`); loop `shutil.which(tool) is None → pytest.skip(...)` (`test_e2e.py:124-126,191-193,251-252,340-342,440-442`). Runtime test adds `npm`: `_REQUIRED_RUNTIME_TOOLS = (*REQUIRED_TOOLS, 'npm')` (`:35`).
- **Compose detection**: `_detect_compose_command()` (`test_e2e.py:67-88`) probes `_COMPOSE_CANDIDATES` (`:60-64`): `('docker','compose')`, `('podman','compose')`, `('podman-compose',)`. Runs `<cmd> version` with `check=False`, returns first with `returncode == 0`; `FileNotFoundError` → continue; all fail → `None`. Caller skips: `if compose is None: pytest.skip(...)` (`:443-445`).
- **HTTP probing**: `_http_get(url, timeout=30.0)` (`test_e2e.py:91-104`) uses stdlib `urllib.request.urlopen` (avoids httpx dependency), returns `(status, body)`; `HTTPError` returns `(code, body)` so callers assert on 4xx/5xx; only connection-level errors propagate.
- **Subprocess helper**: `_run(command, cwd, env)` (`test_e2e.py:45-57`) — `subprocess.run(..., check=False, capture_output=True, text=True)`. Git identity injected via `_GIT_IDENTITY_ENV` (`:37-42`) merged as `os.environ | _GIT_IDENTITY_ENV`.
- **Stack teardown**: `try/finally` around `compose up` (`test_e2e.py:475-550`); `finally: _run([*compose, 'down', '-v'], cwd=destination)` (`:549-550`) — always tears down with volume removal.
- **Graceful sub-skip**: Playwright browser-install failure treated as skip, not fail (`test_e2e.py:538-545`).

## Cross-Cutting Observations
- **Two injection paths**: backend-only test stages manually (`_add_backend` + explicit `git add -A`, `test_e2e.py:211-212`); fullstack uses `_inject_templates(..., fullstack=True)` which stages internally (`main.py:982-992`). A backend-only "runs end-to-end" test would parallel the fullstack runtime test but use `_add_backend` + manual `git add -A` (no frontend).
- **Token rename**: every template file keeps the literal `modernpackage` token so `just init`'s rename sed rewrites it; tests assert no `modernpackage` remains in injected sources (`test_e2e.py:226-227`).
- **Layout after injection**: backend files (`compose.yml`, `Containerfile`, `.dockerignore`, `alembic.ini`, `migrations/`) land at package root `destination`; Python modules merge into `destination/module_name/`. compose `build: .` context is `destination`.
- **Readiness contract chain**: `compose up --wait` → app `HEALTHCHECK /readyz` → `database_ready` `SELECT 1` → proves db + migrate + app. Same `/readyz` endpoint is asserted host-side over HTTP.
- **e2e isolation by marker, not path**: coverage gate (`--cov-fail-under=95`) and `-m 'not e2e'` keep e2e out of the default run; `test-e2e` uses `--no-cov` + `-m e2e`.

## Open Areas
- **No backend-only "runs end-to-end" test exists today** — only the fullstack runtime test (`test_fullstack_package_runs_end_to_end`) brings up the real DB stack. Q2 was answered using that fullstack test as the closest existing example.
- **No concrete model/table or migration version exists** in `backend_template/` (Q6); only the unused metadata/Base infrastructure is present.
- env.py is async-only with no offline migration branch and hard-requires `DATABASE_URL` (`env.py:29`); behavior when unset is an uncaught `KeyError`.
