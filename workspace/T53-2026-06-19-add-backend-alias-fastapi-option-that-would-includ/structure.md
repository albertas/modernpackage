# Structure Outline

## Approach

Add a store-true `--backend`/`--fastapi` flag that threads into `init_new_package`
and triggers a single new `_add_backend(package_path)` step (same slot as
`_strip_scaffolding`, after metadata write, before `just init`). `_add_backend`
copies a committed top-level `backend_template/` tree into the clone with
`shutil.copytree(dirs_exist_ok=True)`, appends backend deps to
`[project.dependencies]`, and a new `git add -A` `Popen` call stages the copied
files so the existing `just init` `git grep`/`sed` rename rewrites their
`modernpackage` tokens. The no-flag path stays byte-for-byte identical. Backend
content (app → migrations → container) grows the template across phases, each
flowing through the same injection mechanism.

---

## Phase 1: CLI flag plumbing + dry-run

Adds the `--backend`/`--fastapi` store-true flag and threads it end-to-end
(parse → `main` → `init_new_package` → dry-run). No injection yet; with the flag
set, `init_new_package` calls a no-op `_add_backend` placeholder so the flow is
provably wired.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `parse_args`: `parser.add_argument('--backend', '--fastapi', action='store_true', default=False)` (mirror `-v/--version`, `main.py:350-356`)
- `init_new_package(package_name, *, ..., backend: bool = False)` — new keyword-only param (`main.py:786-795`)
- `main()`: `init_new_package(..., backend=parsed_args.backend)` (`main.py:890-900`)
- `_format_dry_run_plan(..., backend: bool) -> str` — appends `add FastAPI backend (app, migrations, container, recipes)` line when set (`main.py:599-635`)
- `_add_backend(package_path: Path) -> None` — placeholder (pass) this phase

**Verify**: `just test` passes new tests:
`parse_args(['p', '--fastapi']).backend is True` and `--backend` likewise;
`uv run modernpackage foo --backend --dry-run` stdout contains
`add FastAPI backend`. Without the flag the dry-run output is unchanged
(assert against a captured baseline string).

---

## Phase 2: Injection mechanism + FastAPI app (core slice)

Builds the real `_add_backend`: copy `backend_template/` into the clone, append
backend deps, and stage with `git add -A` before `just init`. The template ships
a working FastAPI app (factory + `lifespan` engine/sessionmaker, async
SQLAlchemy/asyncpg DI, `/livez` + `/readyz`) **and its own tests** so the
generated package still clears `--cov-fail-under=95.0`. This is the first phase
that produces a runnable `--backend` package.

**Files**: `backend_template/modernpackage/{app.py,db.py,health.py}`,
`backend_template/tests/test_app.py`, `modernpackage/main.py`,
`pyproject.toml` (extend `[tool.hatch.build]` include to ship `backend_template/`
as package data, `pyproject.toml:49-51`), `tests/test_main.py`, `tests/test_e2e.py`

**Key changes**:
- `_BACKEND_TEMPLATE_DIR: Path` and `_BACKEND_DEPENDENCIES: tuple[str, ...]` (fastapi, `sqlalchemy[asyncio]`, asyncpg, alembic, uvicorn — lower bounds only) module constants
- `_add_backend(package_path: Path) -> None` — `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` then `_append_backend_dependencies(package_path / 'pyproject.toml')`
- `_append_backend_dependencies(pyproject_path: Path) -> None` — line-surgery append into `[project.dependencies]` (mirror `_remove_project_scripts` style, `main.py:531-551`; missing-file → notice, no raise)
- `init_new_package`: call `_add_backend(package_path)` when `backend`, then a new `git -C <clone> add -A` `Popen` call before `just init` (`main.py:836-841`)
- Template app: `create_app()` with `@asynccontextmanager lifespan`, `get_db` / `DbSessionDep = Annotated[AsyncSession, Depends(get_db)]`, `GET /livez` → 200, `GET /readyz` → `SELECT 1` (200 / 503). All reference the `modernpackage` token where they import the package.

**Verify**: `just test` passes — `_add_backend` on a `_seed_clone(tmp_path)` copies the tree, appends deps, and after a simulated rename no `modernpackage` token remains in injected files (`git grep -l modernpackage` empty); existing `Popen` side_effect sequences updated for the extra `git add -A` call (`test_main.py:378-407`). `just test-e2e` scaffolds `--backend` for real and asserts the generated package's `just check` passes and `<module>/health.py` + a `/readyz` route exist (grep generated tree).

---

## Phase 3: Alembic async migrations + recipes

Adds Alembic async migration scaffolding and the `just migrate` /
`just makemigration` / `just migration-check` recipes to the template. Flows
through the Phase-2 injection unchanged (more files under `backend_template/`).

**Files**: `backend_template/migrations/{env.py,script.py.mako}`,
`backend_template/alembic.ini`, `backend_template/Justfile` fragment (or template
`Justfile` override), `tests/test_e2e.py`

**Key changes**:
- `migrations/env.py` — async bridge `await connection.run_sync(do_run_migrations)`, `poolclass=pool.NullPool`, `DATABASE_URL` from `os.environ`, deterministic `MetaData(naming_convention=...)` (`fastapi_backend.md:223-299`)
- Recipes follow `<name>: sync` + `uv run alembic ...` (`Justfile:8-42`):
  `migrate: sync` → `alembic upgrade head`; `makemigration msg: sync` → `alembic revision --autogenerate -m`; `migration-check: sync` → `alembic check`
- Decide template-Justfile merge strategy: ship a full backend `Justfile` in the template that copytree overwrites the clone's, OR append recipes — note which in plan (overwrite is simpler, copytree-native)

**Verify**: `just test-e2e` (extended): generated `Justfile` contains `migrate:`
and `makemigration` recipes (grep); `cd <generated> && uv run just --list`
lists them (or grep the recipe names); `just check` still passes.

---

## Phase 4: Containerization (Containerfile + compose + dockerignore)

Adds the multi-stage `Containerfile`, `compose.yml` (app + Postgres + one-shot
migration service gated by `service_completed_successfully`), and `.dockerignore`
to the template. Additive; same injection path.

**Files**: `backend_template/{Containerfile,compose.yml,.dockerignore}`,
`tests/test_e2e.py`

**Key changes**:
- `Containerfile` — `python:3.14-slim`, uv `COPY --from=ghcr.io/astral-sh/uv:0.5`, two-phase `uv sync --locked`, `HEALTHCHECK` → `urllib.request.urlopen('http://localhost:8000/readyz', timeout=4)` (`containerization.md:22-256`)
- `compose.yml` — `app` (`build: .`, `depends_on: {db: service_healthy, migrate: service_completed_successfully}`), `migrate` one-shot (`alembic upgrade head`), `db` (`postgres:17`, `pg_isready` healthcheck), `volumes: pgdata:`; no `version:` key (`containerization.md:296-342`)
- `.dockerignore` — `.git,__pycache__,*.pyc,.ruff_cache,.mypy_cache`

**Verify**: `just test-e2e`: generated tree has `Containerfile`, `compose.yml`,
`.dockerignore` (file existence); `compose.yml` contains
`service_completed_successfully` and the `migrate` service, and `Containerfile`
`HEALTHCHECK` targets `/readyz` (grep). `just check` still passes.

---

## Phase 5: e2e hardening + template lint guard

Solidifies the extended e2e assertions and adds a lightweight guard against
silent `backend_template/` rot (the template is excluded from the repo's own
ruff/mypy — see design Open Risks).

**Files**: `tests/test_e2e.py`, `Justfile` (optional `check-backend-template` recipe), `pyproject.toml`

**Key changes**:
- One `@pytest.mark.e2e` test `test_scaffolded_backend_package_passes_check` asserting full chain: scaffold `--backend` → `just check` passes, `/readyz` route, migration recipes, and compose migration service all present
- Optional `just check-backend-template` → `uv run ruff check backend_template/` (a tolerant config) so template source can't rot undetected

**Verify**: `just test-e2e` green end-to-end; if added,
`just check-backend-template` exits 0.

---

## Testing Checkpoints

- **After P1**: `--backend`/`--fastapi` parse to `backend=True`; dry-run announces
  the backend; no-flag dry-run output unchanged. (`just test`)
- **After P2**: `--backend` produces a package with a FastAPI app whose
  `just check` passes; all injected `modernpackage` tokens renamed; updated
  `Popen` sequences green. (`just test`, `just test-e2e`)
- **After P3**: generated package has Alembic async env + `migrate`/
  `makemigration` recipes; `just check` still passes.
- **After P4**: generated package has `Containerfile`/`compose.yml`/`.dockerignore`
  with migration-gated compose and `/readyz` healthcheck.
- **After P5**: single comprehensive e2e test guards the whole feature; template
  source has a lint guard.

If context resets: the seam is `_add_backend(package_path)` + the `git add -A`
`Popen` call in `init_new_package`; everything backend-specific lives in
top-level `backend_template/`, shipped via `[tool.hatch.build]` include. No-flag
path must remain byte-for-byte identical (regression-assert against captured
baseline output).
