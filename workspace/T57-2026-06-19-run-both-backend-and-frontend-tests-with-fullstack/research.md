# Research Findings

## Q1: How does the e2e test layer scaffold from the local checkout and assert on `just check`? Markers/fixtures/guards?

### Findings
- `tests/test_e2e.py` holds **three** e2e tests, all marked `@pytest.mark.e2e`:
  - `test_scaffolded_package_passes_check` (`tests/test_e2e.py:69`) — no-flag scaffold.
  - `test_scaffolded_backend_package_passes_check` (`tests/test_e2e.py:137`) — `--backend` scaffold.
  - `test_scaffolded_package_has_no_backend_or_frontend` (`tests/test_e2e.py:196`) — negative test.
  - **No `--fullstack`/frontend e2e test currently exists** (file ends at line 270). Frontend is only asserted *absent* in the negative test (`tests/test_e2e.py:228-269`).
- **Scaffold flow** (replicates `init_new_package` against the local repo, not the GitHub URL — docstring `tests/test_e2e.py:7-14`):
  1. `git clone REPO_ROOT → destination` (`tests/test_e2e.py:79`). `REPO_ROOT = parent.parent` (`:28`). Clones **committed** state only (`:11-12`).
  2. `main._write_package_metadata(...)` (`:82`).
  3. `main._strip_scaffolding(...)` (`:91`).
  4. (backend test only) `main._add_backend(...)` then `git add -A` (`:158-160`).
  5. `just init <module_name>` with `_GIT_IDENTITY_ENV` (`:93-97`, env at `:31-36`).
  6. `just check` and `assert check.returncode == 0` (`:110-111`).
- **Markers/config**: `e2e` marker declared in `pyproject.toml:42-44`. Default run **excludes** it via `addopts = "... -m 'not e2e'"` (`pyproject.toml:40`). `Justfile:17-18` `test-e2e` runs `pytest -m e2e --no-cov`. Therefore `just check` (→ `test`) does **not** run e2e tests; CI (`just check`) does not either.
- **Fixture**: built-in `tmp_path` only (`:70`).
- **Tool/skip guard**: `REQUIRED_TOOLS = ('git', 'just', 'uv')` (`:29`); each test loops `shutil.which(tool)` → `pytest.skip(...)` if missing (`:71-73`, `:138-140`, `:197-199`).
- **Subprocess helper** `_run` (`:39-51`): `subprocess.run(..., check=False, capture_output=True, text=True)`.
- **Token helpers** for the negative test: `_dependency_tokens()` (`:57-60`) splits `main._BACKEND_DEPENDENCIES + _BACKEND_DEV_DEPENDENCIES`; `_recipe_tokens()` (`:63-66`) regex-extracts recipe names from `_BACKEND_RECIPES + _FRONTEND_RECIPES` via `_RECIPE_NAME_RE` (`:54`).
- The inner `just check` runs `uv sync` + networked `pip-audit`, so the test needs network and takes minutes (`:12-14`).

## Q2: Backend template tests — runner, dependencies, recipes, place in the `check` chain

### Findings
- Tests live at `backend_template/tests/test_app.py` (95 lines). Runner is **pytest** (the generated package's). Six `test_*` functions covering `/livez`, `/readyz` pass/fail, `database_ready`, `get_db` (`backend_template/tests/test_app.py:45-95`).
- Uses FastAPI `TestClient` (`:7`, `:46`), which depends on **httpx**. Imports from `modernpackage.app/db/health` and `sqlalchemy.ext.asyncio` (`:7-11`).
- DB is **faked** in-test: `_FakeEngine`/`_FakeConnection` (`:17-42`); no real database needed.
- **Dependencies injected** by `_add_backend`:
  - Runtime `_BACKEND_DEPENDENCIES` = fastapi, sqlalchemy[asyncio], asyncpg, alembic, uvicorn (`modernpackage/main.py:565-571`).
  - Dev `_BACKEND_DEV_DEPENDENCIES = ('httpx',)` for TestClient (`main.py:573-574`).
- **Where they run**: `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` merges `backend_template/tests/` into the clone's `tests/` (`main.py:1002`). They then run as normal pytest under the generated package's `just test`, which **is** part of `check` (`Justfile:53` includes `test`). So backend tests are inside the generated `check` chain.
- **Migration recipes** (`migrate`, `makemigration`, `migration-check`) are appended to the Justfile but **deliberately NOT in `check`** — they need a live DB (`main.py:576-588`, esp. comment `:576-578`).

## Q3: Frontend template tests — package.json scripts, runner, `frontend-*` recipes, and `check` chain membership

### Findings
- `frontend_template/package.json` scripts (`:6-17`): `test` = `vitest run`, `test:watch` = `vitest`; also `dev`, `build` (`tsc --noEmit && vite build`), `preview`, `typecheck` (`tsc --noEmit`), `lint` (`eslint .`), `format` / `format:check` (prettier), `generate-client` (`openapi-ts`).
- **Runner**: Vitest. Config in `frontend_template/vite.config.ts:12-17` — `environment: 'jsdom'`, `globals: true`, `setupFiles: './src/setupTests.ts'`, `coverage: { provider: 'v8' }`. `setupTests.ts` imports `@testing-library/jest-dom` (`:1`).
- Example test `frontend_template/src/App.test.tsx` uses `@testing-library/react` `render`/`screen` + `vitest` `describe/it/expect` (`:1-10`).
- Test deps in `package.json` devDependencies: `vitest`, `@vitest/coverage-v8`, `jsdom`, `@testing-library/{react,jest-dom,user-event}` (`:23-43`).
- **`frontend-*` recipes** are defined in `_FRONTEND_RECIPES` (`modernpackage/main.py:595-614`), appended to the generated Justfile by `_append_frontend_recipes` (`main.py:946-959`):
  - `frontend-install` (`npm ci`), `frontend-build`, `frontend-test` (`npm run test`), `frontend-lint`, `generate-client`, and aggregate `frontend-check: frontend-install` → `npm run format:check && lint && typecheck && test`.
  - Each is `cd frontend && ...`; none have `: sync` (Node, not uv).
- **Not part of `check`**: explicit comment `main.py:590-594` — excluded because the generated package's CI has no Node. The generated `check` chain stays the Python one inherited from the root `Justfile:53`; no recipe references `frontend-*`.

## Q4: Fullstack injection — `_inject_templates`, `_add_frontend`, `_add_backend`, appenders, token rename, staging

### Findings
- Entry: `init_new_package` calls `if backend or fullstack: _inject_templates(new_package_path, fullstack=fullstack)` (`main.py:1065-1066`), after `_strip_scaffolding`.
- `_inject_templates` (`main.py:979-989`): always `_add_backend(...)`; if `fullstack`, also `_add_frontend(...)`; then `_stage_injected_files(...)`.
- `_add_backend` (`main.py:992-1004`): `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` (merges into `modernpackage/` + `tests/`), then `_append_backend_dependencies(pyproject)` and `_append_backend_recipes(Justfile)`.
- `_add_frontend` (`main.py:962-976`): `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True)` (isolates Node project under `frontend/`), then `_append_frontend_recipes(Justfile)`. Adds **no** Python deps and spawns **no** child processes.
- Template dirs resolved relative to `__file__`: `_BACKEND_TEMPLATE_DIR` (`main.py:552-554`), `_FRONTEND_TEMPLATE_DIR` (`main.py:559-561`); shipped in wheels via `[tool.hatch.build] include = [..., "frontend_template/**"]` (`pyproject.toml:51`).
- **Dependency appender** `_append_backend_dependencies` (`main.py:884-906`): replaces `dependencies = []\n` with backend runtime deps; prepends httpx into `dev = [`. Graceful no-op if file absent.
- **Recipe appenders**: `_append_backend_recipes` (`main.py:909-922`) appends `_BACKEND_RECIPES`; `_append_frontend_recipes` (`main.py:946-959`) appends `_FRONTEND_RECIPES`.
- **Token rename**: copied files keep the literal `modernpackage` token (e.g. `package.json` `"name": "modernpackage"` `frontend_template/package.json:2`, `App.test.tsx` heading `modernpackage` `:8`, Python imports). `just init`'s `git grep -l 'modernpackage' | xargs sed` rewrites them (`Justfile:62-67`).
- **Staging**: `_stage_injected_files` (`main.py:925-943`) runs `git add -A` via `Popen`; required because the rename sed only touches **tracked** files, and copied files are untracked. The backend e2e test does the equivalent `git add -A` manually (`tests/test_e2e.py:159`).

## Q5: Runtime tooling in test/CI environment; how recipes/tests handle absent tooling

### Findings
- **GitLab CI** (`.gitlab-ci.yml`): `image: python:latest`; `before_script` installs `uv`, `uv tool install rust-just`, `just sync`; the `test` job runs `just check` (`.gitlab-ci.yml:13-22`). **No Node/npm, no database.**
- **GitHub Actions** (`.github/workflows/check-modernpackage-on-python314.yml`): `ubuntu-latest`, Python 3.14, installs uv + rust-just, runs `just check`. **No Node/npm, no database.**
- **Required tools**: only `git`, `just`, `uv` (`main.py:56`, `tests/test_e2e.py:29`). e2e tests `pytest.skip` when any is absent (`:71-73`). The CLI `_verify_required_tools` raises with install hints (`main.py:795-806`).
- **Network**: inner `just check` runs `uv sync` + networked `pip-audit` (`Justfile:42`, `tests/test_e2e.py:12-14`); offline runners fail at sync.
- **Node**: not provided anywhere in CI; frontend recipes assume the developer runs them locally (`main.py:590-594`).
- **Database**: not provided in CI. Backend tests avoid a real DB via fakes (`backend_template/tests/test_app.py:17-42`). `compose.yml` defines a Postgres 17 service for runtime, with healthcheck + `migrate` service `service_completed_successfully` gating (`backend_template/compose.yml:3-38`) — runtime only, not used by tests.
- `pytest` is told not to collect template trees: `norecursedirs = ["backend_template", "frontend_template"]` (`pyproject.toml:41`).

## Q6: Relationship between `check` and external-runtime recipes; what is excluded and why

### Findings
- Root `check` chain: `check-format check-lint check-complexity check-typecheck test audit` (`Justfile:53`). Same chain is inherited by generated packages (template Justfile is the repo Justfile minus stripped pieces).
- **Excluded — needs a live database**: `migrate`, `makemigration`, `migration-check` (`_BACKEND_RECIPES`, `main.py:579-588`); explicit comment "NOT added to the `check` chain — they need a live database" (`main.py:576-578`).
- **Excluded — needs Node**: `frontend-install/build/test/lint`, `generate-client`, `frontend-check` (`_FRONTEND_RECIPES`, `main.py:595-614`); comment "NOT added to the `check` chain — they need Node, which the generated package's CI does not have; mirrors the backend-recipes precedent" (`main.py:590-594`).
- **Excluded — e2e tests**: `test` uses `-m 'not e2e'` (`pyproject.toml:40`); e2e only via `just test-e2e` (`Justfile:17-18`).
- `check-backend-template: sync` (`Justfile:76-77`) runs `ruff check backend_template` — lints the template **in this repo**; it is a standalone recipe, **not** wired into `check`.
- Backend **unit tests** (faked DB) DO run in `check` via `test`; only DB/Node-requiring recipes are split out.

## Cross-Cutting Observations
- Two exclusion precedents are explicitly cited as a pattern: backend migration recipes (DB) and frontend recipes (Node) are appended to the Justfile but kept out of `check` (`main.py:576-578`, `:590-594`). A `frontend-check` aggregate exists for local-only use.
- Injection is uniform: copytree → append deps → append recipes → `git add -A` so `just init`'s rename sed sees files. Frontend differs by copying into `frontend/` and adding no Python deps.
- Graceful-boundary pattern in every appender: missing file → stderr notice + return, never raises (`main.py:891-898`, `:914-921`, `:952-958`).
- e2e tests exercise the *committed* tree and are themselves excluded from the default/CI test run; they must be invoked deliberately (`just test-e2e`).

## Open Areas
- **No `--fullstack` e2e test exists** in `tests/test_e2e.py`; there is no test that scaffolds a fullstack package and runs both backend (`just test`/`check`) and frontend (`frontend-test`/`frontend-check`) suites. The questions reference running "both backend and frontend tests with fullstack," but the current suite only asserts frontend *absence* in the no-extras negative test (`tests/test_e2e.py:228-269`).
- No recipe currently runs the frontend Vitest suite as part of any automated gate; `frontend-check` is local-only and uncalled by `check`.
