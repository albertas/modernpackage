# Research Findings

Scope: `modernpackage/main.py` (CLI scaffolder), `backend_template/`, `docs/`
(`fastapi_backend.md`, `reactjs_frontend.md`), `Justfile`, `pyproject.toml`,
`tests/`. The `--backend`/`--fastapi` feature is the existing model the questions
probe; there is **no** frontend template or Node wiring in the repo today.

## Q1: How an optional store-true CLI flag with an alias is defined, parsed, and threaded

### Findings
- Defined in `parse_args` as a single `add_argument` with two option strings (alias) plus `action='store_true'`, `default=False`: `modernpackage/main.py:363-369` (`'--backend', '--fastapi'`). argparse stores both option strings to the same `dest` (`backend`), so `--fastapi` sets `backend=True`.
- Other store_true flags follow the same shape: `--version`/`-v` `main.py:350-356`, `--dry-run` `main.py:357-362`.
- Threaded: `main()` reads `parsed_args.backend` and passes it as keyword `backend=...` into `init_new_package` (`main.py:1023-1034`, specifically `main.py:1033`).
- `init_new_package` signature declares `backend: bool = False` (`main.py:922`).
- Influence on scaffolding behavior:
  - Dry-run plan: `backend` forwarded to `_print_dry_run_plan`/`_format_dry_run_plan`; when true appends `'  add FastAPI backend (app, migrations, container, recipes)'` (`main.py:681-682`, plan call `main.py:930-941`).
  - Real run: `if backend:` calls `_add_backend(...)` then `_stage_injected_files(...)` (`main.py:969-971`), placed after `_strip_scaffolding` and before `just init`.
- Default-absence: `default=False` means the no-flag path skips both the dry-run line and the injection block.

## Q2: How the existing template-injection path works end-to-end

### Findings
- Template tree located relative to the installed/source module: `_BACKEND_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'backend_template'` (`main.py:544-546`). Shipped in wheels via `[tool.hatch.build] include = [..., "backend_template/**"]` (`pyproject.toml:50-51`).
- Copy: `_add_backend` does `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` merging into the clone's existing `modernpackage/` and `tests/` (`main.py:898-908`).
- The clone always contains `backend_template/` (it is part of the repo being cloned), but `_strip_scaffolding` unconditionally deletes it via `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:512-518`, deletion loop `main.py:608-613`). So the no-flag scaffold never includes it; `_add_backend` re-injects from the installed package path only when `--backend` is set (comment `main.py:509-511`).
- Staging for `just init`: `_stage_injected_files` runs `git add -A` in the clone (`main.py:877-895`). Needed because copied files are untracked, and `just init`'s rename `git grep -l 'modernpackage' | xargs sed` only rewrites tracked files (`Justfile:62-67`). Injected files keep the literal `modernpackage` token so the sed rewrites their imports (`main.py:904-906`).
- Ordering in `init_new_package`: clone → `_write_package_metadata` → `_strip_scaffolding` → (if backend) `_add_backend` + `_stage_injected_files` → `just init` → `just check` (`main.py:943-1013`).
- Conditional + absent-by-default: gated solely by `if backend:` (`main.py:969`); flag defaults False (`main.py:368`); template always stripped from the default clone (`main.py:517`).

## Q3: How extra deps, Justfile recipes, and dry-run lines are added under the flag

### Findings
- Runtime deps: `_BACKEND_DEPENDENCIES` tuple — `fastapi>=0.115`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `alembic>=1.14`, `uvicorn>=0.34` (`main.py:550-556`). Injected by `_append_backend_dependencies` replacing `dependencies = []\n` with the populated array (`main.py:836-855`).
- Dev deps: `_BACKEND_DEV_DEPENDENCIES = ('httpx',)` (`main.py:559`); prepended into the `dev = [` group via `content.replace('dev = [\n', f'dev = [\n{dev}')` (`main.py:856-857`).
- Both replacements happen only inside `_add_backend` (`main.py:909`), invoked only when `backend` is true. Missing file → notice, no raise (`main.py:843-850`).
- Justfile recipes: `_BACKEND_RECIPES` multi-line string with `migrate`, `makemigration`, `migration-check` (each `: sync`), appended by `_append_backend_recipes` (`main.py:564-573`, append `main.py:861-874`, call `main.py:910`). Comment notes they are deliberately NOT added to the `check` chain because they need a live DB (`main.py:561-563`).
- Dry-run line: single appended line in `_format_dry_run_plan` guarded by `if backend:` (`main.py:681-682`).
- Kept out of default scaffold: all additions live behind `if backend:` (`main.py:969`); without the flag, `dependencies = []` and the Justfile/dry-run plan stay untouched.

## Q4: What `backend_template/` provides at runtime + test-suite/coverage shape

### Findings
- App factory: `create_app() -> FastAPI` builds `FastAPI(lifespan=lifespan)` and `app.include_router(health_router)`, returns app (`backend_template/modernpackage/app.py:29-32`). No CORS/auth/exception middleware wired.
- Lifespan: `@asynccontextmanager` creates engine via `create_engine()` and `async_sessionmaker(expire_on_commit=False)`, stores on `app.state.engine`/`app.state.sessionmaker`, disposes engine in `finally` (`app.py:17-26`).
- Container entry: `uvicorn modernpackage.app:create_app --factory --host 0.0.0.0 --port 8000` (`backend_template/Containerfile:26`).
- Health endpoints in `backend_template/modernpackage/health.py` on module `router = APIRouter()` (`health.py:15`):
  - `GET /livez` → `{'status': 'pass'}`, always 200, no DB (`health.py:32-35`).
  - `GET /readyz` → `Depends(database_ready)`; `database_ready` runs `SELECT 1` under `asyncio.timeout(2.0)` against `request.app.state.engine` returning bool (`health.py:17,20-29`). Pass → 200 `{'status':'pass'}` (`health.py:48`); fail → `JSONResponse({'status':'fail'}, status_code=503)` (`health.py:43-46`).
- OpenAPI surface: auto `/docs`, `/redoc`, `/openapi.json` (not disabled); only `/livez`+`/readyz` registered. Endpoints return plain dict/`JSONResponse` (no Pydantic `response_model`), so schema is minimal (`reactjs_frontend.md:174-177`).
- Test suite `backend_template/tests/test_app.py`: 6 tests, no fixtures, no `conftest.py`. Uses `TestClient` as context manager to fire lifespan (`test_app.py:7,45-49`); overrides `app.dependency_overrides[database_ready]` for pass/fail (`test_app.py:52-67`); drives async paths with `asyncio.run` and hand-rolled `_FakeConnection`/`_FakeEngine`/`_request_with_engine` (`test_app.py:17-42,70-94`).
- Coverage relevance: the 6 tests exercise `app.py`, `health.py` (both routes + dependency branches + timeout), and `db.py` (`get_db`, `create_engine`). No `--cov-fail-under` config inside `backend_template/`; the gate lives in the generated package's root pyproject (Q6). Backend template tests are excluded from the scaffolder's own coverage via `norecursedirs = ["backend_template"]` (`pyproject.toml:41`).
- Deps inferred from imports: runtime `fastapi`, `sqlalchemy[asyncio]`, `asyncpg` (URL driver), `alembic`, `uvicorn`; dev `httpx`/`anyio` (TestClient) — matches the injected dep tuples in Q3.

## Q5: What `docs/reactjs_frontend.md` documents (structure, Vite, testing, schema sync, tooling)

### Findings
- Project structure: `index.html` + `src/main.tsx` (`ReactDOM.createRoot`) + `src/App.tsx`, `public/`, `src/assets/`, `src/vite-env.d.ts` (`reactjs_frontend.md:30-34`). Feature-folder layout `features/<name>/{components,hooks,utils,index.ts}`; "features must never import from each other" (`:38-42`). Three tsconfigs: root orchestrator, `tsconfig.app.json`, `tsconfig.node.json` with `strict`, `moduleResolution:"bundler"`, `jsx:"react-jsx"`, `noEmit` (`:46-63`).
- Vite: Vite 8.x on Rolldown, React 19 via `@vitejs/plugin-react` v6 (`:15-17`). Scaffold: `npm create vite@latest my-app -- --template react-ts` then `cd my-app && npm install` (`:19-22`); alt template `react-swc-ts` (`:24`). Dev proxy `server.proxy` maps `/api` → `http://localhost:8000` (`:89-103`). `vite build` → `dist/`; `vite preview` on `:4173` (`:107`). Env vars use `VITE_` prefix (`:67-82`).
- Unit testing: Vitest 4.1.x, Vite-native, config via `mergeConfig` from `vitest/config`, `environment:'jsdom'`, `globals:true`, `setupFiles` (`:197-218`). Libs: React Testing Library 16.3.x, `@testing-library/user-event`, `@testing-library/jest-dom`, MSW 2.14.x (`:222-241`). Coverage `@vitest/coverage-v8` with `test.coverage.thresholds` (`:246-248`). Commands `"test":"vitest run"`, `"test:watch":"vitest"` (`:372-373`).
- Backend API schema sync: chain Pydantic → OpenAPI 3.1 → TS types (`:126-128`). Primary generator `@hey-api/openapi-ts` emitting `types.gen.ts`/`sdk.gen.ts`/`schemas.gen.ts` (+ `@tanstack/react-query` plugin) (`:133-158`); config `input:'http://localhost:8000/openapi.json'`, `output:'src/client'` (`:140-148`). Command `"generate-client":"openapi-ts"` → `npm run generate-client` (`:151-156,374`). CI drift gate: `npm run generate-client` + `git diff --exit-code src/client` (`:162-169`). Alternatives: `openapi-typescript`+`openapi-fetch`, Orval, Kubb, `openapi-generator-cli` (`:187-189`).
- Tooling/quality: full npm scripts block (`:362-376`); ESLint v10 flat config + typescript-eslint v8 + react-hooks/react-refresh (`:381-397`); Prettier 3.8.x + `eslint-config-prettier`; `tsc --noEmit` as a separate typecheck gate (`:399-402`). Alternatives Biome v2.4, Oxlint v1.x.

## Q6: How `just check`/`just init`/generated Justfile+pyproject define quality gates; Node-step mechanisms

### Findings
- `check` aggregates: `check: check-format check-lint check-complexity check-typecheck test audit` (`Justfile:53`). Sub-recipes: `check-format` = `ruff format --check` (`Justfile:29-30`), `check-lint` = `ruff check` (`:32-33`), `check-complexity` = `ruff check --select C901` (`:35-36`), `check-typecheck` = `mypy` (`:38-39`), `test` = `uv run pytest -n "$(nproc...)"` (`:14-15`), `audit` = `pip-audit --skip-editable` (`:41-42`). Every recipe depends on `sync` (`uv sync`, `:8-9`).
- Coverage gate lives in pytest addopts: `--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'` (`pyproject.toml:39-44`). `e2e` marker tests run separately via `test-e2e` `--no-cov` (`Justfile:17-18`).
- `just init` (`Justfile:60-74`): renames `modernpackage`→package name via `git grep -l ... | xargs sed`, resets version to `0.0.1`, `mv modernpackage <name>`, `rm -fr .git/ .venv`, `git init`, `git add .`, single `git commit`.
- The scaffolder runs `just check` in the generated package after `just init` and reports pass/fail (`main.py:994-1013`).
- Non-Python (Node) test/build step: **none exists** in repo. `backend_template` is Python-only; `pyproject.toml`/`Justfile` contain no `npm`/`node`/`vitest` references (verified by grep). The only relevant injection precedent is `_append_backend_recipes` appending Justfile recipes (`main.py:861-874`) — those backend recipes are intentionally NOT chained into `check` (`main.py:561-563`). The reactjs doc proposes (does not implement) mapping frontend gates to `just check` via npm scripts: `prettier --check`/`eslint .`/`tsc --noEmit`/`vitest run`/`npm audit`, run with `npm ci` in CI (`reactjs_frontend.md:359-376,404-417,427-435`).
- `backend_template`-specific repo recipe `check-backend-template` lints the template in the scaffolder repo (`Justfile:76-77`).

## Q7: How CLI behaviors are verified in `tests/` (clone/subprocess seams, injection assertions)

### Findings
- Subprocess seam mocked by patching the imported names on the module: `patch('modernpackage.main.Popen')` and `patch('modernpackage.main.run')` (e.g. `tests/test_main.py:295-301`). `Popen.return_value.communicate.return_value = (b'', b'')` and `.returncode = 0` simulate success.
- Call-count / argument assertions on the ordered subprocess calls: no-flag run expects 3 Popen calls (clone, just init, just check) (`test_main.py:303`, args asserted `:318-339`). Backend run expects 4 (clone, `git add -A`, just init, just check) and asserts the 2nd call is `['git','add','-A']` with `cwd` the clone (`test_main.py:1646-1661`).
- Flag parsing: `patch('sys.argv', [...])` + `parse_args()` — `--backend` and `--fastapi` both assert `result.backend is True`; no flag asserts `False` (`test_main.py:1542-1557`).
- `_strip_scaffolding`/`_add_backend` patched out for orchestration tests (`patch('modernpackage.main._strip_scaffolding')`, `..._add_backend`) to isolate sequencing; ordering asserted via side-effect call log (`test_main.py:342-365`); `_add_backend` invocation asserted `assert_called_once_with(Path.cwd()/'mypackage')` (`test_main.py:1587-1598`).
- Injection verified against a real seeded tree: `_seed_clone(tmp_path)` builds a fake clone (uses repo's real `pyproject.toml`) (`test_main.py:1286-1300`). `test_add_backend_copies_template_and_appends_deps` asserts `app.py`/`health.py`/`test_app.py` copied and `fastapi`/`sqlalchemy[asyncio]`/`httpx` present + valid TOML (`test_main.py:1606-1616`). Recipes asserted by substring on the written Justfile (`test_main.py:1664-1671`). Token-rename invariant simulated: replace `modernpackage`→`newpkg`, assert no leftover token (`test_main.py:1623-1635`). Missing-file graceful paths asserted to not raise (`test_main.py:1619-1620,1674-1675`).
- Dry-run: `_format_dry_run_plan(..., backend=True)` asserts `'add FastAPI backend' in plan`; default omits it (`test_main.py:1560-1584`).
- `parse_args` also tested via `patch('modernpackage.main.ArgumentParser')` for version/metadata flows (`test_main.py:43-48,544-567`). Real-subprocess e2e lives behind the `e2e` marker in `tests/test_e2e.py`.

## Cross-Cutting Observations
- Feature-flag pattern is uniform: a `store_true` flag with alias → keyword threaded into `init_new_package` → gated `if backend:` block doing copytree + targeted `str.replace` injections into `pyproject.toml`/`Justfile` + a dry-run line, all defaulting off (`main.py:363-369,550-573,898-911,969-971`).
- Injection helpers degrade gracefully at the file boundary (FileNotFoundError → stderr notice, no raise) while subprocess steps raise `RuntimeError` on non-zero exit — matches CLAUDE.md error-handling convention (`main.py:843-850,891-895`).
- Token-rename coupling: every injected/stub file must keep the literal `modernpackage` token so `just init`'s `git grep | sed` rewrites it; this requires staging via `git add -A` (`main.py:877-906`, `Justfile:62-67`).
- Coverage gate is a single pytest addopts knob (`--cov-fail-under=95.0`) in the generated package's pyproject, not in templates; `norecursedirs`/per-file-ignores keep `backend_template` out of the scaffolder's own gate (`pyproject.toml:40-41,78-80`).

## Open Areas
- No frontend/reactjs template directory, no Node tooling, and no `--frontend`/`--reactjs`/`--fullstack` flag exist in the repo today. `docs/reactjs_frontend.md` is reference material only; its `just check` mapping (`:404-417`) is documentation, not implemented wiring.
- The mechanism to invoke a non-Python (Node) test/build step from `just check` does not exist; the only precedent for adding gates is appending Justfile recipes (`_append_backend_recipes`), and backend recipes are explicitly excluded from the `check` chain (`main.py:561-563`).
- `backend_template` carries `Containerfile`/`compose.yml`/`alembic.ini`/`migrations/` (containerization + migrations) beyond app/health; no equivalent container/build assets exist for a frontend.
