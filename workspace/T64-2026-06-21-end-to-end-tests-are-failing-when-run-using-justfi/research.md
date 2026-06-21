# Research Findings

Environment observed: pytest 9.1.0, Python 3.14.3, just 1.45.0, uv (repo root
`/home/niekas/tools/modernpackage`). All `file:line` refs are relative to repo root.

## Q1: How are `e2e`-marked tests defined, located, and discovered?

### Findings
- **Two separate e2e locations exist** and both are collected:
  - `tests/test_e2e.py` — 5 tests (`tests/test_e2e.py:149,217,276,353,452`).
  - `tests_e2e/test_backend_e2e.py:22` and
    `tests_e2e/test_fullstack_feature_e2e.py:26` — 1 test each.
  - Observed collection: `uv run pytest -m e2e --collect-only` → exactly these 7
    tests, `146 deselected`, no collection error.
- **Marker**: declared at `pyproject.toml:42-44`
  (`e2e: tests that perform real external calls`). Every e2e test carries
  `@pytest.mark.e2e` (e.g. `tests/test_e2e.py:149`, `tests_e2e/test_backend_e2e.py:22`).
- **`addopts`** (`pyproject.toml:40`):
  `--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'`. The
  default selector is `-m 'not e2e'`, so a bare `pytest` deselects all 7 e2e tests
  and enforces 95% coverage on the rest.
- **No `testpaths`** is configured → pytest recurses from rootdir. `norecursedirs`
  (`pyproject.toml:41`) excludes only `backend_template` and `frontend_template`;
  `tests_e2e/` is NOT excluded, so it is discovered.
- **Per-directory layout differences**:
  - `tests/` has `__init__.py` (empty, present) → imported as package `tests.test_e2e`.
  - `tests_e2e/` has **no `__init__.py`** and **no conftest** (verified:
    `find . -name conftest.py` returns nothing). Under pytest's default `prepend`
    import mode the dir is prepended to `sys.path`, so its modules import as
    top-level (`test_backend_e2e`, `test_fullstack_feature_e2e`).
  - **Shared helper**: `tests_e2e/_scaffold.py` is imported as a first-party
    top-level module via `from _scaffold import (...)`
    (`tests_e2e/test_backend_e2e.py:9`, `tests_e2e/test_fullstack_feature_e2e.py:9`).
    This only resolves because `tests_e2e/` is on `sys.path` (prepend mode) — the
    module docstring states this explicitly (`tests_e2e/_scaffold.py:3-6`).
  - `tests/test_e2e.py` keeps all helpers in-module (no `_scaffold` import).
- **Lint config records the layout asymmetry**: `pyproject.toml:78` ignores
  `INP001` (no `__init__.py`) and `I001` (first-party `_scaffold` import ordering)
  for `tests_e2e/*`; `tests/*` (a package) gets neither ignore (`pyproject.toml:77`).
- Stale bytecode hints at history: `tests/__pycache__/test_e2e_probe.*.pyc` exists
  with no matching `.py` (a removed probe module); not currently collected.

## Q2: What Justfile recipes run the e2e tests and how do they interact with pytest defaults?

### Findings
- **`e` is an alias for `test-e2e`** (`Justfile:13`: `e: test-e2e`).
- **`test-e2e`** (`Justfile:14-15`): prerequisite `sync` (`uv sync`), then
  `uv run pytest -m e2e --no-cov {{args}}`.
  - `-m e2e` **overrides** the `-m 'not e2e'` in `addopts` (last `-m` wins), so the
    7 e2e tests are selected.
  - `--no-cov` disables the coverage plugin, neutralizing `--cov=...` /
    `--cov-fail-under=95.0` from `addopts` (e2e runs touch little package code).
- **`test`** (`Justfile:11-12`): prerequisite `sync`, then
  `uv run pytest -n "$(nproc --ignore=1)" {{args}}`. Uses the unmodified
  `addopts`, so it runs the non-e2e suite with coverage and xdist parallelism.
- Both recipes depend on `sync` (`Justfile:7-9`: `uv sync`), which needs network on
  first run / stale lock (PyPI + the GitLab index `pyproject.toml:103-106`).
- `test-e2e` does NOT pass `-n` (xdist); the e2e tests run serially.

## Q3: How do e2e tests obtain the package under test, and which helpers do scaffolding?

### Findings
- **Mechanism = `git clone` of the local committed checkout**, not editable install
  and not the GitHub URL. Each test runs
  `git clone <REPO_ROOT> <destination>` where
  `REPO_ROOT = Path(__file__).resolve().parent.parent`
  (`tests/test_e2e.py:31,159`; `tests_e2e/_scaffold.py:19,173`).
  - Module docstring documents the deviation: it replicates the
    `git clone` + `just init` flow against the local repo instead of calling
    `init_new_package` (which clones GitHub) so local-template regressions fail
    the test (`tests/test_e2e.py:7-14`). Clone copies **committed** state only.
- **Scaffolding helpers live in `modernpackage/main.py`** and are called directly
  (with `# noqa: SLF001`) by the tests:
  - `normalize_module_name` (`main.py:199`) — `.`/`-` → `_`.
  - `_write_package_metadata` (`main.py:446`) — str.replace template literals in
    `pyproject.toml` (author/email/description/url) + `_apply_license`
    (`main.py:496`, PEP 639 key + drops MIT trove classifier).
  - `_strip_scaffolding` (`main.py:644`) — deletes `_SCAFFOLDING_PATHS_TO_DELETE`
    (`main.py:519-527`: `modernpackage/main.py`, `tests/test_e2e.py`, `tests_e2e`,
    `docs`, `BACKLOG.md`, `backend_template`, `frontend_template`), writes
    `_TEST_MAIN_STUB` (`main.py:534-540`) + `_README_STUB`, and calls
    `_remove_project_scripts` (`main.py:621`).
  - `_add_backend` (`main.py:996`) — copytree `backend_template/` over the clone,
    append `_BACKEND_DEPENDENCIES`/`_BACKEND_DEV_DEPENDENCIES` to pyproject and
    `_BACKEND_RECIPES` to Justfile.
  - `_add_frontend` (`main.py:966`) — copytree `frontend_template/` into
    `frontend/`, append `_FRONTEND_RECIPES`.
  - `_inject_templates(package_path, fullstack=...)` (`main.py:983`) — backend +
    optional frontend, then `_stage_injected_files` (`git add -A`, `main.py:929`).
- **`just init`** (`Justfile:55-73`) is invoked as a subprocess
  (`tests/test_e2e.py:173-178`). It `git grep`-renames the `modernpackage` token,
  resets version to `0.0.1`, `mv modernpackage <module>`, removes `.git/`/`.venv`,
  re-inits git, and makes one commit. Git identity is injected via
  `_GIT_IDENTITY_ENV` merged onto `os.environ`
  (`tests/test_e2e.py:38-43,176`; `tests_e2e/_scaffold.py:22-27`).
- **Backend test stages manually** before init (`git add -A`,
  `tests/test_e2e.py:239`); the fullstack/`_inject_templates` path stages
  internally (`main.py:993`).

## Q4: What does the generated package's `just check` chain execute, and what does each step require?

### Findings
- The cloned root `Justfile:54` defines:
  `check: check-format check-lint check-complexity check-typecheck test audit`
  (run sequentially; `# deadcode` is commented out).
  - `check-format` → `uv run ruff format --check modernpackage tests` (`Justfile:31-32`).
  - `check-lint` → `uv run ruff check modernpackage tests` (`Justfile:34-35`).
  - `check-complexity` → `uv run ruff check --select C901 ...` (`Justfile:37-38`;
    max-complexity 8 at `pyproject.toml:85`).
  - `check-typecheck` → `uv run mypy modernpackage tests` (`Justfile:40-41`;
    strict, `python_version = "3.14"`, `pyproject.toml:87-95`).
  - `test` → `uv run pytest -n "$(nproc --ignore=1)" ...` (`Justfile:14-15`).
  - `audit` → `uv run pip-audit --skip-editable` (`Justfile:42-43`).
- Every recipe depends on `sync` = `uv sync` (`Justfile:7-9`).
- **External requirements per step**:
  - `sync`: network on first run / stale lock (PyPI + GitLab index
    `pyproject.toml:103-106`).
  - format/lint/complexity/typecheck/test: offline after sync; need
    `ruff`/`mypy`/`pytest(+cov,+xdist)` from the dev group (`pyproject.toml:28-37`);
    `nproc` on PATH (Linux).
  - **`audit`: always needs network** (pip-audit queries the OSV/PyPI advisory DB).
  - Python **3.14** required (`pyproject.toml:8` `requires-python = ">= 3.14"`).
- **Migration recipes are NOT in the check chain** (`main.py:577-578`): `migrate`
  (`alembic upgrade head`), `makemigration` (`alembic revision --autogenerate`),
  `migration-check` (`alembic check`) come from `_BACKEND_RECIPES`
  (`main.py:580-589`) and need a live Postgres at `DATABASE_URL`.
- **Frontend recipes are NOT in the check chain** either (`main.py:591-595`); from
  `_FRONTEND_RECIPES` (`main.py:596-618`): `frontend-install` (`npm ci`),
  `frontend-build` (`npm run build`), `frontend-test` (`vitest run`),
  `generate-client` (`openapi-ts`), `frontend-test-e2e`
  (`npx playwright install --with-deps chromium && npm run test:e2e`),
  `frontend-check` (format:check/lint/typecheck/test). Frontend scripts map in
  `frontend_template/package.json:6-18`; need Node/npm + network.

## Q5: How are modifications applied to an already-scaffolded package, and how is it re-verified?

### Findings
- **Backend model + migration** (`tests_e2e/test_backend_e2e.py`):
  - `_register_product_model` (`tests_e2e/_scaffold.py:149`) appends a
    `Product` SQLAlchemy model (`_PRODUCT_MODEL_SOURCE`, `_scaffold.py:133-146`) to
    the renamed `<module>/db.py` (env.py imports `Base` from there for
    `target_metadata`).
  - `_expose_db_port` (`_scaffold.py:111`) edits the ephemeral compose copy to
    publish `127.0.0.1:5432:5432` using the unique anchor `'  db:\n    image:'`
    (deviation documented at `_scaffold.py:120-124`).
  - Re-verify: `compose up -d --build`, poll `/readyz` until 200
    (`_wait_for_ready`, `_scaffold.py:82`), then host-side
    `just makemigration "add products"` + `just migrate` with
    `DATABASE_URL=_HOST_DATABASE_URL` injected (recipes don't set it;
    `env.py:29` hard-requires it) (`test_backend_e2e.py:66-81`), and assert a
    version file contains `create_table('products')` (`test_backend_e2e.py:89`).
- **Fullstack feature** (`tests_e2e/test_fullstack_feature_e2e.py`):
  - `_register_products_page` (`_scaffold.py:335`) overwrites `frontend/src/App.tsx`
    and adds `frontend/e2e/products.spec.ts` **before** `just init`
    (`_scaffold.py:410`) so the token is renamed.
  - `_register_products_feature` (`_scaffold.py:348`) runs **after** `just init`:
    appends the model, writes `<module>/products.py` (router, `_scaffold.py:297-332`),
    and wires it into `app.py` via asserted anchors
    (`from <module>.health import router as health_router` and
    `app.include_router(health_router)`) (`_scaffold.py:365-382`).
  - Re-verify: compose up + `/readyz`, host-side migrate, POST `/api/products`
    then GET round-trip (`_http_post_json`, `_scaffold.py:199`), `frontend-install`,
    `generate-client` (asserts `products` in regenerated client),
    `frontend-build` (asserts `dist/index.html`), `frontend-test-e2e`
    (`test_fullstack_feature_e2e.py:88-143`).
- **In `tests/test_e2e.py`**, modifications are via `main.py` injection only
  (`_add_backend` at `:238`, `_inject_templates(fullstack=True)` at `:390,491`);
  re-verification is `just check` (`:190,257,399`) plus frontend `just frontend-test`
  / live `compose up` + HTTP assertions (`:399-579`).

## Q6: What environment/tooling prerequisites do the e2e tests assume, and how are missing ones handled?

### Findings
- **Required base tools** `('git', 'just', 'uv')` (`tests/test_e2e.py:32`,
  `tests_e2e/_scaffold.py:20`). Each test loops `shutil.which(tool)` and calls
  `pytest.skip(...)` if missing — **skip, not fail** (`tests/test_e2e.py:151-153`,
  `tests_e2e/test_backend_e2e.py:24-26`).
- **Node toolchain (`npm`)** added for frontend/fullstack tests
  (`_REQUIRED_RUNTIME_TOOLS`, `tests/test_e2e.py:36,468`;
  `tests_e2e/test_fullstack_feature_e2e.py:22,28`) — same `pytest.skip` guard.
- **Compose** detected via `_detect_compose_command`
  (`tests/test_e2e.py:68`, `_scaffold.py:52`) probing
  `docker compose` → `podman compose` → `podman-compose` with `<cmd> version`;
  `FileNotFoundError` is swallowed. `None` → `pytest.skip('no compose command...')`
  (`tests/test_e2e.py:471-473`, `test_backend_e2e.py:42-44`).
- **Playwright browser install** failure is treated as "browsers unavailable" and
  **skipped** when stderr contains `playwright install`
  (`tests/test_e2e.py:567-574`, `test_fullstack_feature_e2e.py:133-140`).
- **Git identity** is forced via `_GIT_IDENTITY_ENV` so `just init`'s commit works
  on identity-less CI (`tests/test_e2e.py:38-43`, `_scaffold.py:22-27`).
- **Ports / DB config**: app on host `127.0.0.1:8000` (`/livez`,`/readyz`,`/api`);
  Postgres exposed at `127.0.0.1:5432` only by `_expose_db_port` for host-side
  migrations; `_HOST_DATABASE_URL =
  postgresql+asyncpg://appuser:secret@localhost:5432/appdb` (`_scaffold.py:108`).
  Compose internal URL uses host `db` (`backend_template/compose.yml:9,19`).
- **Network/runtime cost is assumed, not guarded**: the inner `just check` runs
  `uv sync` + networked `pip-audit`; `compose up` pulls `postgres:17` and builds a
  `python:3.14-slim` image; `npm ci` + `vite build` hit the network. Offline
  runners fail at sync (documented `tests/test_e2e.py:7-15`,353-366).
- **Python**: generated package requires `>= 3.14`; the inner image is
  `python:3.14-slim` (`backend_template/Containerfile:2`).

## Cross-Cutting Observations
- The repo root `Justfile`/`pyproject.toml` ARE the template: `just init`
  in-place renames `modernpackage` → `<module>` (`Justfile:55-73`). The generated
  package's check chain is the same recipes minus the deleted scaffolding.
- Two parallel e2e suites coexist with **duplicated infra helpers**: `_run`,
  `_detect_compose_command`, `_http_get`, `_wait_for_ready` appear both in
  `tests/test_e2e.py` and `tests_e2e/_scaffold.py` (intentional, `_scaffold.py:3-6`).
- `tests/test_e2e.py` and `tests_e2e` are themselves stripped from any generated
  package (`_SCAFFOLDING_PATHS_TO_DELETE`, `main.py:519-527`) so they never ship.
- DATABASE_URL is hard-required (`KeyError`) at `backend_template/migrations/env.py`
  (env.py:29 per analyzer); recipes never set it, so e2e tests inject it host-side.

## Open Areas
- The questions frame "tests are failing", but discovery itself is clean: both
  `pytest -m e2e --no-cov` (7 collected) and the default run (146 collected)
  complete **without collection errors** in this environment. Any failure is
  therefore at **runtime** of a specific e2e test (e.g. missing compose/Node,
  network, port conflicts, or an assertion), not at marker/path discovery — the
  questions do not ask for a specific failure root-cause and none was reproduced
  here.
- Whether `just test` (the default, parallel, coverage-gated recipe) is the
  command the reporter used vs. `just e`/`test-e2e` is not determinable from the
  codebase alone.
