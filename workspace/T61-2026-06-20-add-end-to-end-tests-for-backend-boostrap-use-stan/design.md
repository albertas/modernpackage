# Design Discussion

## Current State

- E2E tests live in `tests/test_e2e.py`, mixed with the package's other tests under
  `tests/`. Each is marked `@pytest.mark.e2e` (`tests/test_e2e.py:189,424,…`).
- Selection is by **marker, not path**: default `addopts` carries `-m 'not e2e'`
  and a 95% coverage gate on `modernpackage` (`pyproject.toml:40`); `just test-e2e`
  flips to `-m e2e --no-cov` (`Justfile:17-18`). `norecursedirs` only excludes the
  two template dirs (`pyproject.toml:41`).
- The closest existing example is `test_fullstack_package_runs_end_to_end`
  (`tests/test_e2e.py:424-551`): it scaffolds, `compose up -d --wait --build`,
  asserts host-side `/livez` + `/readyz` over HTTP, then exercises the frontend.
  There is **no backend-only "runs end-to-end" test** and **no test that performs a
  schema change**.
- The backend template ships migration infra but **no concrete model**: `Base` +
  deterministic naming convention live in `backend_template/modernpackage/db.py:35-38`;
  `migrations/env.py:7,12` points `target_metadata = Base.metadata`; `versions/`
  holds only `.gitkeep`. A `grep` for `Mapped|mapped_column|__tablename__` returns
  nothing (research Q6).
- Migration Justfile targets are injected by `_add_backend` from `main.py:579-588`:
  `migrate → uv run alembic upgrade head`, `makemigration message → uv run alembic
  revision --autogenerate -m "{{message}}"`, `migration-check → uv run alembic check`.
  These run `uv run alembic` **on the host**, not in a container.
- **Critical constraint**: `compose.yml:23-36` defines `db` with **no `ports:`
  mapping** — Postgres is reachable only inside the compose network as `db:5432`.
  `env.py:29` does `config_section['sqlalchemy.url'] = os.environ['DATABASE_URL']`
  and connects a live async engine for autogenerate, so host-side `alembic` needs a
  host-reachable URL.

## Desired End State

A new standalone E2E test that:
1. Scaffolds a **backend-only** package from the local checkout (no frontend).
2. Brings the shipped stack up against a real Postgres (`compose up --wait`) and
   asserts the health check reports DB connectivity: `/livez` 200 + `/readyz` 200.
3. Introduces a real `products` table, generates a migration via the scaffold's own
   `just makemigration`, applies it via `just migrate`, and asserts `/readyz` is
   still 200 after the DB schema changed.

Verify it's correct: `just test-e2e tests_e2e/` selects and passes the new test on a
host with `git`, `just`, `uv`, and a compose command; it skips (not fails) where
those are absent. `just check` is unaffected (e2e excluded by marker). A new file
appears under the scaffold's `migrations/versions/` containing
`create_table('products')`.

## Patterns to Follow

- **Scaffold flow** (clone → metadata → strip → `_add_backend` → `git add -A` →
  `just init`): `tests/test_e2e.py:199-220`. Backend-only uses `_add_backend` +
  manual `git add -A` (`main.py:995`), *not* `_inject_templates`.
- **Skip guards**: `for tool in REQUIRED_TOOLS: shutil.which(...) → pytest.skip`
  (`tests/test_e2e.py:191-193`).
- **Compose detection**: `_detect_compose_command()` probing docker/podman variants
  (`tests/test_e2e.py:67-88`); `compose is None → pytest.skip`.
- **Stack lifecycle**: `try: compose up -d --wait --build … finally: compose down -v`
  (`tests/test_e2e.py:475-550`) — always tears down with volume removal.
- **HTTP probe**: stdlib `_http_get` returning `(status, body)`
  (`tests/test_e2e.py:91-104`) — avoids an httpx dependency in the outer env.
- **Subprocess helper + git identity**: `_run(..., check=False, capture_output=True,
  text=True)` with `os.environ | _GIT_IDENTITY_ENV` (`tests/test_e2e.py:45-57,37-42`).
- **Model definition pattern**: SQLAlchemy 2.0 declarative subclassing `Base` with
  `__tablename__` + `Mapped[...] = mapped_column(...)`, relying on the existing
  naming convention (`db.py:26-38`). No example exists, so we author the canonical one.
- **Pattern to NOT introduce**: do not add a path-based pytest selector or touch
  `norecursedirs`/`addopts` — marker-based selection already works for any directory
  (research Q1). Do not modify the shipped `compose.yml`/`env.py` template files.

## Design Decisions

1. **Standalone directory `tests_e2e/`** — new top-level dir holding the new test,
   satisfying "separate from the existing package unit-test layout." No config change
   needed: the test keeps `@pytest.mark.e2e`, so the default run still deselects it and
   `just test-e2e` (marker-based) still finds it (research Q1). Existing
   `tests/test_e2e.py` is left untouched (surgical; don't refactor working code).
2. **Shared helpers in `tests_e2e/_scaffold.py`** — house `_run`,
   `_detect_compose_command`, `_http_get`, the constants, and a
   `scaffold_backend_package(tmp_path) -> (destination, module_name)` that runs the
   clone→init flow. The test imports them (pytest "prepend" import mode puts the test
   dir on `sys.path`, so a sibling module imports cleanly). Chosen over importing from
   `tests/test_e2e.py` (fragile cross-package import) and over duplicating inline.
3. **Expose the DB to the host via a test-side compose edit** — after scaffolding,
   the test appends `ports: ["127.0.0.1:5432:5432"]` to the *generated* `db` service
   before `compose up`. This is the minimum change that lets the shipped host-side
   `just makemigration`/`just migrate` reach the same Postgres the app uses. Chosen
   over: shipping a published port in the template (changes production-facing behavior,
   out of scope) and running alembic inside the container (the container lacks `just`,
   and autogenerated version files written in-container are lost — they must land in the
   host package dir).
4. **Run migration targets host-side with an explicit `DATABASE_URL`** — invoke
   `just makemigration "add products"` and `just migrate` with
   `env = os.environ | {'DATABASE_URL': 'postgresql+asyncpg://appuser:secret@localhost:5432/appdb'}`.
   The Justfile recipes don't set `DATABASE_URL`, and `env.py:29` hard-requires it.
   Same Postgres instance as the app, reached over the published localhost port.
5. **Register the model by appending to the generated `module/db.py`** — write the
   `Product` model (plus its `Mapped`/`mapped_column` imports) into the renamed
   `db.py`, which `env.py` already imports for `Base`. Guarantees the table lands in
   `Base.metadata` for autogenerate with zero extra env wiring. Chosen over a new
   models module (would require also editing `env.py` to import it).
6. **Assertions** — after the schema change: a new `migrations/versions/*.py` exists
   containing `create_table('products')` (proves autogenerate ran), and `/readyz`
   returns 200 (proves the DB still answers `SELECT 1` post-migration, the task's core
   requirement). `/livez` + `/readyz` 200 are also asserted pre-migration.

## What We're NOT Doing

- Not modifying any shipped template file (`backend_template/compose.yml`, `env.py`,
  `db.py`) or adding an example model to the template — only the test's ephemeral
  `tmp_path` copy is edited.
- Not touching `pyproject.toml` markers/`addopts`/`norecursedirs` or the `Justfile`.
- Not moving or refactoring the existing `tests/test_e2e.py`.
- Not exercising the frontend, API-client generation, or Playwright.
- Not asserting row-level data or running `migration-check`/`just check` inside the
  new test (health pass + migration file are sufficient).

## Open Risks

- **Host port 5432 collision**: a Postgres already listening on the host's 5432 would
  fail `compose up`. Acceptable for an e2e/CI runner; could bind an alternate host port
  if it proves flaky.
- **Host asyncpg availability**: `just makemigration` depends on `sync`, so `uv sync`
  installs the backend deps (incl. asyncpg) into the package venv before alembic runs —
  expected to work, but adds minutes and needs network (mirrors sibling-test caveats).
- **Autogenerate stability**: relies on the deterministic naming convention
  (`db.py:26-38`) and `compare_type=True` (`env.py:19`) producing a single
  `create_table('products')` op; assert on the substring, not exact file structure.
- **Helper drift**: `_scaffold.py` mirrors infra logic currently in
  `tests/test_e2e.py`. A future cleanup could extract a shared module both import;
  out of scope here to keep changes surgical.
- **Compose-file edit brittleness**: appending a `ports:` block by text manipulation
  assumes the shipped `db` service shape; a structural YAML edit (parse/dump) is more
  robust if the template changes.
