# Research Findings

All references are to `/home/niekas/tools/modernpackage/`.

## Q1: How does the CLI inject frontend/backend templates — copy functions, dependency/recipe appends, inclusion control?

### Findings
- **Flags control inclusion.** `--backend`/`--fastapi` sets `backend=True`; `--fullstack`/`--reactjs` sets `fullstack=True` (`modernpackage/main.py:363-376`). Both are plain `store_true` booleans threaded through `parse_args` → `main` → `init_new_package` (`main.py:1118-1130`, `1007-1018`).
- **Injection gate:** `if backend or fullstack: _inject_templates(new_package_path, fullstack=fullstack)` (`main.py:1065-1066`), run after clone, `_write_package_metadata`, and `_strip_scaffolding`, but before `just init`.
- **`_inject_templates`** (`main.py:979-989`): always calls `_add_backend`; calls `_add_frontend` only when `fullstack=True`; then `_stage_injected_files` (`git add -A`). So `--fullstack` implies the backend too; there is no frontend-only path.
- **`_add_backend`** (`main.py:992-1005`): `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` (merges into clone's `modernpackage/` and `tests/`), then `_append_backend_dependencies` + `_append_backend_recipes`.
- **`_add_frontend`** (`main.py:962-977`): `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True)` (isolated subdir), then `_append_frontend_recipes`. Adds **no** Python deps and spawns **no** child processes.
- **Template dirs** resolved relative to `main.py` so they work from source checkout or installed wheel: `_BACKEND_TEMPLATE_DIR` (`main.py:552-554`), `_FRONTEND_TEMPLATE_DIR` (`main.py:559-561`).
- **Dependency append:** `_append_backend_dependencies` (`main.py:884-906`) replaces `dependencies = []` with `_BACKEND_DEPENDENCIES` (fastapi, sqlalchemy[asyncio], asyncpg, alembic, uvicorn — `main.py:565-571`) and prepends `_BACKEND_DEV_DEPENDENCIES = ('httpx',)` (`main.py:574`) into the `dev` group. No frontend dependency append exists.
- **Recipe appends:** `_append_backend_recipes` (`main.py:909-922`) appends `_BACKEND_RECIPES` (`migrate`, `makemigration`, `migration-check` — `main.py:579-588`). `_append_frontend_recipes` (`main.py:946-959`) appends `_FRONTEND_RECIPES` (`frontend-install`, `frontend-build`, `frontend-test`, `frontend-lint`, `generate-client`, `frontend-check` — `main.py:595-614`). Both no-op with a stderr notice if the Justfile is absent.
- **Removal first:** `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:519-526`) always removes `backend_template` and `frontend_template` from the clone; they are re-injected only when flagged.
- **Staging:** `_stage_injected_files` runs `git add -A` (`main.py:925-943`) so `just init`'s `git grep` rename sees copied files.
- **Dry-run preview** mentions backend/frontend additions (`main.py:723-728`).
- Unit tests: `test_add_backend_*` / `test_add_frontend_*` / `test_append_*` (`tests/test_main.py:1629-1789`); `test_add_frontend_no_npm_or_subprocess` (`tests/test_main.py:1769`) asserts no subprocess at scaffold time.

## Q2: React/Vite frontend template structure — rendering, testing, dev server/proxy, typed API client

### Findings
- **Render:** `src/main.tsx:5-9` mounts `<App/>` in `<StrictMode>` via `createRoot(document.getElementById('root')!)`. `src/App.tsx:1-3` is a named export returning `<h1>modernpackage</h1>` (no state/router/client usage).
- **Unit test:** `src/App.test.tsx:5-9` renders `<App/>`, asserts the `modernpackage` heading via `@testing-library/react` + jest-dom. Setup: `src/setupTests.ts:1` imports `@testing-library/jest-dom`.
- **Vitest config** in `vite.config.ts:13-16`: `environment: 'jsdom'`, `globals: true`, `setupFiles: './src/setupTests.ts'`, `coverage.provider: 'v8'`.
- **Dev server proxy** (`vite.config.ts:7-11`): requests starting `/api` proxied to `http://localhost:8000` with `changeOrigin: true`. Plugin `@vitejs/plugin-react` (`vite.config.ts:6`).
- **Typed API client generation:** `openapi-ts.config.ts:4-6` — `input: 'http://localhost:8000/openapi.json'` (fetched from live backend), `output: 'src/client'`, `plugins: ['@hey-api/client-fetch']`. A committed static snapshot `openapi.json` describes `GET /livez` and `GET /readyz`.
- **Current client is a placeholder:** `src/client/index.ts:1-4` is a hand-written stub exporting only `type LivezResponse = Record<string, unknown>` and `type ReadyzResponse = Record<string, unknown>`; comment says regenerate via `just generate-client`. `App.tsx` does not import it.
- **npm scripts** (`package.json:6-17`): `dev`=`vite`, `build`=`tsc --noEmit && vite build`, `typecheck`=`tsc --noEmit`, `lint`=`eslint .`, `format`=`prettier --write .`, `format:check`=`prettier --check .`, `test`=`vitest run`, `test:watch`=`vitest`, `generate-client`=`openapi-ts`.
- **Deps:** `@hey-api/client-fetch ^0.10.0` (runtime, `package.json:22`), `@hey-api/openapi-ts ^0.64.0` (dev, line 24), `@tanstack/react-query ^5.0.0` (dev, line 25, currently unused).

## Q3: FastAPI backend template — endpoints, payloads, status codes, DB interaction

### Findings
- **Endpoints** (both in `backend_template/modernpackage/health.py`, router included at `app.py:33`):
  - `GET /livez` (`health.py:31-34`): no deps/DB; always `200` with `{"status": "pass"}`.
  - `GET /readyz` (`health.py:37-46`): depends on `database_ready`; `200 {"status":"pass"}` when reachable (`health.py:46`), else `503 {"status":"fail"}` (`health.py:43-45`).
- **DB engine/session** (`db.py`): `create_async_engine(database_url())` lazily (`db.py:46-48`); `database_url()` reads `DATABASE_URL` env, default `postgresql+asyncpg://appuser:secret@db:5432/appdb` (`db.py:23,41-43`). `lifespan` builds engine + `async_sessionmaker(expire_on_commit=False)` on `app.state` at startup, `await engine.dispose()` on shutdown (`app.py:21-27`).
- **Session dependency:** `get_db` async generator yields a session (`db.py:51-57`); `DbSessionDep = Annotated[AsyncSession, Depends(get_db)]` (`db.py:60`) — defined but no route uses it.
- **Readiness probe:** `database_ready` opens `engine.connect()` under `asyncio.timeout(2.0)`, runs `text('SELECT 1')`, returns `False` on any exception else `True` (`health.py:16,19-28`).
- **Models:** `Base` (AsyncAttrs + DeclarativeBase) with naming-convention `MetaData` (`db.py:26-38`); **no concrete ORM model classes exist** in the template.
- **Backend tests:** `backend_template/tests/test_app.py` uses `TestClient(create_app())` and `app.dependency_overrides` for `database_ready`. Cases: livez 200/pass (`:46-50`); readyz 200/pass override-True (`:53-59`); readyz 503/fail override-False (`:62-68`); `database_ready` direct True/False via fakes (`:71-76`); `get_db` yields a session (`:79-99`). Fakes `_FakeConnection`/`_FakeEngine` at `:18-43`.

## Q4: Test setups across templates and repo — frontend unit, backend, e2e

### Findings
- **Top-level pytest config** (`pyproject.toml:39-44`): `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`; `norecursedirs = ["backend_template","frontend_template"]` (template tests never collected by repo run); marker `e2e`.
- **Justfile test recipes:** `test` (`Justfile:14`) = `pytest -n "$(nproc --ignore=1)"`; `test-e2e` (`Justfile:17`) = `pytest -m e2e --no-cov`.
- **Frontend unit test:** `frontend_template/src/App.test.tsx` run via `vitest run` (`package.json:14`); see Q2.
- **Backend tests:** `backend_template/tests/test_app.py`; see Q3. Run inside generated package by `just check` after backend injection.
- **Scaffolding e2e:** `tests/test_e2e.py`, all `@pytest.mark.e2e`, skip-guarded on tool presence (`REQUIRED_TOOLS=('git','just','uv')`, `_REQUIRED_RUNTIME_TOOLS` adds `npm`):
  - `test_scaffolded_package_passes_check` (`:122-186`): no-flags scaffold, asserts `just check`==0, metadata applied, scaffolding artifacts removed.
  - `test_scaffolded_backend_package_passes_check` (`:189-246`): `_add_backend` + `git add -A`, asserts app/health files, recipes, container/compose/migration files present.
  - `test_scaffolded_package_has_no_backend_or_frontend` (`:248-322`): asserts backend/frontend artifacts absent and import tokens not present.
  - `test_scaffolded_fullstack_package_passes_check` (`:325-421`): `_inject_templates(fullstack=True)`, asserts `just check`, `just frontend-install`, `just frontend-test` succeed and `check:` recipe excludes `frontend-`.
  - `test_fullstack_package_runs_end_to_end` (`:424-532`): full compose bring-up; see Q5.
- The repo's own `main.py` is unit-tested in `tests/test_main.py` (1839 lines) with `Popen`/`run` mocked.

## Q5: Containerization and DB orchestration for a generated package; how e2e brings up/probes the stack

### Findings
- **Containerfile** (`backend_template/Containerfile`): two-stage. Builder (`:4-17`) `python:${PYTHON_VERSION}-slim` (default 3.14), copies `uv`/`uvx` from `ghcr.io/astral-sh/uv:0.5`, `uv sync --locked --no-install-project --no-dev` (cache+bind mounts) then `uv sync --locked --no-dev --no-editable`. Runtime (`:19-26`) copies `/app`, prepends `/app/.venv/bin` to PATH, `HEALTHCHECK` (interval 30s/timeout 5s/start 20s/3 retries) hits `/readyz` via stdlib `urllib`, `CMD` `uvicorn modernpackage.app:create_app --factory --host 0.0.0.0 --port 8000`. `.dockerignore` excludes `.venv .git __pycache__ *.pyc .ruff_cache .mypy_cache`.
- **compose.yml** (`backend_template/compose.yml`): no `version:` key (V2). Services:
  - `db` (`:23-36`): `postgres:17`, env appuser/secret/appdb, healthcheck `pg_isready -U appuser -d appdb` (interval 10s/timeout 5s/retries 5/start 30s), volume `pgdata`.
  - `migrate` (`:15-22`): built from `.`, command `["alembic","upgrade","head"]`, `depends_on db: service_healthy`.
  - `app` (`:4-14`): built from `.`, port `127.0.0.1:8000:8000`, `depends_on db: service_healthy` + `migrate: service_completed_successfully`.
- **Migrations:** `alembic.ini` has no `sqlalchemy.url` (`:1`), `script_location=migrations`, `prepend_sys_path=.`. `migrations/env.py` sets `target_metadata=Base.metadata` (`:7,12`), `compare_type=True` (`:15-22`), async online-only path reading `DATABASE_URL` (`:29`), `asyncio.run(run_async_migrations())` at import (`:36`). `script.py.mako` is the standard revision template.
- **e2e full-stack probe** `test_fullstack_package_runs_end_to_end` (`tests/test_e2e.py:424-532`): `_detect_compose_command` tries docker compose / podman compose / podman-compose (`:60-88`); skip if none. Scaffolds via `_inject_templates(fullstack=True)` + `just init`. Brings up with `[*compose,'up','-d','--wait','--build']` (`:476-477`); `try/finally` always runs `compose down -v` (`:531-532`). Probes `http://127.0.0.1:8000/livez` (200, body contains `pass`) and `/readyz` (200) via `_http_get` (30s timeout, `:91-104,481-486`). Then `just frontend-install`, `just generate-client` (regenerates client from live `/openapi.json`), asserts client contains `livez`/`readyz` and not `Record<string, unknown>`; `just frontend-build` then asserts `frontend/dist/index.html` exists (`:490-525`). No explicit overall timeout; relies on compose healthcheck timings.

## Q6: Justfile recipes and CI for this repo and generated packages; default vs on-demand checks

### Findings
- **Repo `check` chain** (`Justfile:53`): `check: check-format check-lint check-complexity check-typecheck test audit` (ruff format check, ruff lint, ruff C901 complexity, mypy, pytest+cov, pip-audit). A `deadcode` step is commented out.
- **Individual recipes** (`Justfile`): `sync`(8), `compile`(11), `test`(14), `test-e2e`(17), `format`(20), `lint`(23), `typecheck`(26), `check-*`(29-38), `audit`(41), `fix`(51), `publish`(55), `init`(60), `check-backend-template`(76, `ruff check backend_template`), `lock`(79). No top-level recipe needs Node, a DB, or a container runtime; e2e tests are excluded by default (`-m 'not e2e'`).
- **`just init`** (`Justfile:60-74`): default arg `modernpackage`; platform-conditional `git grep -l 'modernpackage' | xargs sed` rename (Linux `:62-64`, macOS `:65-67`); version reset to `0.0.1` in `__init__.py` (`:68`); `mv modernpackage {{package_name}}` (`:69`); `rm -fr .git/ .venv`, `git init -b main`, `git add .`, commit (`:70-73`).
- **Generated-package recipes are scaffolder-injected, not template-shipped.** Neither `backend_template/` nor `frontend_template/` contains a Justfile. Backend recipes (`migrate`/`makemigration`/`migration-check`) come from `_BACKEND_RECIPES` (`main.py:579-588`); frontend recipes from `_FRONTEND_RECIPES` (`main.py:595-614`). Comments at `main.py:579-580,591-594` state these are deliberately **not** added to the `check` chain because they need a DB / Node.
- **`frontend-check`** (`main.py:611-614`) aggregates `format:check && lint && typecheck && test` but is on-demand only; the generated package's `check:` recipe excludes `frontend-` (asserted at `tests/test_e2e.py:418-421`).
- **CI — GitLab** (`.gitlab-ci.yml`): single `test` job, `python:latest`, `before_script` installs uv + rust-just + `just sync`, script runs `just check`. No stages/rules/manual jobs; runs on every push.
- **CI — GitHub** (`.github/workflows/check-modernpackage-on-python314.yml`): triggers on push/PR to `main`; job `run-linters-and-tests` on `ubuntu-latest`, Python 3.14, installs uv + rust-just, runs `just check`. No matrix/cache/manual triggers. Neither CI runs e2e or any Node/DB/container job by default.

## Cross-Cutting Observations
- **Layering:** backend merges into the package root/`modernpackage/`/`tests/`; frontend is isolated under `frontend/`. The literal token `modernpackage` is preserved throughout so `just init`'s rename sed rewrites it (asserted via `test_injected_files_have_no_unrenamed_token_after_sed`, `tests/test_main.py:1646`).
- **Node/DB/container gates are always on-demand:** never in `check`, never in CI; only exercised by `@pytest.mark.e2e` tests run via `just test-e2e`.
- **Graceful boundary degradation:** dependency/recipe/metadata appenders no-op with a stderr notice when target files are absent (`main.py:884-959`).
- **Health endpoints `/livez` and `/readyz`** are the integration contract spanning Containerfile healthcheck, compose ordering, e2e HTTP probes, the committed `openapi.json`, and the generated TS client.

## Open Areas
- **Playwright / browser end-to-end testing is absent.** No Playwright config, dependency, recipe, or test exists anywhere (`package.json`, `frontend_template/`, Justfiles, e2e tests). The only frontend test tooling is Vitest + Testing Library (jsdom). The existing "end-to-end" test (`test_fullstack_package_runs_end_to_end`) probes HTTP and runs `vite build`, but performs no browser automation.
- `@tanstack/react-query` is a declared dev dependency (`package.json:25`) but is not used in any source file.
