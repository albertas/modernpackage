# Research Findings

## Q1: How do the existing e2e tests scaffold a fullstack package and bring the stack up/down? (tool detection, skips vs failures)

### Findings
- Two test entry points share one pattern: `tests_e2e/test_backend_e2e.py` (backend-only) and `tests/test_e2e.py::test_fullstack_package_runs_end_to_end` (`tests/test_e2e.py:424-550`).
- Shared scaffold helper: `scaffold_backend_package()` at `tests_e2e/_scaffold.py:132-168`. `_run()` wrapper (`_scaffold.py:28-40`, mirrored `tests/test_e2e.py:45-57`) always uses `check=False`, captures stdout/stderr — never raises; callers assert on `returncode`.
- **Tool detection / skips:** `REQUIRED_TOOLS = ('git','just','uv')` at `_scaffold.py:18` and `tests/test_e2e.py:31`. Each test loops `if shutil.which(tool) is None: pytest.skip(...)` (`test_backend_e2e.py:23-25`, `test_e2e.py:124-126`). Fullstack adds `npm`: `_REQUIRED_RUNTIME_TOOLS = (*REQUIRED_TOOLS,'npm')` (`test_e2e.py:35`, loop at `440-441`).
- **Compose detection:** `_detect_compose_command()` (`_scaffold.py:43-64`, dup `test_e2e.py:60-88`) probes `('docker','compose')`, `('podman','compose')`, `('podman-compose',)` by running `[*candidate,'version']` with `check=False`; catches `FileNotFoundError`→`continue`; returns first `returncode==0` or `None`. `None` → `pytest.skip('no compose command available ...')` (`test_backend_e2e.py:42-43`, `test_e2e.py:444-445`).
- **Scaffold steps** (`_scaffold.py:132-168`): clone `REPO_ROOT` (resolved `_scaffold.py:17`) → `destination = tmp_path/module_name` (`:143`, clone `:145`); write metadata `main._write_package_metadata` (`:148-155` → `main.py:446-493`); strip scaffolding `main._strip_scaffolding` (`:156` → `main.py:643-660`); inject backend `main._add_backend` (`:157` → `main.py:995-1007`); `git add -A` (`:158-159`); `just init module_name` with `_GIT_IDENTITY_ENV` (`:161-166`).
- `_GIT_IDENTITY_ENV` (`_scaffold.py:20-25`) sets `GIT_AUTHOR_*`/`GIT_COMMITTER_*` so the `just init` initial commit succeeds headless. `init` recipe body at `Justfile:60-74`.
- **Compose up/--wait:** `_run([*compose,'up','-d','--wait','--build'], cwd=destination)` (`test_backend_e2e.py:51`, `test_e2e.py:476`). `--wait` blocks until healthchecks pass.
- **Teardown:** `try/finally` with `_run([*compose,'down','-v'], cwd=destination)` always runs (`test_backend_e2e.py:50/95`, `test_e2e.py:475/549-550`); `-v` removes volumes.

## Q2: How does the backend register routes and wire database access?

### Findings
- **Factory:** `create_app()` at `backend_template/modernpackage/app.py:30-34` builds `FastAPI(lifespan=lifespan)` (`:32`) and `app.include_router(health_router)` (`:33`, no prefix).
- **Lifespan:** `@asynccontextmanager async def lifespan` (`app.py:18-27`). Startup (`:21-23`): `create_engine()`→`app.state.engine`; `async_sessionmaker(expire_on_commit=False)`→`app.state.sessionmaker`. Shutdown (`:26-27`): `finally: await engine.dispose()`.
- **health.py:** `router = APIRouter()` (`health.py:14`). `_READINESS_TIMEOUT_SECONDS = 2.0` (`:16`). `database_ready(request)` dependency (`:19-28`) reads `request.app.state.engine`, `asyncio.timeout(2.0)` around `engine.connect()` + `execute(text('SELECT 1'))`; bare `except Exception: return False`.
- Routes: `@router.get('/livez')` → `livez()` returns `{'status':'pass'}` unconditionally (`health.py:31-34`). `@router.get('/readyz')` → `readyz(ready: Annotated[bool, Depends(database_ready)], response: Response)` (`:37-46`); on `not ready` sets `response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE` + `{'status':'fail'}`, else `{'status':'pass'}`.
- **db.py:** `_DEFAULT_DATABASE_URL = 'postgresql+asyncpg://appuser:secret@db:5432/appdb'` (`db.py:23`). `_NAMING_CONVENTION` (`:26-32`). `class Base(AsyncAttrs, DeclarativeBase)` with `metadata = MetaData(naming_convention=_NAMING_CONVENTION)` (`:35-38`). `database_url()` returns `os.environ.get('DATABASE_URL') or _DEFAULT_DATABASE_URL` (`:41-43`). `create_engine()` → `create_async_engine(database_url())` (`:46-48`).
- **Request-scoped session:** `get_db(request)` (`db.py:51-57`) casts `request.app.state.sessionmaker`, `async with sessionmaker() as session: yield session`. Alias `DbSessionDep = Annotated[AsyncSession, Depends(get_db)]` (`:60`).
- Tests (`backend_template/tests/test_app.py`): `TestClient(create_app())` for `/livez` (`:46`); `app.dependency_overrides[database_ready]` for readyz branches (`:53,62`); fake engine/connection for `database_ready` (`:71,75`); `get_db` exercised directly (`:79`).

## Q3: How are DB schema changes defined and applied? (models, Alembic, recipes, host-side migration in tests)

### Findings
- **Model pattern:** subclass `Base` (`backend_template/modernpackage/db.py:35-38`); all models share `Base.metadata`.
- **alembic.ini:** `script_location = migrations` (`:4`), `prepend_sys_path = .` (`:5`); NO `sqlalchemy.url` key — comment (`:1-2`) says URL injected from `$DATABASE_URL` in env.py.
- **migrations/env.py** (fully async, no offline path): `from modernpackage.db import Base` (`:7`); `target_metadata = Base.metadata` (`:12`); `config_section['sqlalchemy.url'] = os.environ['DATABASE_URL']` (`:29`, hard KeyError if unset); `async_engine_from_config(..., poolclass=pool.NullPool)` (`:30`); `do_run_migrations` calls `context.configure(..., compare_type=True)` (`:15-22`); bridged via `connection.run_sync(do_run_migrations)` (`:31-32`); top-level `asyncio.run(run_async_migrations())` (`:36`). Template `script.py.mako` defines `upgrade()`/`downgrade()` (`:20,23`).
- **Justfile recipes** (`_BACKEND_RECIPES`, `modernpackage/main.py:579-588`): `migrate: sync → uv run alembic upgrade head`; `makemigration message: sync → uv run alembic revision --autogenerate -m "{{message}}"`; `migration-check: sync → uv run alembic check`. Appended by `_append_backend_recipes` (`main.py:912-925`).
- **Compose migrate service** (`backend_template/compose.yml:15-19`): `migrate` service `command: ["alembic","upgrade","head"]` with `DATABASE_URL` inline; `app` depends on `migrate: condition: service_completed_successfully` (`:13-14`).
- **Host-side migration in tests:** `_expose_db_port(destination)` (`_scaffold.py:83-102`, called `test_backend_e2e.py:45`) injects `ports: "127.0.0.1:5432:5432"` into `compose.yml` before up. `_PRODUCT_MODEL_SOURCE` (`_scaffold.py:105-118`) is a `class Product(Base)` string with `id`/`name` columns; `_register_product_model(source_dir)` (`:121-129`) appends it to the renamed `db.py` via `write_text(read_text() + source)` (called `test_backend_e2e.py:64`). `_HOST_DATABASE_URL = 'postgresql+asyncpg://appuser:secret@localhost:5432/appdb'` (`_scaffold.py:80`); `migration_env = os.environ | {'DATABASE_URL': _HOST_DATABASE_URL}` (`test_backend_e2e.py:65`). Then `just makemigration 'add products'` (`:67-73`) and `just migrate` (`:76`) run with that env. Assertions: version file contains `create_table('products')` (`:83-89`); final `_http_get('http://127.0.0.1:8000/readyz')` == 200 (`:92-93`).

## Q4: How does the frontend fetch/render backend data and produce the typed client?

### Findings
- **App.tsx:** `fetchStatus(path)` (`frontend_template/src/App.tsx:6-17`) uses native `fetch(path)` then `response.json()`; returns `'pass'`/`'fail'`/`'unavailable'`. Two `useState` init to `'checking'` (loading state) (`:20-21`). One `useEffect([])` fires `fetchStatus('/livez')` (`:24`) and `fetchStatus('/readyz')` (`:29`) concurrently, mapping to `'healthy'/'unhealthy'/'unavailable'` and `'ready'/'not ready'/'unavailable'` (`:25-32`). Renders `<dl>` interpolating `{appHealth}`/`{dbHealth}` (`:36-46`). No spinner/error element; states are inline strings. **App.tsx does not use the generated client — it calls `fetch` directly.**
- **vite.config.ts proxy:** both `server` (`:9-13`) and `preview` (`:17-21`) proxy `/api`, `/livez`, `/readyz` → `target: 'http://localhost:8000', changeOrigin: true`.
- **src/client/index.ts:** hand-written placeholder (comment `:1-2`); exports only types `LivezResponse`/`ReadyzResponse` as `Record<string,unknown>` (`:3-4`); no functions, no `@hey-api` imports. Stub at the generator's output path.
- **openapi-ts.config.ts** (`:1-7`): `input: 'http://localhost:8000/openapi.json'`, `output: 'src/client'`, `plugins: ['@hey-api/client-fetch']`. Live backend is the schema source.
- **generate-client:** `package.json:16` `"generate-client": "openapi-ts"` (binary `@hey-api/openapi-ts`, devDep `:26`); reads config by convention. Committed `openapi.json` snapshot describes `livez_livez_get` (`/livez`) and `readyz_readyz_get` (`/readyz`) with empty response schemas; generator pulls live, not from this file.

## Q5: How are Playwright e2e tests structured and executed?

### Findings
- **Spec** `frontend_template/e2e/status.spec.ts:3-8`: single test, `page.goto('/')`, asserts `getByRole('heading',{name:'modernpackage'})`, `getByText('healthy')`, `getByText('ready')` all `.toBeVisible()`. DOM-only, no direct API calls.
- **playwright.config.ts** (11 lines): `testDir: './e2e'` (`:4`); `baseURL: 'http://localhost:4173'` (`:5`, Vite preview port); `webServer: { command: 'npm run preview', url: 'http://localhost:4173', reuseExistingServer: !process.env.CI }` (`:6-10`). No `projects` key → Chromium default.
- **Justfile recipe** `frontend-test-e2e` in `_FRONTEND_RECIPES` (`modernpackage/main.py:611-612`): `cd frontend && npx playwright install --with-deps chromium && npm run test:e2e`. `test:e2e` = `playwright test` (`frontend_template/package.json:17`). Browser install is unconditional each run.
- **Host-side invocation** (`tests/test_e2e.py:538-548`): `_run(['just','frontend-test-e2e'], cwd=destination)`. Skip gate: `if returncode != 0 and 'playwright install' in (stdout+stderr): pytest.skip(...)` (`:539-545`); otherwise `assert returncode == 0` (`:546-548`) so real spec failures still fail. Earlier steps: `compose up --wait --build` (`:476`), `just frontend-install`→`generate-client`→`frontend-build`, assert `frontend/dist/index.html` (`:490-530`). Round-trip: browser → local `vite preview` (4173) → live compose backend (8000). Teardown `compose down -v` in `finally` (`:549-550`).

## Q6: Conventions for generated Justfile recipes and the token-rename step

### Findings
- Generated package's Justfile = the cloned repo root `Justfile`; backend/frontend recipes are **appended** at scaffold time.
- **Backend recipes** `_BACKEND_RECIPES` (`main.py:579-588`); appended by `_append_backend_recipes` (`:912-925`, `write_text(content + _BACKEND_RECIPES)` at `:925`), called from `_add_backend` (`:1007`), from `_inject_templates` (`:989`).
- **Frontend recipes** `_FRONTEND_RECIPES` (`main.py:595-617`): `frontend-install` (`npm ci`), `frontend-build`, `frontend-test`, `frontend-lint`, `generate-client`, `frontend-test-e2e`, and aggregate `frontend-check: frontend-install` (`format:check && lint && typecheck && test`). Appended by `_append_frontend_recipes` (`:949-962`), from `_add_frontend` (`:979`), from `_inject_templates` gated `fullstack=True` (`:991`).
- **Base recipes** (`Justfile`): `sync`(`:8`), `compile`(`:11`), `test`(`:14`), `format`(`:20`), `lint`(`:23`), `typecheck`(`:26`), `check-*`(`:29-41`), `check`(`:53`), `init`(`:60-74`). No `dev` recipe exists.
- **Token rename (`just init`, `Justfile:60-74`):** token = literal `modernpackage`. `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'` (Linux `:63`) / `sed -i ''` (macOS `:66`). Only git-tracked files seen — so injected files must be staged first via `_stage_injected_files` `git add -A` (`main.py:928-946`). Version reset: `sed ... '0.0.1' modernpackage/__init__.py` (`:68`; `_RESET_VERSION='0.0.1'` at `main.py:677`). Dir rename `mv modernpackage {{package_name}}` (`:69`). Then `rm -fr .git/ .venv`, `git init -b main`, `git add .`, initial commit (`:70-73`). Invoked from `main.py:1072-1090` via `Popen(cwd=new_package_path)` with `module_name = normalize_module_name(package_name)`. Stubs keep the token: `_TEST_MAIN_STUB` `from modernpackage import __version__` (`main.py:533-539`), `_README_STUB` `# modernpackage` (`:543-547`).
- **Excluded from `check`** (`check: check-format check-lint check-complexity check-typecheck test audit # deadcode`, `Justfile:53`):
  - `deadcode` — commented out in recipe body and definition (`Justfile:44-45`), no rationale given.
  - `migrate`/`makemigration`/`migration-check` — rationale `main.py:576-578`: "need a live database".
  - all `frontend-*` + `generate-client` — rationale `main.py:591-594`: "need Node, which the generated package's CI does not have; mirrors the backend-recipes precedent".

## Cross-Cutting Observations
- **Skip-not-fail discipline** is uniform: missing tools (`shutil.which`), absent compose, and Playwright browser-install failures all `pytest.skip`; only genuine assertion/spec failures fail. `_run(check=False)` underpins this everywhere.
- **`DATABASE_URL` is the single DB-URL seam**: default `@db:5432` for in-compose use (`db.py:23`, `compose.yml:19`); overridden to `@localhost:5432` host-side after `_expose_db_port` (`_scaffold.py:80`); env.py hard-requires it (`env.py:29`).
- **`modernpackage` token threads through everything**: source dir, imports, recipes, stubs, `e2e/status.spec.ts` heading assertion — all rely on `just init` sed rename and on injected files being git-staged first.
- **Two compose-detection blocks are duplicated** verbatim in `_scaffold.py` and `tests/test_e2e.py` (not shared).
- **Recipe-append convention**: both backend and frontend recipe blocks are raw string constants appended without editing the `check` line, keeping Node/DB-dependent recipes out of CI by construction.

## Open Areas
- Generated client functions are not observable — `src/client/index.ts` is a placeholder; the real `@hey-api/client-fetch` output only exists after a live `generate-client` run and is regenerated, not committed.
- The backend/frontend templates contain no Justfiles of their own; recipes exist solely as string constants in `main.py` until appended.
