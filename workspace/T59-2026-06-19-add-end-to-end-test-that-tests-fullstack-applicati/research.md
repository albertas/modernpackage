# Research Findings

## Q1: How is the e2e test suite structured — marking, selection/exclusion, invocation, setup/skip guards?

### Findings
- **Marker registration:** `e2e` is declared in `pyproject.toml:42-44` as a custom marker
  ("tests that perform real external calls (network/subprocess/fs)").
- **Default exclusion:** `pyproject.toml:40` sets `addopts = "... -m 'not e2e'"`, so a plain
  `pytest` run (and `just test`/`just check`) excludes all `@pytest.mark.e2e` tests. Coverage
  gates `--cov-fail-under=95.0 --no-cov-on-fail` are also in this line.
- **Explicit selection:** `just test-e2e` (`Justfile:17-18`) runs `uv run pytest -m e2e --no-cov`
  — selects only e2e tests and disables coverage. Not part of `just check` (`Justfile:53`, which
  runs `check-format check-lint check-complexity check-typecheck test audit`).
- **Recursion exclusion:** `pyproject.toml:41` `norecursedirs = ["backend_template", "frontend_template"]`
  keeps the template trees out of collection.
- **All four e2e tests live in `tests/test_e2e.py`**, each decorated `@pytest.mark.e2e`
  (`test_e2e.py:69, 136, 195, 272`).
- **Required-tool skip guard:** `REQUIRED_TOOLS = ('git', 'just', 'uv')` (`test_e2e.py:29`); every
  test loops and calls `pytest.skip(...)` when `shutil.which(tool) is None`
  (`test_e2e.py:71-73, 138-140, 197-199, 287-289`). The fullstack test extends the tuple with
  `'npm'` (`test_e2e.py:286`) so Node-less environments skip rather than fail.
- **Git identity for commits:** `_GIT_IDENTITY_ENV` (`test_e2e.py:31-36`) is merged into `os.environ`
  for `just init` (which commits) at `test_e2e.py:96-97, 164-165, 313-315`.
- **Shared helper:** `_run()` (`test_e2e.py:39-51`) wraps `subprocess.run(..., check=False,
  capture_output=True, text=True)`.
- **Caveats documented in module docstring** (`test_e2e.py:1-15`): tests clone the *local committed*
  checkout (not the GitHub URL), `git clone` copies committed state only, and the inner `just check`
  runs `uv sync` + networked `pip-audit`, so it needs network and takes minutes.

## Q2: What does the fullstack e2e test exercise step by step; what is covered vs. left unexercised?

### Findings
`test_scaffolded_fullstack_package_passes_check` (`test_e2e.py:272-369`):
1. Skip guard for `git, just, uv, npm` (`test_e2e.py:286-289`).
2. `git clone <REPO_ROOT>` into `tmp_path/module_name` (`test_e2e.py:295-296`).
3. `main._write_package_metadata(...)` with author/email/description/license/repo
   (`test_e2e.py:298-305`).
4. `main._strip_scaffolding(destination)` (`test_e2e.py:306`).
5. **Production fullstack injection:** `main._inject_templates(destination, fullstack=True)`
   (`test_e2e.py:309`) — runs `_add_backend` + `_add_frontend` + internal `git add -A`
   (`main.py:979-989`). Unlike the backend test (`test_e2e.py:158-160`) it does **not** stage manually.
6. `just init <module_name>` with git identity env (`test_e2e.py:311-316`).
7. `just check` — backend pytest/lint/typecheck/audit (`test_e2e.py:318-319`).
8. `just frontend-install` (= `npm ci`) (`test_e2e.py:324-327`).
9. `just frontend-test` (= `npm run test` → `vitest run`) (`test_e2e.py:331-334`).

**Assertions covered:**
- Backend sources present: `app.py`, `health.py` (`test_e2e.py:343-345`).
- Frontend injected at `frontend/` (`test_e2e.py:348-349`).
- Rename sed reached staged frontend files: no `modernpackage` token in `package.json` /
  `App.test.tsx` (`test_e2e.py:352-355`).
- Frontend recipes injected into Justfile: `frontend-install`, `frontend-test`, `frontend-check`
  (`test_e2e.py:358-361`).
- Frontend recipes excluded from `check:` chain line (`test_e2e.py:364-368`).
- Vitest actually ran: asserts `'Test Files'` appears in combined output (`test_e2e.py:336-340`).

**Left unexercised (per comments/observed):**
- `frontend-check` is NOT run (only `frontend-test`); format/lint/typecheck out of scope
  (`test_e2e.py:329-330`).
- `frontend-build`, `generate-client` recipes (`main.py:599-609`) are not invoked.
- No backend container/compose run (no `compose.yml`/`Containerfile` assertions here, unlike the
  backend-only test `test_e2e.py:186-192`).
- No runtime backend↔frontend connectivity test; the Vitest suite renders `<App/>` only
  (`App.test.tsx:5-9`), no real HTTP. The generated API client is a placeholder
  (`frontend_template/src/client/index.ts:1-4`).
- `main._add_frontend` is exercised only via `_inject_templates`; the `just frontend-build` and dev
  server paths are not tested.

## Q3: How does `--fullstack`/`--reactjs` flow from CLI parsing to template injection?

### Findings
- **Argument parsing:** `--fullstack`/`--reactjs` is a `store_true` flag (`main.py:370-376`);
  `--backend`/`--fastapi` is a separate `store_true` flag (`main.py:363-369`).
- **main() dispatch:** `parsed_args.fullstack` is passed to `init_new_package(...)`
  (`main.py:1128-1129`).
- **Full sequence in `init_new_package`** (`main.py:1007-1108`):
  1. `_run_preflight_checks` (`main.py:1023`).
  2. dry-run branch returns early if set (`main.py:1025-1037`).
  3. `git clone _TEMPLATE_REPOSITORY_URL` via `Popen` (`main.py:1039-1052`).
  4. `_write_package_metadata` (`main.py:1054-1061`).
  5. `_strip_scaffolding` (`main.py:1063`).
  6. **Injection guard:** `if backend or fullstack: _inject_templates(new_package_path,
     fullstack=fullstack)` (`main.py:1065-1066`).
  7. `just init <module_name>` (`main.py:1068-1087`).
  8. `just check` (`main.py:1089-1108`).
- **`_inject_templates`** (`main.py:979-989`): always `_add_backend`; if `fullstack` also
  `_add_frontend`; then `_stage_injected_files` (`git add -A`).
- **`_add_backend`** (`main.py:992-1005`): `copytree(_BACKEND_TEMPLATE_DIR, package_path,
  dirs_exist_ok=True)` → `_append_backend_dependencies` → `_append_backend_recipes`.
- **`_add_frontend`** (`main.py:962-976`): `copytree(_FRONTEND_TEMPLATE_DIR, package_path/'frontend',
  dirs_exist_ok=True)` → `_append_frontend_recipes`. Adds no Python deps, spawns no child processes.
- **Staging:** `_stage_injected_files` runs `git add -A` (`main.py:925-943`); needed because the
  rename sed in `just init` only rewrites tracked files (`Justfile:62-67`).
- **Template dirs resolved relative to `main.py`** so they work from source or installed wheel
  (`main.py:552-561`); shipped via `[tool.hatch.build] include` (`pyproject.toml:51`).
- **`backend_template`/`frontend_template` always stripped** from the clone first
  (`main.py:519-526`), then re-injected only when flags are set.

## Q4: What does the generated fullstack package contain and how is it run?

### Findings
- **Generated Justfile** = base template recipes (`Justfile:1-81`) + appended backend recipes
  (`_BACKEND_RECIPES`, `main.py:579-588`) + appended frontend recipes (`_FRONTEND_RECIPES`,
  `main.py:595-614`).
- **Backend recipes** (`main.py:579-588`): `migrate: sync` (`alembic upgrade head`),
  `makemigration message: sync` (`alembic revision --autogenerate`), `migration-check: sync`
  (`alembic check`). Depend on `sync` (= `uv sync`), NOT added to `check` chain (need live DB).
- **Frontend recipes** (`main.py:595-614`): `frontend-install` (`cd frontend && npm ci`),
  `frontend-build` (`npm run build`), `frontend-test` (`npm run test`), `frontend-lint`
  (`npm run lint`), `generate-client` (`npm run generate-client`), `frontend-check:
  frontend-install` (runs format:check + lint + typecheck + test). No `: sync` dep; scoped via
  `cd frontend`.
- **`frontend-test` does NOT depend on `frontend-install`** — install must run first (noted in
  `test_e2e.py:322-323`).
- **`check` chain** (`Justfile:53`) covers only Python gates; frontend recipes intentionally excluded.
- **Backend run path:** `compose.yml` (`backend_template/compose.yml`) three services — `app`
  (uvicorn factory), `migrate` (`alembic upgrade head`), `db` (`postgres:17`). `app` waits on
  `db: service_healthy` and `migrate: service_completed_successfully`; `migrate` waits on
  `db: service_healthy`.
- **Container CMD:** `uvicorn modernpackage.app:create_app --factory --host 0.0.0.0 --port 8000`
  (`backend_template/Containerfile:26`); `--factory` invokes `create_app()` (`app.py:30`).
- **Frontend run path:** Vite dev server (`npm run dev` → `vite`) with `/api` proxied to
  `http://localhost:8000` (`vite.config.ts:5-11`); build via `npm run build` (`tsc --noEmit &&
  vite build`).
- **Backend dependencies appended** (`main.py:565-574`): fastapi, sqlalchemy[asyncio], asyncpg,
  alembic, uvicorn (runtime); httpx (dev, for TestClient).

## Q5: How do the backend application, health, and database modules work; how is DB integration exercised?

### Findings
- **App factory:** `create_app()` (`backend_template/modernpackage/app.py:30-34`) builds `FastAPI`
  with `lifespan` and includes the health router. **Lifespan** (`app.py:18-27`): on startup creates
  engine via `create_engine()`, stores `app.state.engine` and an `async_sessionmaker`
  (`expire_on_commit=False`) on `app.state.sessionmaker`; on shutdown `await engine.dispose()`.
- **Health** (`backend_template/modernpackage/health.py`): `router = APIRouter()` (line 14).
  `GET /livez` always returns `{'status':'pass'}` (lines 31-34). `GET /readyz` (lines 37-46) depends
  on `database_ready` (lines 19-28), which runs `SELECT 1` inside `asyncio.timeout(2.0)`
  (`_READINESS_TIMEOUT_SECONDS`, line 16) over `request.app.state.engine`; any exception → `False`;
  `False` sets HTTP 503 + `{'status':'fail'}`.
- **DB module** (`backend_template/modernpackage/db.py`): default URL
  `postgresql+asyncpg://appuser:secret@db:5432/appdb` (line 23); `_NAMING_CONVENTION` applied to
  `MetaData` for deterministic autogenerate (lines 26-32); `Base(AsyncAttrs, DeclarativeBase)`
  (lines 35-38); `database_url()` reads `$DATABASE_URL` else default (lines 41-43);
  `create_engine()` → `create_async_engine(...)` (lines 46-48); `get_db()` async-generator
  dependency yields a session from `app.state.sessionmaker` (lines 51-57); `DbSessionDep` alias
  (line 60).
- **Migrations:** `alembic.ini` sets `script_location = migrations`, `prepend_sys_path = .`, no
  `sqlalchemy.url` (injected at runtime). `migrations/env.py` imports `Base` and sets
  `target_metadata = Base.metadata` (lines 7-12), `compare_type=True` (lines 15-22), injects
  `os.environ['DATABASE_URL']` (line 29), uses `async_engine_from_config` + `NullPool`, bridges via
  `connection.run_sync(do_run_migrations)` (line 32), and `asyncio.run(...)` at module level
  (line 36). `migrations/script.py.mako` is the revision template; `migrations/versions/` holds only
  `.gitkeep`.
- **Container/compose DB integration:** `Containerfile` two-stage uv build; `HEALTHCHECK` hits
  `http://localhost:8000/readyz` (lines 24-25). `compose.yml`: `db` postgres:17 with `pg_isready`
  healthcheck + `pgdata` volume; `migrate` runs `alembic upgrade head` after
  `db: service_healthy`; `app` starts after `migrate: service_completed_successfully` (line 14).
- **Backend tests** (`backend_template/tests/test_app.py`): use `_FakeEngine`/`_FakeConnection`
  (lines 18-43) and `app.dependency_overrides`. Cases: `/livez` pass (46-50); `/readyz` pass with
  `database_ready→True` (53-59); `/readyz` 503 with `→False` (62-68); `database_ready` true/false on
  select success/error (71-76); `get_db` yields a session (79-99). No live DB — connections are
  lazy/faked.

## Q6: How does the frontend define/run tests and connect to the backend?

### Findings
- **Test runner = Vitest** (`frontend_template/package.json:14, 24-32`). `test` script =
  `vitest run` (line 14); `test:watch` = `vitest` (line 15).
- **Vitest config** embedded in `vite.config.ts:12-17`: `environment: 'jsdom'`, `globals: true`,
  `setupFiles: './src/setupTests.ts'`, `coverage.provider: 'v8'`. Triple-slash
  `/// <reference types="vitest/config" />` (line 1).
- **Setup file** `src/setupTests.ts:1`: `import '@testing-library/jest-dom'` (registers matchers).
- **Test** `src/App.test.tsx:1-10`: renders `<App/>`, asserts heading named `modernpackage` is in
  the document. `App.tsx:1-3` renders `<h1>modernpackage</h1>` — no API calls.
- **API schema sync:** `openapi-ts.config.ts:4-6` — `input: 'http://localhost:8000/openapi.json'`,
  `output: 'src/client'`, `plugins: ['@hey-api/client-fetch']`. Run via `npm run generate-client`
  (`package.json:16`) → recipe `generate-client` (`main.py:608-609`).
- **Static schema snapshot:** `frontend_template/openapi.json` (OpenAPI 3.1.0; paths `/livez`,
  `/readyz`); committed but the generator reads the live URL, not this file.
- **Client placeholder:** `src/client/index.ts:1-4` is hand-written, exports `LivezResponse` /
  `ReadyzResponse` as `Record<string, unknown>`; comment says regenerate via `just generate-client`
  once the backend runs. No `createClient`/base URL configured anywhere in `src/`.
- **Runtime backend connection:** dev-server proxy only — `vite.config.ts:5-11` forwards `/api` →
  `http://localhost:8000` (`changeOrigin: true`). Current schema exposes `/livez`,`/readyz` at root,
  not under `/api`.
- **Build/dev tooling** (`package.json:6-17`): `dev`=`vite`, `build`=`tsc --noEmit && vite build`,
  `preview`=`vite preview`, `typecheck`=`tsc --noEmit`, `lint`=`eslint .`, `format`/`format:check`=
  prettier. Deps: react 19, react-dom 19, `@hey-api/client-fetch` (runtime);
  `@hey-api/openapi-ts`, vitest, jsdom, testing-library, eslint/typescript-eslint, vite (dev).
- **TS/eslint config:** `tsconfig.json` references `tsconfig.app.json` (src) + `tsconfig.node.json`
  (vite config); `eslint.config.js` flat config ignores `dist`/`src/client` (line 8);
  `.npmrc:1` = `legacy-peer-deps=true`.

## Cross-Cutting Observations
- **Three injection modes** share one strip/inject/init pipeline: no-flag (`_strip_scaffolding`
  only, `test_e2e.py:195-269`), backend (`_add_backend` + manual `git add -A`, `test_e2e.py:136-192`),
  fullstack (`_inject_templates(fullstack=True)` which stages internally, `test_e2e.py:272-369`).
- **Rename mechanism:** the literal `modernpackage` token is preserved in all template/stub files so
  `just init`'s `git grep | sed` (`Justfile:62-67`) rewrites it to the new module name; staging is
  mandatory so `git grep` sees injected files.
- **Recipe-exclusion convention:** both backend and frontend recipes are appended but kept out of the
  `check:` chain because they require external services (DB / Node) unavailable in CI
  (`main.py:577-578, 590-594`).
- **Graceful boundary degradation** across helpers (`_write_package_metadata`,
  `_append_backend_dependencies`, `_append_*_recipes`): missing files print a notice and return
  rather than raise.
- **e2e tests bypass the GitHub clone**, calling the private `main._*` helpers directly against a
  local clone so local template regressions surface (`test_e2e.py:7-12`).

## Open Areas
- No existing e2e test runs the backend service against a real Postgres or exercises
  `compose.yml`/`Containerfile` at runtime; container behavior is only asserted by file-content
  checks (`test_e2e.py:186-192`) and the backend unit tests use fakes (`test_app.py:18-43`).
- No test exercises actual backend↔frontend HTTP wiring (`/api` proxy, generated client, live
  `openapi.json` fetch); the generated client is a static placeholder
  (`frontend_template/src/client/index.ts`).
- `frontend-build` and `generate-client` recipes are defined but not covered by any e2e test.
