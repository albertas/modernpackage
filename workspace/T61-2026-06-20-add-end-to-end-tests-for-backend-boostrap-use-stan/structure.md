# Structure Outline

## Approach

Add a standalone `tests_e2e/` top-level dir holding one new `@pytest.mark.e2e`
test that scaffolds a **backend-only** package from the local checkout, brings
the shipped stack up against a real Postgres, then performs a real schema change
through the scaffold's own `just makemigration`/`just migrate`. Shared infra
lives in a sibling `tests_e2e/_scaffold.py`. No shipped template file, no
`pyproject.toml`/`Justfile` config is touched (marker-based selection already
works for any directory — research Q1).

The test is built in three vertical slices. Each slice grows the **same** test
function plus its helper module, and each leaves a runnable, independently
valuable e2e test behind. Slices are sequenced so a later failure still leaves
the earlier slices passing.

---

## Phase 1: Scaffold helper + backend-only scaffold

Create `tests_e2e/` with a shared helper module and a test that scaffolds a
backend-only package (clone → metadata → strip → `_add_backend` → `git add -A` →
`just init`) and asserts the generated layout — no DB yet. Establishes the
import seam and reproduces the proven scaffold flow (research Q2).

**Files**: `tests_e2e/_scaffold.py` (new), `tests_e2e/test_backend_e2e.py` (new)

**Key changes**:
- `tests_e2e/_scaffold.py` — port the proven infra constants/helpers verbatim:
  - `REPO_ROOT: Path`, `REQUIRED_TOOLS: tuple[str, ...]`, `_GIT_IDENTITY_ENV: dict[str, str]`
  - `_run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]`
  - `_detect_compose_command() -> list[str] | None`
  - `_http_get(url: str, timeout: float = 30.0) -> tuple[int, str]`
  - `scaffold_backend_package(tmp_path: Path) -> tuple[Path, str]` — runs the full
    backend-only scaffold flow; returns `(destination, module_name)`. New.
- `tests_e2e/test_backend_e2e.py` — `@pytest.mark.e2e def
  test_backend_package_runs_end_to_end(tmp_path: Path) -> None`; for now only the
  required-tool skip guard, `scaffold_backend_package(...)`, and layout asserts.

**Verify**: `just test-e2e tests_e2e/` passes (or skips where `git`/`just`/`uv`
absent); inside the test assert `(destination / module_name / 'db.py').exists()`,
`(destination / 'compose.yml').exists()`, `'migrate: sync'` in the generated
`Justfile`, and no `modernpackage` token remains in `destination/module_name/*.py`.
`just check` still passes (e2e deselected by marker — research Q1).
`uv run ruff check tests_e2e/` is clean.

---

## Phase 2: Bring the stack up + health asserts (pre-migration)

Extend the test to publish the `db` port to the host, `compose up --wait --build`,
and assert `/livez` 200 and `/readyz` 200 over HTTP — the backend-only "runs
end-to-end" test that does not exist today (research Open Areas). Wrapped in
`try/finally` with `compose down -v`.

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_backend_e2e.py`

**Key changes**:
- `tests_e2e/_scaffold.py`:
  - `_HOST_DATABASE_URL: str = 'postgresql+asyncpg://appuser:secret@localhost:5432/appdb'`
  - `_expose_db_port(destination: Path) -> None` — append
    `ports: ["127.0.0.1:5432:5432"]` to the generated `compose.yml` `db` service
    (test-side edit of the `tmp_path` copy only — design decision 3). New.
- `tests_e2e/test_backend_e2e.py`: add compose skip guard
  (`_detect_compose_command() is None → pytest.skip`), call `_expose_db_port(...)`,
  then `try: compose up -d --wait --build … finally: compose down -v`. Assert
  `_http_get('http://127.0.0.1:8000/livez') == (200, body)` with `'pass'` in body,
  and `_http_get('.../readyz')[0] == 200`.

**Verify**: `just test-e2e tests_e2e/` brings the stack up and passes on a host
with a compose command; skips (not fails) where compose is absent. Agent check:
test asserts `compose up` returncode 0 and both probes 200; `finally` always runs
`compose down -v` (confirm no leftover containers via
`docker compose -f <destination>/compose.yml ps` returning empty / equivalent).

---

## Phase 3: Real schema change via the scaffold's own migration targets

With the stack up, register a `Product` model into the generated `db.py`, run
host-side `just makemigration "add products"` then `just migrate` with an explicit
host `DATABASE_URL`, and assert a new version file containing
`create_table('products')` exists and `/readyz` is still 200 (DB answers
`SELECT 1` after the schema changed — the task's core requirement).

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_backend_e2e.py`

**Key changes**:
- `tests_e2e/_scaffold.py`:
  - `_PRODUCT_MODEL_SOURCE: str` — canonical SQLAlchemy 2.0 declarative model text
    (`Mapped`/`mapped_column` imports + `class Product(Base)` with
    `__tablename__ = 'products'` and a couple of typed columns; relies on the
    existing naming convention — research Q4/Q6).
  - `_register_product_model(source_dir: Path) -> None` — append `_PRODUCT_MODEL_SOURCE`
    to the renamed `module/db.py`, which `env.py` already imports for `Base`
    (design decision 5). New.
- `tests_e2e/test_backend_e2e.py` (inside the `try`, after health asserts): call
  `_register_product_model(destination / module_name)`; run `just makemigration
  "add products"` and `just migrate` with `env = os.environ | {'DATABASE_URL':
  _HOST_DATABASE_URL}`; re-probe `/readyz`.

**Verify**: `just test-e2e tests_e2e/` passes. Agent checks (all asserted in-test):
`makemigration`/`migrate` returncodes 0; at least one file in
`destination/migrations/versions/*.py` contains the substring
`create_table('products')` (assert on substring, not exact structure — design Open
Risks); `_http_get('.../readyz')[0] == 200` after migration.

---

## Testing Checkpoints

Useful for resuming if context resets — what must be true after each phase:

- **After Phase 1**: `tests_e2e/_scaffold.py` and `tests_e2e/test_backend_e2e.py`
  exist; `just test-e2e tests_e2e/` scaffolds a backend-only package and passes
  layout asserts (or skips on missing tools). `just check` unaffected. Lint clean.
- **After Phase 2**: the same test additionally publishes the `db` port,
  `compose up --wait` succeeds, `/livez` and `/readyz` return 200 pre-migration,
  and `compose down -v` always tears the stack down.
- **After Phase 3**: the test additionally registers `Product`, generates and
  applies a migration via the scaffold's own `just` targets, a
  `migrations/versions/*.py` file contains `create_table('products')`, and
  `/readyz` is still 200 — proving the DB serves `SELECT 1` after a real schema
  change. End state of design.md "Desired End State" reached.

**Note on slicing**: Phases 2 and 3 share one expensive compose lifecycle, so they
grow the same test function (one `compose up`/`down`) rather than splitting into
two tests. Each phase is still independently verifiable via the in-test asserts it
adds, and a Phase 3 failure leaves the Phase 1–2 asserts passing within the same
run up to the failure point.
