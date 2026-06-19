# Research Findings

Scope: scaffolding CLI `modernpackage/main.py`, `backend_template/`,
`frontend_template/`, root `pyproject.toml` + `Justfile`, and `tests/`.

## Q1: Full sequence the scaffolder runs to produce a generated package; unconditional vs CLI-gated steps

Entry point `init_new_package` (`modernpackage/main.py:1007-1108`) runs, in order:

1. `module_name = normalize_module_name(package_name)` (`main.py:1020`) → target
   `Path.cwd() / module_name` (`main.py:1021`). **Unconditional.**
2. `_run_preflight_checks(new_package_path)` (`main.py:1023`): package-name valid,
   required tools on PATH, target dir absent, template remote reachable
   (`main.py:855-881`). **Unconditional.**
3. **`dry_run` gate** (`main.py:1025-1037`): if `--dry-run`, print plan and
   `return 0` — no clone, no mutation.
4. `git clone _TEMPLATE_REPOSITORY_URL → new_package_path` via `Popen`
   (`main.py:1039-1052`); non-zero exit → `RuntimeError` (humanized).
   **Unconditional** (when not dry-run).
5. `_write_package_metadata(...)` (`main.py:1054-1061`) — placeholder
   replacements in cloned `pyproject.toml`. **Unconditional.**
6. `_strip_scaffolding(new_package_path)` (`main.py:1063`). **Unconditional.**
7. **`if backend or fullstack:` gate** → `_inject_templates(new_package_path,
   fullstack=fullstack)` (`main.py:1065-1066`). Gated on `--backend`/`--fullstack`.
8. `just init module_name` via `Popen` (`main.py:1068-1087`); does the
   `modernpackage`→`module_name` sed rename, version reset, `mv`, fresh
   `git init`/`add`/`commit` (`Justfile:60-74`). **Unconditional.**
9. `just check` via `Popen` (`main.py:1089-1096`); exit 0 → print summary/next
   steps `return 0`, else `return 1` (`main.py:1098-1108`). **Unconditional.**

`_inject_templates` (`main.py:979-989`): always `_add_backend`; `_add_frontend`
only if `fullstack`; then `_stage_injected_files` (`git add -A`). The "commit"
is `just init`'s single commit (`Justfile:72-73`) over the already-mutated tree.

## Q2: What is removed before a clone becomes a generated package; where the list lives; behavior on absent paths

- Removal list: `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:519-526`):
  `modernpackage/main.py`, `tests/test_e2e.py`, `docs`, `BACKLOG.md`,
  `backend_template`, `frontend_template`.
- Applied by `_strip_scaffolding` (`main.py:640-657`): loops the tuple; dirs →
  `shutil.rmtree(target, ignore_errors=True)`, files → `target.unlink(missing_ok=True)`
  (`main.py:649-654`). **Absent paths are tolerated** (no raise).
- After deletion it writes stubs: `tests/test_main.py` = `_TEST_MAIN_STUB`
  (`main.py:533-539,655`), `README.md` = `_README_STUB` (`main.py:543-547,656`),
  and `_remove_project_scripts(pyproject.toml)` (`main.py:617-637,657`) deletes
  the `[project.scripts]` table (no-op if table/file absent, `main.py:625-632`).
- `backend_template`/`frontend_template` are **always stripped** from the clone
  even with flags; `_add_backend`/`_add_frontend` re-inject from the installed/
  source package path, not from the clone (`main.py:514-518,552-561`).
- Test coverage: `test_strip_scaffolding_tolerates_absent_paths`
  (`test_main.py:1342-1349`), `test_strip_scaffolding_removes_backend_template`
  (`test_main.py:1643-1648`).

## Q3: How `--backend`/`--fastapi` and `--fullstack`/`--reactjs` change the package; what is added and its origin

Flags defined `main.py:363-376`: `--backend`/`--fastapi` and
`--fullstack`/`--reactjs`, both `store_true` default `False`. `--fullstack` is a
superset (backend always injected; `_inject_templates` guard `main.py:986-988`).

**`_add_backend` (`main.py:992-1005`):**
- `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)`
  merges `backend_template/` into the clone. Origin `_BACKEND_TEMPLATE_DIR =
  <pkg parent>/backend_template` (`main.py:552-554`). Files: `modernpackage/app.py`,
  `db.py`, `health.py`; `tests/test_app.py`; `alembic.ini`, `compose.yml`,
  `Containerfile`, `.dockerignore`; `migrations/env.py`, `script.py.mako`,
  `versions/.gitkeep` (tree listed via `find`). App imports FastAPI/SQLAlchemy
  async/asyncpg (`backend_template/modernpackage/app.py:8-11`, `db.py:11-23`,
  `health.py:8-13`).
- `_append_backend_dependencies` (`main.py:884-906`): replaces
  `dependencies = []` with `_BACKEND_DEPENDENCIES` = `fastapi>=0.115`,
  `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `alembic>=1.14`, `uvicorn>=0.34`
  (`main.py:565-571`); prepends `_BACKEND_DEV_DEPENDENCIES` = `httpx`
  (`main.py:574`) into the `dev` group.
- `_append_backend_recipes` (`main.py:909-922`): appends `_BACKEND_RECIPES`
  (`main.py:579-588`): `migrate: sync`, `makemigration message: sync`,
  `migration-check: sync` (NOT added to `check` chain).

**`_add_frontend` (`main.py:962-976`):**
- `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend',
  dirs_exist_ok=True)` (`main.py:973-975`); origin `_FRONTEND_TEMPLATE_DIR`
  (`main.py:559-561`). Tree: `package.json`, `vite.config.ts`, `eslint.config.js`,
  `index.html`, `openapi-ts.config.ts`, `openapi.json`, `tsconfig*.json`,
  `src/{App.tsx,App.test.tsx,main.tsx,setupTests.ts,vite-env.d.ts,client/index.ts}`.
- `_append_frontend_recipes` (`main.py:946-959`): appends `_FRONTEND_RECIPES`
  (`main.py:595-614`): `frontend-install`, `frontend-build`, `frontend-test`,
  `frontend-lint`, `generate-client`, `frontend-check`.
- **Adds NO Python deps and spawns NO subprocess** at scaffold time
  (`main.py:962-971`; asserted `test_add_frontend_no_npm_or_subprocess`
  `test_main.py:1751-1754`). Frontend npm deps live in
  `frontend_template/package.json` (React 19, `@hey-api/client-fetch`, Vite 8,
  Vitest, etc.).

Dry-run plan announces these: `add FastAPI backend...` if `backend or fullstack`,
`add React frontend...` if `fullstack` (`main.py:723-728`).

## Q4: Where backend/frontend names and dependencies are declared or referenced

- **Root `pyproject.toml`**: `dependencies = []` (`pyproject.toml:18`) — no
  backend/frontend runtime deps in the scaffolder itself. References templates
  only as build data: `[tool.hatch.build] include` lists `backend_template/**`,
  `frontend_template/**` (`pyproject.toml:51`); `norecursedirs` excludes both
  (`pyproject.toml:41`); per-file ruff ignores for `backend_template/**`,
  `frontend_template/**`, `backend_template/tests/*`, `backend_template/migrations/*`
  (`pyproject.toml:78-81`).
- **Root `Justfile`**: only `check-backend-template: sync → ruff check
  backend_template` (`Justfile:76-77`). No FastAPI/React deps. The backend/frontend
  recipe text is in `main.py` constants, not the root Justfile.
- **`modernpackage/` modules**: only `main.py` mentions these names — as the
  injection constants/templated literals (`main.py:565-614`); `__init__.py` does
  not. (Grep: only `modernpackage/main.py` matches.)
- **`README.md`**: documents both flags and dep lists at lines 20-21, 87-98,
  212-239, 301-321 (FastAPI/SQLAlchemy/asyncpg/Alembic/uvicorn; React 19/Vite 8/
  Vitest 4.1/Testing Library).
- **`docs/`** describe the features: `docs/fastapi_backend.md`,
  `docs/reactjs_frontend.md`, `docs/containerization.md`, `docs/architecture.md`,
  `docs/overview.md`, `docs/invocation.md` (matched by grep). Note: `docs/` is in
  `_SCAFFOLDING_PATHS_TO_DELETE` so it never reaches a generated package.
- **Template trees themselves** declare the actual deps:
  `backend_template/modernpackage/*.py` import `fastapi`/`sqlalchemy`/`asyncpg`;
  `frontend_template/package.json` declares React/Vite/Vitest/etc.

## Q5: What the tests assert about generated-package contents; no-flag vs --backend / --fullstack

`tests/test_e2e.py` has **two** e2e tests (file is 177 lines; no fullstack e2e):

- **No-flag** `test_scaffolded_package_passes_check` (`test_e2e.py:53-117`):
  clones local repo, `_write_package_metadata` + `_strip_scaffolding`, `just init`,
  `just check`. Asserts metadata applied (`test_e2e.py:97-105`); scaffolding
  removed: no `main.py`, no `tests/test_e2e.py`, no `docs`, no `BACKLOG.md`, no
  `[project.scripts]`, **`not (destination/'backend_template').exists()`**
  (`test_e2e.py:108-114`); stub has `0.0.1` (`test_e2e.py:116-117`).
- **`--backend`** `test_scaffolded_backend_package_passes_check`
  (`test_e2e.py:120-177`): adds `main._add_backend` + `git add -A`
  (`test_e2e.py:141-144`). Asserts injected sources exist (`app.py`, `health.py`,
  `'/readyz'`, token fully renamed) `test_e2e.py:153-159`; Justfile gains
  `migrate: sync`/`makemigration` `test_e2e.py:164-166`; `migrations/env.py`,
  `alembic.ini`, `Containerfile`, `.dockerignore`, `compose.yml` (with
  `service_completed_successfully`, `migrate:`) `test_e2e.py:167-176`.

`tests/test_main.py` (mocked) distinguishes flags:
- No-flag: `init_new_package('mypackage')` → exactly 3 `Popen` calls (clone, just
  init, just check) (`test_main.py:296-307,723`).
- `--backend`: `_add_backend` invoked once (`test_main.py:1592-1603`); 4 `Popen`
  calls incl. `git add -A` (`test_main.py:1651-1666`).
- `--fullstack`: `_add_backend` **and** `_add_frontend` both called once
  (`test_main.py:1773-1786`); 4 `Popen` calls (`test_main.py:1789-1805`).
- backend-only does **not** call `_add_frontend` (`test_main.py:1808-1820`).
- `_add_frontend` adds frontend files + recipes but leaves `pyproject.toml`
  byte-identical (`test_main.py:1735-1748`).

## Q6: How deps/recipes are appended; what the source repo's pyproject/Justfile contain by default

- **Dependency append** `_append_backend_dependencies` (`main.py:884-906`):
  string-replace `dependencies = []\n` → `dependencies = [\n<runtime>]\n`
  (`main.py:899-903`); `dev = [\n` → `dev = [\n<dev>` to prepend `httpx`
  (`main.py:904-905`). Missing file → notice, no raise (`main.py:892-898`).
- **Recipe append**: `_append_backend_recipes` / `_append_frontend_recipes`
  read the Justfile and write `content + _BACKEND_RECIPES`/`_FRONTEND_RECIPES`
  (`main.py:909-922`, `946-959`). Pure append; missing file → notice, no raise.
- **Source `pyproject.toml` defaults**: name `modernpackage`; placeholder author
  `Name Surname`/`email@example.com` (`pyproject.toml:3-5`); description literal
  (`:6`); `requires-python ">= 3.14"`; MIT trove classifier (`:11`);
  `dynamic=["version"]`; **`dependencies = []`** (`:18`); `[project.scripts]`
  `modernpackage`/`mp` (`:23-25`); `[dependency-groups] dev` = ruff, mypy,
  pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, `vupi>=0.0.7`
  (`:27-37`); pytest `--cov-fail-under=95.0 -m 'not e2e'` (`:40`); hatch build
  include/exclude (`:50-52`); gitlab uv index (`:102-104`).
- **Source `Justfile` defaults**: `lifecycle`, `vision`, `sync`, `compile`,
  `test`, `test-e2e`, `format`, `lint`, `typecheck`, `check-*`, `audit`, `fix`,
  `check` chain (`Justfile:53`), `publish`, `init` (rename/reset/commit,
  `:60-74`), `check-backend-template` (`:76-77`), `lock`. No FastAPI/React deps.

## Cross-Cutting Observations

- Placeholder-driven mutation: every injection is a targeted `str.replace` on a
  known literal (`dependencies = []`, `dev = [`, `readme = "README.md"`,
  `Name Surname`, etc.) — `_write_package_metadata` (`main.py:446-511`),
  `_append_backend_dependencies` (`main.py:899-905`).
- The literal token `modernpackage` is deliberately retained in stubs and
  injected files so `just init`'s sed rewrites them (`main.py:528-547,996-998`;
  `Justfile:62-67`).
- Graceful boundary degradation: file-absent paths print a `[stderr]` notice and
  return rather than raise (`main.py:467-472,892-898,914-921,952-958`).
- Backend/frontend recipes are intentionally excluded from the `check` chain
  (need DB/Node) (`main.py:576-578,591-594`).

## Open Areas

- No `--fullstack` e2e test exists; fullstack injection is only verified via
  mocked unit tests (`test_main.py:1773-1820`) and `_add_frontend` unit tests
  (`test_main.py:1735-1766`).
- Precedence when both `--backend` and `--fullstack` are passed is documented in
  `README.md:237` ("fullstack takes precedence") and follows from the
  `if backend or fullstack` / `if fullstack` guards (`main.py:1065,987`); no
  dedicated test asserts the combined-flag case.
