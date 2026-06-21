# Research Findings

## Q1: How e2e tests are defined, marked, invoked; which test functions exist

### Findings
- **Marker**: every e2e test carries `@pytest.mark.e2e` (`tests/test_e2e.py:122,189,248,325,424`; `tests_e2e/test_backend_e2e.py:21`; `tests_e2e/test_fullstack_feature_e2e.py:25`). Marker declared in `pyproject.toml:42-44` (`e2e: tests that perform real external calls (network/subprocess/fs)`).
- **Default exclusion**: `pyproject.toml:39` `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`. The `-m 'not e2e'` deselects all e2e tests on a bare `pytest`/`just test` run.
- **Selection recipes** (`Justfile`):
  - `test *args: sync` → `uv run pytest -n "$(nproc --ignore=1)" {{args}}` (inherits `-m 'not e2e'` from addopts → e2e NOT run).
  - `test-e2e *args: sync` → `uv run pytest -m e2e --no-cov {{args}}` (the `-m e2e` on the CLI overrides addopts' `-m 'not e2e'`; `--no-cov` disables coverage gate).
  - `e: test-e2e` is a shorthand alias.
- **Collection scope**: `norecursedirs = ["backend_template", "frontend_template"]` (`pyproject.toml:40`). `tests_e2e/` is NOT excluded, so pytest discovers both `tests/` and `tests_e2e/`. `tests_e2e/` has no `__init__.py` (per-file ignore `INP001` at `pyproject.toml`), and `_scaffold` is imported as a first-party sibling module under pytest "prepend" mode (`tests_e2e/_scaffold.py:1-6`).
- **Test functions**:
  - `tests/test_e2e.py`: `test_scaffolded_package_passes_check` (:123), `test_scaffolded_backend_package_passes_check` (:190), `test_scaffolded_package_has_no_backend_or_frontend` (:249), `test_scaffolded_fullstack_package_passes_check` (:326), `test_fullstack_package_runs_end_to_end` (:425).
  - `tests_e2e/test_backend_e2e.py`: `test_backend_package_runs_end_to_end` (:22).
  - `tests_e2e/test_fullstack_feature_e2e.py`: `test_fullstack_feature_runs_end_to_end` (:26).

## Q2: Compose detection + exact subcommands/flags; duplication

### Findings
- **Detection candidates** (identical tuple in both files): `('docker','compose')`, `('podman','compose')`, `('podman-compose',)` — `tests/test_e2e.py:60-64`, `tests_e2e/_scaffold.py:44-48`.
- **`_detect_compose_command`** probes `[*candidate, 'version']` with `check=False`, catches `FileNotFoundError` (treated as "not available"), returns the first candidate whose `returncode == 0`, else `None` — `tests/test_e2e.py:67-88`, `tests_e2e/_scaffold.py:51-65`.
- **Exact compose calls** (all four runtime tests use the same flags):
  - Up: `[*compose, 'up', '-d', '--wait', '--build']` — `tests/test_e2e.py:476`, `tests_e2e/test_backend_e2e.py:51`, `tests_e2e/test_fullstack_feature_e2e.py:54`.
  - Down (in `finally`): `[*compose, 'down', '-v']` — `tests/test_e2e.py:550`, `test_backend_e2e.py:95`, `test_fullstack_feature_e2e.py:143`.
- **Duplication**: `_detect_compose_command`, `_http_get`, `_run`, the `_COMPOSE_CANDIDATES` tuple, `REQUIRED_TOOLS`, and `_GIT_IDENTITY_ENV` are **duplicated** verbatim between `tests/test_e2e.py` and `tests_e2e/_scaffold.py`. `_scaffold.py:1-6` docstring states it intentionally "Mirrors the proven scaffold/compose/http helpers in `tests/test_e2e.py`". The `tests_e2e/` runtime tests import these from `_scaffold` rather than re-defining.

## Q3: Which backends `--wait` resolves to, and option support per backend

### Findings (verified in this environment)
- Local availability: **`docker` is not installed** (`docker: command not found`); `podman 5.7.0` + `podman-compose 1.5.0` are present. So `_detect_compose_command` skips the docker candidate (FileNotFoundError) and resolves to **`['podman', 'compose']`**, which delegates to `podman-compose 1.5.0`.
- **`podman compose up` / `podman-compose up` flag set (1.5.0)**: `-h -d --no-color --quiet-pull --no-deps --force-recreate --always-recreate-deps --no-recreate --no-build --no-start --build --abort-on-container-exit --abort-on-container-failure -t/--timeout -V --remove-orphans --scale --exit-code-from --pull --pull-always --build-arg --no-cache`. **`--wait` is NOT present.**
- **Confirmed rejection**: `podman compose up --wait` → `podman-compose: error: unrecognized arguments: --wait` / `exit status 2`. The tests' `up -d --wait --build` therefore fails non-zero on the podman backend (`up.returncode == 0` assertion fails before any HTTP check).
- `podman-compose` does expose a separate top-level `wait` subcommand (`{...,wait,...}`), but that is not the same as `up --wait`.
- **`down -v`** IS supported by `podman compose down` (`-v/--volumes`), so teardown works on podman.
- **docker compose**: supports `up --wait` (added in Compose v2; blocks until `depends_on`/healthcheck conditions are satisfied) and `up --build`, and `down -v`. (External/general knowledge; docker not installable here to re-verify.)
- Net: `--wait` (the block-until-healthy flag the tests rely on) is supported by `docker compose` but **rejected by `podman compose`/`podman-compose` 1.5.0**, the only backend available in this environment.

## Q4: compose.yml startup ordering / readiness; how tests depend on it

### Findings (`backend_template/compose.yml`)
- Three services: `app` (:4), `migrate` (:15), `db` (:23). No top-level `version:` (comment :1-2, portability).
- **`db` healthcheck** (:29-34): `pg_isready -U appuser -d appdb`, `interval 10s`, `timeout 5s`, `retries 5`, `start_period 30s`. Named volume `pgdata` (:35-38).
- **`migrate`** (:15-22): `build: .`, `command: ["alembic","upgrade","head"]`, `DATABASE_URL=postgresql+asyncpg://appuser:secret@db:5432/appdb`, `depends_on: db: condition: service_healthy`. Runs once to completion.
- **`app`** (:4-14): `build: .`, publishes `127.0.0.1:8000:8000` (:6-7), same `DATABASE_URL` to host `db`, and `depends_on`: `db → service_healthy` (:11-12) AND `migrate → service_completed_successfully` (:13-14). So app starts only after DB healthy and migrations finished.
- **App readiness signal**: `Containerfile:24-25` `HEALTHCHECK` polls `http://localhost:8000/readyz` (interval 30s, timeout 5s, start-period 20s, retries 3). `/readyz` returns 200 only when a `SELECT 1` succeeds (`health.py:37-46`).
- **How tests depend on it**: the runtime tests rely on `up --wait` to block until all healthchecks/conditions pass before any HTTP assertion (`test_e2e.py:478-487`; `test_backend_e2e.py:48-59`; `test_fullstack_feature_e2e.py:54-62`). Docstrings explicitly state `--wait` "blocks until the app's `/readyz` healthcheck passes, proving DB + migrations + app readiness" (`test_e2e.py:427-431`). Tests assert `service_completed_successfully` and `migrate:` literally appear in the shipped compose (`test_e2e.py:242-243`). When `--wait` is rejected (Q3), `up` returns non-zero and the readiness gate is never honored.

## Q5: Scaffolded `just check`/`just test`; what makes inner pytest pass

### Findings
- The scaffold clones the local repo (`test_e2e.py:132`), so the generated package inherits this repo's `Justfile` and `pyproject.toml`, with the `modernpackage` token renamed to the module by `just init` (`Justfile init` recipe: `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/<module>/g'`).
- **`check` chain** (`Justfile`): `check: check-format check-lint check-complexity check-typecheck test audit`. Frontend/backend recipes are deliberately NOT in the chain (`main.py:576-578,590-594`).
- **`test` recipe**: `uv run pytest -n "$(nproc --ignore=1)" {{args}}` (`Justfile`). Inherits `addopts` from the generated `pyproject.toml`: `--cov=<module> --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'` (renamed from `pyproject.toml:39`).
- **xdist**: `-n "$(nproc --ignore=1)"` runs (cores − 1) workers via `pytest-xdist` (dev dep, `pyproject.toml:33`).
- **Coverage gating** (`pyproject.toml:39`): `--cov-fail-under=95.0` fails the run if total coverage < 95%; `--no-cov-on-fail` suppresses the coverage report when tests already failed (so a test failure isn't masked by coverage output). `-m 'not e2e'` means the inner `just check` never recursively runs e2e tests.
- **Bundled template tests** that supply the coverage:
  - Backend: `backend_template/tests/test_app.py` (6 tests: livez/readyz pass+fail, `database_ready` true/false, `get_db` yields) — copied in by `_add_backend`, exercises `app.py`/`db.py`/`health.py`.
  - No-extras: stub `tests/test_main.py` asserting `0.0.1` (`test_e2e.py:185-186`).
- Per-file lint ignores keep template tests passing `ruff`/`mypy` (`pyproject.toml` `[tool.ruff.lint.per-file-ignores]` for `tests/*`, `tests_e2e/*`, `backend_template/**`).
- `audit` runs networked `pip-audit --skip-editable`; `check` therefore needs network (`test_e2e.py:13-14`).

## Q6: How tests verify live app + DB; endpoints, migrations, host reachability

### Findings
- **Endpoints**: `/livez` (liveness, never touches DB — `health.py:31-34`) and `/readyz` (200 when `SELECT 1` succeeds, else 503 — `health.py:37-46`). `database_ready` uses a 2.0s timeout (`health.py:16,23`).
- **HTTP from host**: tests GET `http://127.0.0.1:8000/livez` and `/readyz` via stdlib `urllib` (`_http_get`, `test_e2e.py:91-104`), asserting status 200 and `'pass'` in body. Fullstack feature also POSTs/GETs `http://127.0.0.1:8000/api/products` via `_http_post_json`/`_http_get` (`test_fullstack_feature_e2e.py:87-98`, `_scaffold.py:172-193`).
- **Port exposure**: app is reachable because `compose.yml:6-7` publishes `127.0.0.1:8000:8000`. Postgres is NOT exposed by the shipped compose (`compose.yml:23-36` has no `ports:`). For host-side migrations the test mutates the tmp copy: `_expose_db_port` inserts `ports: - "127.0.0.1:5432:5432"` under the `db:` service using the unique anchor `  db:\n    image:` (`_scaffold.py:84-103`).
- **DATABASE_URL**: in-container default `postgresql+asyncpg://appuser:secret@db:5432/appdb` (`db.py:23`, `compose.yml:9,19`). Host-side migration recipes get `_HOST_DATABASE_URL = postgresql+asyncpg://appuser:secret@localhost:5432/appdb` (`_scaffold.py:81`) injected via env (`test_backend_e2e.py:64-65`, `test_fullstack_feature_e2e.py:66`) because `migrations/env.py:29` hard-requires `os.environ['DATABASE_URL']` and the recipes don't set it.
- **Migration recipes** (`main._BACKEND_RECIPES`, `main.py:579-588`, appended to generated Justfile): `migrate: sync → uv run alembic upgrade head`; `makemigration message: sync → uv run alembic revision --autogenerate -m "{{message}}"`; `migration-check: sync → uv run alembic check`.
- **Migration flow exercised**: tests register a `Product` model into `db.py` (`_scaffold.py:106-130`), run `just makemigration "add products"` then `just migrate`, and assert a version file contains `create_table('products')` (`test_backend_e2e.py:64-89`; `test_fullstack_feature_e2e.py:67-84`). `env.py` autogenerate sees the table because it imports `Base` (`env.py:7,12`) and `Product` subclasses `Base`.
- **Alembic config**: `alembic.ini:4-5` `script_location = migrations`, `prepend_sys_path = .`. Async env bridges sync migration API onto asyncpg (`env.py:25-36`).

## Cross-Cutting Observations
- The single failing point across **all four** runtime tests is the `up -d --wait --build` invocation: `--wait` is unsupported by `podman compose`/`podman-compose 1.5.0` (the only backend installed here), so `up.returncode != 0` and the `assert up.returncode == 0` fails immediately (`test_e2e.py:477`, `test_backend_e2e.py:52`, `test_fullstack_feature_e2e.py:55`). The compose-detection layer treats podman as available (its `version` probe returns 0) but the up-flag layer assumes docker-compose semantics.
- Compose helper logic is duplicated between `tests/test_e2e.py` and `tests_e2e/_scaffold.py` (Q2), so a fix to `--wait` handling would need to land in both places.
- The two non-runtime tests in `tests/test_e2e.py` (`..._passes_check`, `...has_no_backend_or_frontend`, `..._fullstack_..._passes_check`) do not call compose and are unaffected by the `--wait` issue; they depend on `git`/`just`/`uv`/`npm` and network for `uv sync`/`pip-audit`/`npm ci`.
- Skip guards: missing `git`/`just`/`uv`/`npm` → `pytest.skip`; `_detect_compose_command() is None` → skip; Playwright browser-install failure → skip (`test_e2e.py:539-545`). A rejected `--wait` is an `assert` failure, NOT a skip.

## Open Areas
- Whether `docker compose` is intended as the canonical backend (its `--wait` works) vs. supporting podman is a design intent question, not answerable from code. The compose-detection comment (`compose.yml:1`) lists all three as a "portability set," yet the `up --wait` flag is docker-only — this mismatch is the observed failure but the intended resolution is not specified in the repo.
- docker compose `--wait` behavior is asserted from general knowledge (docker is not installable in this environment to re-verify).
