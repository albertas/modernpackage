# Research Findings

Investigation done first-hand: read source, ran `just e` (full suite) and several
individual tests under `uv run pytest`. Environment tooling probed directly.

## Q1: How are e2e tests selected and executed?

### Findings
- `Justfile:16` — `e: test-e2e` is a pure alias.
- `Justfile:17-18` — `test-e2e *args: sync` runs `uv run pytest -m e2e --no-cov {{args}}`.
  It depends on `sync` (`Justfile:8-9 → uv sync`). No `-n`, so e2e runs **serially**.
- `Justfile:11-12` — the default `test *args: sync` runs `uv run pytest -n "$(nproc --ignore=1)" {{args}}` (parallel via xdist).
- `pyproject.toml:42` — `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`.
  The default selection is `-m 'not e2e'`, so plain `pytest`/`just test` **excludes** e2e tests and enforces 95% coverage.
- `test-e2e` overrides this two ways: a second `-m e2e` (the **last** `-m` wins in pytest, flipping selection to e2e-only) and `--no-cov` (disables the coverage plugin; e2e tests exercise subprocess/container code that the coverage measurement does not see).
- `pyproject.toml:43` — `norecursedirs = ["backend_template", "frontend_template"]` keeps the in-repo template trees out of collection (they contain their own `tests/`).
- `pyproject.toml:44-46` — single marker registered: `e2e: tests that perform real external calls (network/subprocess/fs)`.
- Observed: `just e` collected 7 e2e tests, **146 deselected** (the `not e2e` suite), ran in ~319 s.

## Q2: What does each e2e test do?

### Findings
Tests live in two places. `tests/test_e2e.py` (4 tests, self-contained helpers) and
`tests_e2e/` (2 tests + `_scaffold.py` shared helpers). `tests_e2e/` has no `__init__.py`;
`_scaffold` is imported flat under pytest prepend mode (`tests_e2e/_scaffold.py:1-6`).

Common scaffold flow (`tests/test_e2e.py:159-178`, `tests_e2e/_scaffold.py:160-196`):
`git clone <REPO_ROOT>` → `main._write_package_metadata` → `main._strip_scaffolding` →
inject (`_add_backend` / `_inject_templates`) → `git add -A` → `just init <module>`.
Then assertions, optionally `compose up` + HTTP.

- `test_scaffolded_package_passes_check` (`tests/test_e2e.py:149-213`) — no-extras: strip, init, `just check`; asserts metadata substituted, scaffolding removed, version `0.0.1`. **PASSED**.
- `test_scaffolded_backend_package_passes_check` (`:216-272`) — `_add_backend`, `git add -A`, init, `just check`; asserts `app.py`/`health.py`, token renamed, migrate recipes, `compose.yml`/`Containerfile`. **PASSED**.
- `test_scaffolded_package_has_no_backend_or_frontend` (`:275-350`) — strip+init only; asserts NO backend/frontend dirs/files/deps/recipes/import-tokens leak. **PASSED**.
- `test_scaffolded_fullstack_package_passes_check` (`:353-449`) — `_inject_templates(fullstack=True)`, init, `just check`, `just frontend-install` (`npm ci`), `just frontend-test` (Vitest). **PASSED**.
- `test_fullstack_package_runs_end_to_end` (`:452-579`) — strip, fullstack inject, init, `compose up -d --build`, poll `/readyz`, assert `/livez`+`/readyz`, `frontend-install`, `generate-client` (live openapi), `frontend-build`, `frontend-test-e2e`. **FAILED at `compose up`** (`:504-505`).
- `tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end` (`:23-97`) — `scaffold_backend_package`, `_expose_db_port`, `compose up`, poll `/readyz`, register `Product` model, host-side `just makemigration "add products"` + `just migrate` (with `DATABASE_URL`), assert autogen `create_table('products')`. **FAILED at `compose up`** (`:53`).
- `tests_e2e/test_fullstack_feature_e2e.py::test_fullstack_feature_runs_end_to_end` (`:27-145`) — `scaffold_fullstack_package`, `_register_products_feature`, `_expose_db_port`, `compose up`, migrate, POST/GET `/api/products`, `generate-client`, `frontend-build`, `frontend-test-e2e`. **FAILED at `compose up`** (`:56`).

`_expose_db_port` (`tests_e2e/_scaffold.py:111-130`) edits the tmp compose copy to publish `127.0.0.1:5432:5432` so host-side `just migrate` reaches Postgres (shipped `db:` has no `ports:`, `compose.yml:23-36`).

## Q3: How is the package installed / how are `modernpackage`/`vupi` resolved?

### Findings
- **No explicit `pip install -e`** anywhere. Installation is implicit via `uv sync`.
  Outer repo: `Justfile:8-9` `sync` → `uv sync` installs the repo's own project editable into `.venv`. e2e tests run under `uv run pytest`, so `from modernpackage import main` (`tests/test_e2e.py:28`, `_scaffold.py:16-17`) resolves to that editable install.
- The generated package does **not** depend on `modernpackage`. `_strip_scaffolding` deletes `modernpackage/main.py` and removes `[project.scripts]` (`main.py:519-527`, `:621-661`); the scaffolder code never ships. The package is renamed to its own module by `just init` and `uv sync` (run inside `just check`/`just init` via `: sync`) installs *it* editable.
- `vupi>=0.0.10` stays in the dev group (`pyproject.toml:34`) and is carried into the generated package. It is resolved from the custom index `pyproject.toml:99-101` `[[tool.uv.index]] name=gitlab url=https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple`. Needs network.
- **Inside the container** (`backend_template/Containerfile`): builder STEP 5 `uv sync --locked --no-install-project --no-dev` (no source), STEP 7 `uv sync --locked --no-dev --no-editable` after `COPY . /app` (non-editable install). This is where the failure occurs — see Q6.

## Q4: How does the scaffolding code in `main.py` work?

### Findings
- `normalize_module_name` (`main.py:199-207`) — `.`/`-` → `_`; preserves `_`, case. `backend-run.pkg` → `backend_run_pkg`.
- `_write_package_metadata` (`main.py:446-493`) — targeted `str.replace` of known template literals (`Name Surname`, `email@example.com`, the description, `_TEMPLATE_REPOSITORY_URL`), each TOML-escaped; None fields skipped; license via `_apply_license` (`:496-511`, inserts PEP 639 `license=` after `readme`, drops MIT trove classifier). Missing pyproject → notice, no raise.
- `_strip_scaffolding` (`main.py:644-661`) — deletes `_SCAFFOLDING_PATHS_TO_DELETE` (`:519-527`: `modernpackage/main.py`, `tests/test_e2e.py`, `tests_e2e`, `docs`, `BACKLOG.md`, `backend_template`, `frontend_template`), writes `_TEST_MAIN_STUB` (`:534-540`, asserts `__version__=='0.0.1'`) and `_README_STUB`, removes `[project.scripts]` (`_remove_project_scripts:621-641`). Keeps literal `modernpackage` token in stubs so init's sed rewrites them.
- `_add_backend` (`main.py:996-1008`) — `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)`, then `_append_backend_dependencies` (`:888-910`, fills `dependencies=[]` with fastapi/sqlalchemy/asyncpg/alembic/uvicorn and prepends `httpx` to dev) + `_append_backend_recipes` (`:913-926`, appends `migrate`/`makemigration`/`migration-check`).
- `_inject_templates` (`main.py:983-993`) — `_add_backend`, optionally `_add_frontend` (`:966-980`), then `_stage_injected_files` (`:929-947`, `git add -A`). The backend-only e2e tests call `_add_backend` then stage manually (`tests/test_e2e.py:238-240`).
- `just init` (`Justfile:55-72`) — `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/<name>/g'` (Linux branch), sed version → `0.0.1` in `modernpackage/__init__.py`, `mv modernpackage <name>`, `rm -fr .git .venv`, `git init`/`add`/`commit`. The sed only touches **tracked** files, hence the mandatory `git add -A` before init.
- Required state to pass `just check`: clone with committed template, metadata written, scaffolding stripped, injected files staged, then init. Verified: the no-extras and both `_passes_check` flows succeed.

## Q5: External tooling / runtime environment

### Findings
- `_scaffold.py:20` / `tests/test_e2e.py:32` — `REQUIRED_TOOLS = ('git','just','uv')`; `_REQUIRED_RUNTIME_TOOLS` adds `'npm'` (`tests/test_e2e.py:36`, `test_fullstack_feature_e2e.py:22`).
- Skip vs fail: missing required tool → `pytest.skip` (`tests/test_e2e.py:151-153`, etc.); no compose command → `pytest.skip` (`_detect_compose_command` returns None, `_scaffold.py:52-66`); Playwright browser-install failure → `pytest.skip` (`tests/test_e2e.py:567-574`). Network failures inside `just check`/`compose` surface as **assert failures**, not skips.
- Compose detection order `_COMPOSE_CANDIDATES` (`_scaffold.py:45-49`): `docker compose` → `podman compose` → `podman-compose`.
- Migration recipes don't set `DATABASE_URL`; `env.py:29` `os.environ['DATABASE_URL']` hard-requires it, so tests inject `_HOST_DATABASE_URL` (`_scaffold.py:108`, `test_backend_e2e.py:67`).
- **Present in this environment**: git 2.53.0, just 1.45.0, uv 0.11.14, npm/node 22.9.0, podman, podman-compose, pip-audit; GitHub + gitlab index reachable. **Missing**: `docker` (podman is used). So compose tests do **not** skip — they run and fail.

## Q6: Concrete failure when run via the Justfile alias

### Findings
`just e` result: **3 failed, 4 passed, 146 deselected in 319 s**; `Recipe test-e2e failed ... exit code 1`.

Failing tests (all three fail at the **same step and root cause**):
1. `tests/test_e2e.py::test_fullstack_package_runs_end_to_end` — assert at `:504-505`.
2. `tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end` — assert at `:53`.
3. `tests_e2e/test_fullstack_feature_e2e.py::test_fullstack_feature_runs_end_to_end` — assert at `:56`.

Each fails at `podman compose up -d --build` returning **exit code 2** (`assert 2 == 0`).
The build dies in `backend_template/Containerfile` builder **STEP 5/7**:
`uv sync --locked --no-install-project --no-dev`, which bind-mounts **only** `uv.lock` and
`pyproject.toml`. uv builds editable metadata for the root project; the hatchling
dynamic-version source (`pyproject.toml:74-75` `[tool.hatch.version] path = "modernpackage/__init__.py"`,
renamed by `just init` to e.g. `backend_run_pkg/__init__.py`) reads that file, which is
**not in the build context at that layer** (source is `COPY . /app` only at STEP 6). Error:

```
OSError: Error getting the version from source `regex`:
file does not exist: backend_run_pkg/__init__.py
... hatchling ... prepare_metadata_for_build_editable
error: Failed to generate package metadata for `backend-run-pkg @ editable+.`
ERROR:podman_compose:Build command failed
```

The 4 passing tests (`*_passes_check`, `has_no_backend_or_frontend`) never invoke
`compose up`, so they are unaffected. The failure is isolated to the container build,
not to scaffolding, `just init`, or the host-side `just check`.

## Q7: Composition and behavior of the generated `just check`

### Findings
- `Justfile:53` — `check: check-format check-lint check-complexity check-typecheck test audit`. Sub-recipes (`Justfile:20-39`):
  - `check-format` → `ruff format --check`; `check-lint` → `ruff check`; `check-complexity` → `ruff check --select C901` (mccabe `max-complexity=8`, `pyproject.toml:91-92`); `check-typecheck` → `mypy` (strict, py 3.14, `pyproject.toml:94-101`); `test` → `uv run pytest -n …` (default `-m 'not e2e'`, cov ≥95%); `audit` → `pip-audit --skip-editable` (network).
  - `deadcode` is commented out in both `check` and the recipe (`Justfile:32-33,40-41,53`).
- Each sub-recipe depends on `sync` (`uv sync`), which installs the (renamed) project + dev deps incl. `vupi` from the gitlab index — network required.
- Behavior against a freshly scaffolded package: **passes** (observed in 3 of 4 passing e2e tests). Migration/frontend recipes (`_BACKEND_RECIPES:580-589`, `_FRONTEND_RECIPES:596-618`) are intentionally **excluded from `check`** (they need a live DB / Node), asserted at `tests/test_e2e.py:446-449`.
- Against a *modified* package: `test_scaffolded_*_passes_check` add backend/frontend then run `just check` and pass; the runtime tests add a `Product` model + router and exercise migrate/HTTP outside `just check`.

## Cross-Cutting Observations
- `tests_e2e/_scaffold.py` deliberately mirrors `tests/test_e2e.py` helpers (`_run`, `_detect_compose_command`, `_http_get`, `_wait_for_ready`) — duplicated, not shared (`_scaffold.py:1-6`).
- All scaffolding mutates a `git clone` of the **committed** repo state; uncommitted edits are not exercised (`tests/test_e2e.py:10-13`).
- `just init` (`Justfile:55-72`) renaming relies on the `modernpackage` literal token being present in tracked files; injected files must be `git add`-ed first.
- The container's dynamic-version + bind-mount pattern is the single point of failure shared by every compose-based test.

## Open Areas
- Whether the Containerfile STEP-5 failure is a recent regression (e.g. uv version behavior change re: building editable metadata under `--no-install-project`) vs. always-present in this environment could not be determined from the codebase alone — no prior passing run is recorded in-repo. The `.coverage`/`metrics.yml` artifacts are not test logs.
- The Containerfile copies uv from `ghcr.io/astral-sh/uv:0.5`; the host uv is 0.11.14. The version mismatch's relevance to the metadata-build behavior was not isolated.
