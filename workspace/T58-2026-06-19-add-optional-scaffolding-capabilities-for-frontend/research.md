# Research Findings

Repo: `/home/niekas/tools/modernpackage`. CLI lives in `modernpackage/main.py`
(1135 lines, single module). All `file:line` refs below are relative to repo root.

## Q1: CLI option parsing and flow into `init_new_package`

### Findings
- `parse_args()` builds an `ArgumentParser` (`main.py:347-438`). Options:
  `-v/--version` and `--dry-run` (store_true, `main.py:350-362`); scaffolding
  flags `--backend`/`--fastapi` (`main.py:363-369`) and `--fullstack`/`--reactjs`
  (`main.py:370-376`), both store_true; positional optional `package_name`
  (`nargs='?'`, `type=validate_package_name`, `main.py:377-382`); metadata flags
  `--author-name`, `--description`, `--author-email` (`type=validate_author_email`),
  `--license`, `--repository-url` (`type=validate_repository_url`), all
  `default=None` (`main.py:383-429`).
- After `parser.parse_args()`, metadata defaults are filled in-place by
  `_resolve_metadata_defaults(arguments, _load_config_file())` (`main.py:430-431`),
  then `author_email`/`repository_url` re-validated via `_validated_or_error`
  (`main.py:432-437`).
- Precedence per field: flag > env var > git config (author name/email only) >
  config.toml > None. Encoded in `_METADATA_FIELDS` (`main.py:148-158`) and applied
  by `_resolve_metadata_defaults` (`main.py:310-330`), which only fills attrs still
  `None`. `git_key=None` for description/license/repository_url disables their git
  source (`main.py:152-157`).
- `main()` (`main.py:1111-1135`): if `--version`, print and return; elif
  `package_name`, call `init_new_package(...)` threading every parsed value as a
  keyword arg (`main.py:1120-1130`), wrapping `RuntimeError` → stderr + exit 1.
- `init_new_package` signature mirrors the flags: `author_name`, `author_email`,
  `description`, `package_license`, `repository_url`, `dry_run`, `backend`,
  `fullstack` (`main.py:1007-1018`). Note: arg name is `package_license` (CLI
  `--license` maps via `package_license=parsed_args.license`, `main.py:1124`).

## Q2: End-to-end sequence of `init_new_package`

### Findings
Order (`main.py:1007-1108`):
1. `module_name = normalize_module_name(package_name)`; target =
   `Path.cwd() / module_name` (`main.py:1020-1021`).
2. `_run_preflight_checks(target)` (`main.py:1023`) — prints checklist, runs in
   order: package name valid, required tools on PATH (`git`, `just`, `uv`), target
   dir available, template remote reachable (`main.py:855-881`). Any failure raises
   `RuntimeError` → aborts before clone.
3. If `dry_run`: print plan and `return 0` (no subprocess, `main.py:1025-1037`).
4. `git clone _TEMPLATE_REPOSITORY_URL target` via `Popen` (`main.py:1039-1052`);
   non-zero exit → `humanize_git_clone_error` friendly message + raise.
5. `_write_package_metadata(...)` — TOML placeholder substitutions
   (`main.py:1054-1061`).
6. `_strip_scaffolding(target)` (`main.py:1063`).
7. If `backend or fullstack`: `_inject_templates(target, fullstack=fullstack)`
   (`main.py:1065-1066`).
8. `just init module_name` via `Popen` cwd=target (`main.py:1068-1087`); missing
   `just` → friendly `RuntimeError`; non-zero exit → raise.
9. `just check` via `Popen` cwd=target (`main.py:1089-1096`). Exit 0 → print
   "passed", init summary, next-steps, `return 0` (`main.py:1098-1102`); else print
   failure to stderr, `return 1` (`main.py:1103-1108`).

`just init` (`Justfile:60-74`): `git grep -l 'modernpackage' | xargs sed` rename,
version reset to `0.0.1` in `__init__.py` (`Justfile:68`), `mv modernpackage
<name>`, `rm -fr .git .venv`, `git init`, `git add`, single commit.

## Q3: What `_strip_scaffolding` deletes / retains

### Findings
- `_strip_scaffolding(package_path)` (`main.py:640-657`): loops
  `_SCAFFOLDING_PATHS_TO_DELETE`, rmtree dirs / unlink files (missing tolerated),
  then writes two stubs and removes `[project.scripts]`.
- Always-deleted paths `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:519-526`):
  `modernpackage/main.py`, `tests/test_e2e.py`, `docs`, `BACKLOG.md`,
  `backend_template`, `frontend_template`.
- **Both template trees are always removed**, then conditionally re-injected:
  `_add_backend` if `--backend`, `_add_frontend` if `--fullstack`
  (comments `main.py:517-526`). Guarantees no-flag output identical to pre-flag.
- Retained/created: `tests/test_main.py` overwritten with `_TEST_MAIN_STUB`
  (`main.py:533-539`, written `main.py:655`) — keeps pytest collection non-empty +
  coverage ≥95%; `README.md` overwritten with `_README_STUB` (`main.py:543-547`,
  `main.py:656`). Both retain literal `modernpackage` token for the rename sed.
- `_remove_project_scripts(pyproject.toml)` (`main.py:617-637`) deletes the
  `[project.scripts]` table (header → next `[`), leaving other tables intact; no-op
  if table/file absent. Called at `main.py:657`.
- `modernpackage/__init__.py` is **not** deleted (kept; holds `__version__`).

## Q4: How templates are copied and wired

### Findings
- Template dirs resolved relative to the module so they work from source checkout
  or installed wheel: `_BACKEND_TEMPLATE_DIR` / `_FRONTEND_TEMPLATE_DIR` =
  `Path(__file__).resolve().parent.parent / '<name>'` (`main.py:552-561`).
- `_inject_templates(package_path, fullstack)` (`main.py:979-989`): always
  `_add_backend`, then `_add_frontend` if fullstack, then `_stage_injected_files`.
- `_add_backend` (`main.py:992-1005`): `shutil.copytree(_BACKEND_TEMPLATE_DIR,
  package_path, dirs_exist_ok=True)` (merges into existing `modernpackage/`,
  `tests/`), then `_append_backend_dependencies(pyproject)` + `_append_backend_recipes(Justfile)`.
- `_append_backend_dependencies` (`main.py:884-906`): replaces `dependencies = []`
  with `_BACKEND_DEPENDENCIES` (`fastapi>=0.115`, `sqlalchemy[asyncio]>=2.0`,
  `asyncpg>=0.30`, `alembic>=1.14`, `uvicorn>=0.34`, `main.py:565-571`); prepends
  `httpx` (`_BACKEND_DEV_DEPENDENCIES`, `main.py:574`) to the `dev` group.
- `_append_backend_recipes` (`main.py:909-922`): appends `_BACKEND_RECIPES`
  (`migrate`, `makemigration`, `migration-check`, each `: sync`, `main.py:579-588`)
  to Justfile. **Not** added to `check` chain (need live DB).
- `_add_frontend` (`main.py:962-976`): copytree into `package_path/'frontend'`
  (isolated subdir), then `_append_frontend_recipes`. Adds **no** Python deps,
  spawns **no** subprocess (Node tooling deferred to user). `_FRONTEND_RECIPES`
  (`main.py:595-614`): `frontend-install`, `frontend-build`, `frontend-test`,
  `frontend-lint`, `generate-client`, `frontend-check` (all `cd frontend &&`, no
  `: sync`); not in `check` chain.
- `_stage_injected_files` (`main.py:925-944`): `git add -A` in clone so injected
  untracked files become visible to `just init`'s `git grep` rename sed
  (`Justfile:62-67`); non-zero exit raises.
- Coordination with `just init`: all injected files carry literal `modernpackage`
  token; staging before `just init` lets the single rename sed + initial commit
  capture them (docstrings `main.py:996-1000`, `968-971`).

## Q5: Structure/content of `backend_template/` and `frontend_template/`

### Findings — backend_template (tree: `find backend_template`)
- `modernpackage/app.py`: `lifespan` async ctx mgr stores engine +
  `async_sessionmaker(expire_on_commit=False)` on `app.state`, disposes on shutdown
  (`app.py:18-26`); `create_app()` → `FastAPI(lifespan=...)` + `include_router(health_router)`
  (`app.py:29-33`). Used by uvicorn `--factory`.
- `modernpackage/db.py`: `_DEFAULT_DATABASE_URL =
  postgresql+asyncpg://appuser:secret@db:5432/appdb` (`db.py:23`); `_NAMING_CONVENTION`
  (`db.py:26-32`); `Base(AsyncAttrs, DeclarativeBase)` with naming-convention metadata
  (`db.py:35-38`); `database_url()` reads `$DATABASE_URL` else default (`db.py:41-43`);
  `create_engine()` = `create_async_engine` (lazy, `db.py:46-48`); `get_db(request)`
  async-gen dependency from `app.state.sessionmaker` (`db.py:51-57`); `DbSessionDep`
  alias (`db.py:60`).
- `modernpackage/health.py`: `router` (`health.py:15`); `database_ready` runs
  `SELECT 1` under `asyncio.timeout(2.0)`, returns bool (`health.py:20-29`); `GET
  /livez` always 200 `{"status":"pass"}` (`health.py:32-35`); `GET /readyz` 200/pass
  or 503/fail JSONResponse (`health.py:38-48`).
- Alembic: `migrations/env.py` async-only — `target_metadata = Base.metadata`
  (`env.py:12`), overrides url from `os.environ['DATABASE_URL']` (no fallback),
  `NullPool`, `run_sync(do_run_migrations)` with `compare_type=True` (`env.py:15-36`);
  `script.py.mako` standard template; `versions/` empty (`.gitkeep`). `alembic.ini`:
  `script_location=migrations`, `prepend_sys_path=.`, **no** `sqlalchemy.url`
  (injected from env).
- Container: `Containerfile` two-stage `python:3.14-slim`, uv from
  `ghcr.io/astral-sh/uv:0.5`, `UV_COMPILE_BYTECODE/LINK_MODE/PYTHON_DOWNLOADS` set,
  split `uv sync` layers, `HEALTHCHECK` → `/readyz`, CMD
  `uvicorn modernpackage.app:create_app --factory --host 0.0.0.0 --port 8000`
  (`Containerfile:2-26`). `compose.yml` 3 services: `db` (postgres:17, pg_isready
  healthcheck, `pgdata` volume), `migrate` (one-shot `alembic upgrade head`,
  depends_on db service_healthy), `app` (depends_on db service_healthy + migrate
  service_completed_successfully, port `127.0.0.1:8000:8000`). `.dockerignore`: 6
  entries (`.venv`, `.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache`).
- `tests/test_app.py`: 6 tests — livez pass, readyz pass/fail via
  `dependency_overrides[database_ready]`, `database_ready` true/false via
  `_FakeEngine`/`_FakeConnection`, `get_db` yields session (`test_app.py:45-94`).

### Findings — frontend_template (tree: `find frontend_template`)
- `package.json`: `name:"modernpackage"`, scripts `dev`(vite),
  `build`(`tsc --noEmit && vite build`), `preview`, `typecheck`, `lint`(eslint),
  `format`/`format:check`(prettier), `test`(`vitest run`), `test:watch`,
  `generate-client`(`openapi-ts`) (`package.json:6-17`). Deps: react@^19,
  react-dom@^19, `@hey-api/client-fetch@^0.10`; devDeps vite@^8, vitest@^4.1,
  jsdom, typescript@^5.7, eslint@^10, prettier, `@hey-api/openapi-ts@^0.64`,
  `@tanstack/react-query@^5`, testing-library (`package.json:18-43`).
- `vite.config.ts`: react plugin; `server.proxy` `/api` → `http://localhost:8000`;
  `test` block jsdom/globals/`setupFiles ./src/setupTests.ts`/coverage v8
  (`vite.config.ts:1-16`). (No separate `vitest.config.ts` — vitest config lives
  in vite.config.ts.)
- API client: `openapi-ts.config.ts` input `http://localhost:8000/openapi.json`,
  output `src/client`, plugin `@hey-api/client-fetch` (lines 4-6). `openapi.json` is
  a committed snapshot, title `modernpackage`, paths `/livez` + `/readyz`.
  `src/client/index.ts` is a **placeholder** (comment + two `Record<string,unknown>`
  type aliases `LivezResponse`/`ReadyzResponse`), regenerated by `generate-client`.
- App/test: `src/App.tsx` → `<h1>modernpackage</h1>`; `src/App.test.tsx` 1 test
  asserts heading name `'modernpackage'`; `src/main.tsx` React 19 `createRoot` +
  StrictMode; `src/setupTests.ts` imports `@testing-library/jest-dom`.
- `eslint.config.js` flat config, ignores `dist`, `src/client`; three tsconfigs
  (root references + `tsconfig.app.json` for `src/` + `tsconfig.node.json` for
  vite config); `index.html` title/`#root`/main.tsx script.
- `modernpackage` token in package.json:2, openapi.json:3, index.html:6,
  App.tsx:2, App.test.tsx:8.

## Q6: How scaffolding is tested

### Findings
- `tests/test_main.py`: 148 `test_` functions (`test_main.py:44-1839`). Mocks via
  `unittest.mock.patch`/`MagicMock` (`test_main.py:6`); subprocess seam mocked as
  `patch('modernpackage.main.Popen')` + `patch('modernpackage.main.run')`;
  `popen_mock.side_effect=[...]` for per-call return codes.
  Groups: parse_args/flags/aliases/env precedence, metadata resolution, validators,
  `_write_package_metadata`, `_strip_scaffolding`/`_remove_project_scripts`
  (incl. `backend_template` removal, `test_main.py:1661`), backend injection
  (`test_init_new_package_invokes_add_backend_when_flag_set`:1592,
  `test_add_backend_copies_template_and_appends_deps`:1629,
  `test_init_new_package_backend_stages_then_inits`:1669 asserts 4 Popen calls,
  2nd = `git add -A`), frontend injection (`test_add_frontend_copies_template_and_appends_recipes`:1753,
  `test_add_frontend_no_npm_or_subprocess`:1769 via `inspect.getsource`,
  `test_init_new_package_invokes_add_frontend_when_fullstack`:1791,
  `test_init_new_package_backend_only_does_not_add_frontend`:1826), dry-run,
  preflight checks.
- `tests/test_e2e.py`: 4 `@pytest.mark.e2e` tests; run via `just test-e2e`
  (`Justfile:17-18`, `pytest -m e2e --no-cov`). Actually clone repo, strip, inject,
  run real `just init` + `just check`. Tests: plain
  (`test_scaffolded_package_passes_check`:70), backend
  (`test_scaffolded_backend_package_passes_check`:137 — checks app/health renamed,
  recipes, alembic, Containerfile/compose), negative
  (`test_scaffolded_package_has_no_backend_or_frontend`:196 — asserts no
  backend/frontend artifacts), fullstack
  (`test_scaffolded_fullstack_package_passes_check`:272 — `_inject_templates(...,
  fullstack=True)`, then `just frontend-install` + `just frontend-test`, asserts
  Vitest output, token renamed, `check:` excludes `frontend-` recipes). Tools
  missing → `pytest.skip`; `npm` required for fullstack.
- Backend template own tests: `backend_template/tests/test_app.py` (6 tests, run by
  the scaffolded package's pytest). Root `Justfile:76-77`
  `check-backend-template` runs **lint only** (`uv run ruff check backend_template`);
  no recipe runs the template's pytest in the source repo.
- Frontend template own tests: `package.json` `test`=`vitest run`; exercised in e2e
  via `just frontend-test` (`test_e2e.py` fullstack case). `frontend-test` is **not**
  in the root `check` chain.

## Q7: Guidance in `docs/`

### Findings
- `docs/fastapi_backend.md`: app factory + `@asynccontextmanager` lifespan with
  engine/sessionmaker on `app.state` (lines 52-72); `Annotated[T, Depends]` DI alias
  (76-94); async SQLAlchemy 2.0 `postgresql+asyncpg`, `async_sessionmaker(expire_on_commit=False)`
  mandatory (145-153), `Base(AsyncAttrs, DeclarativeBase)`; Alembic async template,
  url from `$DATABASE_URL`, `NullPool`, `MetaData(naming_convention)` (222-299),
  recipes `just migrate/makemigration/migration-check` (302-311), migrate as
  one-shot compose service, never at app startup (354-365); health: `/livez`
  trivial 200, `/readyz` `SELECT 1` 503-on-fail under `asyncio.timeout(2.0)`,
  `/healthz` deprecated (487-524).
- `docs/reactjs_frontend.md`: Vite 8 / React 19, three-tsconfig split, strict mode,
  `moduleResolution:bundler` (47-63); `/api` proxy (86-103); `build` doesn't
  typecheck — separate `tsc --noEmit` gate (400); API sync chain Pydantic → OpenAPI
  3.1 `/openapi.json` → TS via `@hey-api/openapi-ts` (124-159), config input live URL
  or committed `./openapi.json`, output `src/client`, script
  `"generate-client":"openapi-ts"` (143-154), CI drift check
  `generate-client && git diff --exit-code src/client` (163-169); note current
  backend has no response_models so generated types minimal (173-177); Vitest 4.1
  jsdom/globals + RTL + MSW (204-248); `npm ci` in CI (431).
- `docs/containerization.md`: uv via `COPY --from=ghcr.io/astral-sh/uv:0.5`
  pinned, never pip (16-19); `python:3.x-slim`, no Alpine (22-25); multi-stage,
  split layer caching with bind-mounted lock/pyproject (27-42); build env
  `UV_COMPILE_BYTECODE/LINK_MODE/PYTHON_DOWNLOADS` (49-55); `.dockerignore` ≥`.venv`
  (42-46); secrets via `--mount=type=secret`/compose `secrets:` (219-238); non-root
  `appuser` recommended (193-197); stdlib HEALTHCHECK, `/health` 200/503 (249-256);
  compose: omit `version:`, `condition: service_healthy` /
  `service_completed_successfully`, `127.0.0.1` ports in dev, FQ image names
  (274-320); `Containerfile` name (Podman), OCI default (133,173-175).
- `docs/invocation.md` / `docs/overview.md` / `docs/specification.md`: flag aliases
  `--backend`=`--fastapi` (invocation.md:149-153), `--fullstack`=`--reactjs`, a
  strict superset of `--backend` (209-231); flags shown in `--dry-run`; backend
  injects app/db/health/tests/migrations/alembic.ini/Containerfile/compose/.dockerignore
  + deps + 3 recipes; fullstack adds `frontend/` + 6 recipes, **zero** Python deps,
  not in `check` (invocation.md:229); no-flag output byte-identical
  (specification.md:70-71).
- `docs/architecture.md` / `docs/data_flows.md`: templates shipped as package data
  via `[tool.hatch.build] include` (architecture.md:276-332,1426); injection order
  clone → metadata → strip → add_backend → add_frontend → `git add -A` → `just init`
  → `just check` (architecture.md:1251-1291); rename contract relies on literal
  `modernpackage` token + staging; frontend isolated in `frontend/` to avoid Python
  tooling discovery (architecture.md:1122-1123).

## Cross-Cutting Observations
- The literal token `modernpackage` is the universal rename pivot: stubs and both
  templates intentionally keep it so `just init`'s `git grep | sed` rewrites it;
  injected files must be `git add -A`-staged first (`main.py:925-944`, `Justfile:62-67`).
- Graceful boundary degradation pattern: metadata/dep/recipe writers print a
  `[notice]` and return on missing files instead of raising
  (`main.py:465-472`, `891-898`, `914-921`, `952-959`); invariant violations and
  subprocess failures raise `RuntimeError`.
- Backend and frontend recipes are deliberately excluded from the root `check`
  chain (need DB / Node) — comments at `main.py:576-578`, `590-594`.
- `--fullstack` always implies the backend; both code (`if backend or fullstack`,
  `main.py:1065`) and docs treat fullstack as a superset.

## Open Areas
- `src/client/index.ts` ships as a placeholder, not a real generated client
  (`frontend_template/src/client/index.ts:1-4`); the real client is produced only
  when the user runs `generate-client` against a running backend.
- Docs (`docs/containerization.md:193-197`) recommend a non-root `appuser`, but the
  actual `backend_template/Containerfile` as read does not include a `USER` line —
  a convention stated in docs that the current template does not yet implement.
- No source-repo Justfile recipe runs the backend template's own pytest;
  `check-backend-template` is lint-only (`Justfile:76-77`). Template tests run only
  inside a scaffolded package (e2e fullstack/backend cases).
