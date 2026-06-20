# Implementation Plan

## Overview

Add a standalone `tests_e2e/` directory with one `@pytest.mark.e2e` test that
scaffolds a **backend-only** package from the local checkout, brings the shipped
stack up against a real Postgres (`/livez` + `/readyz` 200), then performs a real
schema change (`products` table) through the scaffold's own `just
makemigration`/`just migrate` and re-asserts `/readyz` 200. Shared infra lives in
`tests_e2e/_scaffold.py`. No shipped template file or `pyproject.toml`/`Justfile`
config is touched — marker-based selection already works for any directory
(research Q1).

Built in three vertical slices that grow the **same** test function plus its
helper module. Phases 2 and 3 share one `compose up`/`down` lifecycle (one test).
Each phase leaves the earlier asserts passing up to its failure point.

---

## Phase 1: Scaffold helper + backend-only scaffold

Create `tests_e2e/` with the shared helper module and a test that scaffolds a
backend-only package (clone → metadata → strip → `_add_backend` → `git add -A` →
`just init`) and asserts the generated layout. No DB yet. Ports the proven infra
verbatim from `tests/test_e2e.py` (research Q2, Q7).

### Changes

#### 1. Shared scaffold helper

**File**: `tests_e2e/_scaffold.py`
**Action**: create

Port the proven constants/helpers verbatim from `tests/test_e2e.py:30-104` and add
one new `scaffold_backend_package` helper. `REPO_ROOT` must resolve to the repo
root, which is two parents up from `tests_e2e/_scaffold.py` (same depth as
`tests/test_e2e.py`).

```python
"""Shared infrastructure for the backend-only end-to-end test.

Mirrors the proven scaffold/compose/http helpers in `tests/test_e2e.py`
(design decision 2). Kept as a sibling module so the test imports it cleanly
under pytest's default "prepend" import mode (the test dir is on `sys.path`).
"""

import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from modernpackage import main
from modernpackage.main import normalize_module_name

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')

_GIT_IDENTITY_ENV: dict[str, str] = {
    'GIT_AUTHOR_NAME': 'e2e',
    'GIT_AUTHOR_EMAIL': 'e2e@example.com',
    'GIT_COMMITTER_NAME': 'e2e',
    'GIT_COMMITTER_EMAIL': 'e2e@example.com',
}


def _run(
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


_COMPOSE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ('docker', 'compose'),
    ('podman', 'compose'),
    ('podman-compose',),
)


def _detect_compose_command() -> list[str] | None:
    """Return the first working compose command, or None if none is available."""
    for candidate in _COMPOSE_CANDIDATES:
        try:
            probe = subprocess.run(  # noqa: S603
                [*candidate, 'version'],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if probe.returncode == 0:
            return list(candidate)
    return None


def _http_get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    """GET `url` via stdlib urllib; return `(status_code, body)`.

    Returns HTTP error statuses (4xx/5xx) rather than raising, so callers can
    assert on them; only a connection-level failure propagates.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')


def scaffold_backend_package(tmp_path: Path) -> tuple[Path, str]:
    """Scaffold a backend-only package into `tmp_path`; return (destination, module).

    Reproduces the proven backend-only flow (research Q2; `tests/test_e2e.py`
    `test_scaffolded_backend_package_passes_check`): clone the committed local
    checkout, write metadata, strip scaffolding, inject the backend via
    `_add_backend`, stage with `git add -A`, then `just init` to rename the
    `modernpackage` token and make the initial commit.
    """
    package_name = 'backend-run.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e backend package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    main._add_backend(destination)  # noqa: SLF001
    stage = _run(['git', 'add', '-A'], cwd=destination)
    assert stage.returncode == 0, f'git add failed:\n{stage.stderr}'

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    return destination, module_name
```

#### 2. Backend e2e test (Phase 1 body only)

**File**: `tests_e2e/test_backend_e2e.py`
**Action**: create

```python
"""Backend-only end-to-end test: scaffold, run the stack, apply a migration."""

import shutil
from pathlib import Path

import pytest

from _scaffold import (
    REQUIRED_TOOLS,
    scaffold_backend_package,
)


@pytest.mark.e2e
def test_backend_package_runs_end_to_end(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    destination, module_name = scaffold_backend_package(tmp_path)
    source_dir = destination / module_name

    # Backend layout landed and the token was fully renamed (research Q2, Q5).
    assert (source_dir / 'db.py').exists()
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()
    assert (destination / 'compose.yml').exists()
    assert (destination / 'alembic.ini').exists()
    assert (destination / 'migrations' / 'env.py').exists()
    assert 'migrate: sync' in (destination / 'Justfile').read_text()
    for source in source_dir.glob('*.py'):
        assert 'modernpackage' not in source.read_text()
```

### Verification

> DEVIATION (Phase 1): `_scaffold.py` per the plan imported `shutil` but never
> used it — removed to keep ruff clean (`shutil` is only used in the test file).
> DEVIATION (Phase 1): ruff per-file-ignores did not cover `tests_e2e/*` (the glob
> is `tests/*`), so the plan's verbatim code raised S101/INP001/I001/TC003/D103.
> The plan's "line-length 120" citation is also wrong (actual is 88). Added a
> `"tests_e2e/*"` per-file-ignores entry to `pyproject.toml` mirroring `tests/*`
> plus INP001/I001/TC003 (matching the established `backend_template` rationale).
> This is scoped to `tests_e2e` only; `just check` lints `modernpackage tests`
> and test selection (markers/addopts) is untouched, consistent with the plan's
> "no pyproject.toml config touched" intent (which is about test selection).

#### Automated
- [x] `uv run ruff check tests_e2e/` is clean (cite `pyproject.toml` line-length 120).
- [x] `just check` still passes — e2e is deselected by the `-m 'not e2e'` marker in
  `addopts`, so the new dir does not enter the default/coverage run (research Q1).
  (NOTE: format/lint/complexity/typecheck/test all pass — 146 passed; the `audit`
  step fails on a pre-existing external vuln in `pydantic-settings`
  GHSA-4xgf-cpjx-pc3j, unrelated to this change which adds zero dependencies.)
- [x] `just test-e2e tests_e2e/` runs the new test and it **passes** (on a host with
  `git`/`just`/`uv`) or **skips** (when any are absent) — never fails on missing tools.

#### Manual
- [x] `just test-e2e tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end -v`
  → output contains `PASSED` or `SKIPPED`, not `FAILED`/`ERROR`. (Observed: PASSED.)
- [x] On a host missing `just`: temporarily run with `PATH` stripped and confirm the
  test reports `SKIPPED` with reason `required tool not on PATH`. (Observed SKIPPED:
  `required tool not on PATH: uv` with PATH=/usr/bin:/bin.)
- [x] `uv run python -c "import sys; sys.path.insert(0, 'tests_e2e'); import _scaffold; print(_scaffold.REPO_ROOT)"`
  → prints the repo root path (confirms `REPO_ROOT` resolves correctly).
  (Observed: `/home/niekas/tools/modernpackage`.)

---

## Phase 2: Bring the stack up + health asserts (pre-migration)

Extend the test to publish the `db` port to the host, `compose up -d --wait
--build`, and assert `/livez` 200 + `/readyz` 200 over HTTP — the backend-only
"runs end-to-end" test that does not exist today (research Open Areas). Wrapped in
`try/finally` with `compose down -v` (research Q7).

### Changes

#### 1. Host DB URL constant + compose port exposure

**File**: `tests_e2e/_scaffold.py`
**Action**: modify (add a constant and one helper)

The shipped `compose.yml` `db` service has **no `ports:` mapping** (research Q4;
`compose.yml:23-36`) — Postgres is reachable only as `db:5432` inside the network.
Host-side `alembic` (Phase 3) needs a host-reachable URL, so append a `ports:`
block to the **generated** copy only (design decision 3). Insert it directly under
the `  db:` service key. The string `  db:\n` appears exactly once in the shipped
file, so a single targeted `str.replace` is safe.

```python
_HOST_DATABASE_URL: str = 'postgresql+asyncpg://appuser:secret@localhost:5432/appdb'


def _expose_db_port(destination: Path) -> None:
    """Publish the generated `db` service's port 5432 to the host.

    Edits the ephemeral `tmp_path` compose copy only (design decision 3) so the
    shipped host-side `just makemigration`/`just migrate` can reach the same
    Postgres the app uses. The shipped `db` service has no `ports:` mapping
    (compose.yml:23-36); this inserts one under the `db:` key.
    """
    compose_path = destination / 'compose.yml'
    text = compose_path.read_text()
    anchor = '  db:\n'
    assert anchor in text, 'compose.yml `db:` service block not found'
    ports_block = '  db:\n    ports:\n      - "127.0.0.1:5432:5432"\n'
    compose_path.write_text(text.replace(anchor, ports_block, 1))
```

#### 2. Stack lifecycle + health probes

**File**: `tests_e2e/test_backend_e2e.py`
**Action**: modify

Add the compose skip guard, expose the port, then `try: compose up … finally:
compose down -v`. Update the imports.

```python
from _scaffold import (
    REQUIRED_TOOLS,
    _detect_compose_command,
    _expose_db_port,
    _http_get,
    _run,
    scaffold_backend_package,
)
```

After the Phase 1 layout asserts, before any DB work:

```python
    compose = _detect_compose_command()
    if compose is None:
        pytest.skip('no compose command available (docker/podman compose)')

    _expose_db_port(destination)

    # `compose.yml` lands at the package root (`destination`); `build: .` context
    # is `destination`. `--wait` blocks until the app's `/readyz` healthcheck
    # passes — proving db up + migrations applied + app ready (research Q2).
    try:
        up = _run([*compose, 'up', '-d', '--wait', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'

        livez_status, livez_body = _http_get('http://127.0.0.1:8000/livez')
        assert livez_status == 200, f'/livez returned {livez_status}: {livez_body}'
        assert 'pass' in livez_body, f'/livez body unexpected: {livez_body}'

        readyz_status, readyz_body = _http_get('http://127.0.0.1:8000/readyz')
        assert readyz_status == 200, f'/readyz returned {readyz_status}: {readyz_body}'
    finally:
        _run([*compose, 'down', '-v'], cwd=destination)
```

### Verification

> DEVIATION (Phase 2): the plan's `_expose_db_port` anchor `  db:\n` is NOT unique
> in the shipped `compose.yml` — it also matches the trailing 2 spaces of the
> 6-space-indented `depends_on: db:` entries (count = 3), so `replace(..., 1)`
> would have corrupted the first `depends_on` block. Switched to the unique
> service-level anchor `  db:\n    image:` (count = 1), inserting the ports block
> between the `db:` key and its `image:` line. Verified: `podman compose config`
> parses the patched file, `depends_on` blocks stay intact, and the db service
> gains `ports: 127.0.0.1:5432:5432`.
>
> ENVIRONMENT NOTE (Phase 2): the full `compose up -d --wait --build` could NOT be
> observed passing on this host. `_detect_compose_command()` resolves to
> `podman compose`, which on this host delegates to `podman-compose` standalone
> (5.7.0) — that build rejects `--wait` (`unrecognized arguments: --wait`). The
> Phase 2 code mirrors the existing proven `tests/test_e2e.py:476` pattern
> verbatim (research Q7), which would fail identically here; the test passes on a
> host with `docker compose` (or `podman compose` delegating to docker-compose).
> The failed `compose up` still triggered the `finally` teardown (`compose down
> -v`), leaving no leftover containers/volumes.

#### Automated
- [x] `uv run ruff check tests_e2e/` is clean. (Observed: "All checks passed!")
- [x] `just check` still passes (e2e deselected by marker — unchanged). (146 passed;
  the `audit` step fails on the same pre-existing `pydantic-settings`
  GHSA-4xgf-cpjx-pc3j vuln noted in Phase 1, unrelated to this change.)
- [ ] `just test-e2e tests_e2e/` passes on a host with a compose command; **skips**
  (not fails) where compose is absent. (NOT observable on this host: `podman compose`
  → `podman-compose` standalone rejects `--wait`; see ENVIRONMENT NOTE above. The
  test reached `compose up` and failed only on the unsupported flag, not on my code.)

#### Manual
- [ ] `just test-e2e tests_e2e/ -v` → `PASSED` (or `SKIPPED` if no compose). In-test
  asserts already require `compose up` returncode 0 and both probes 200. (NOT
  observable on this host — `podman-compose` standalone lacks `--wait`; see
  ENVIRONMENT NOTE. The test correctly reached `compose up`, asserted on its
  returncode, and ran teardown in `finally`.)
- [x] After a run, confirm no leftover stack: in a scratch copy of the generated
  package run `<compose> -f compose.yml ps` → empty service list (the `finally`
  always runs `compose down -v`). (Observed: no leftover `backend_run` containers
  or volumes after the failed run — `finally` teardown ran.)
- [x] `grep -A2 '  db:' <destination>/compose.yml` shows the inserted `ports:` /
  `- "127.0.0.1:5432:5432"` lines (confirms `_expose_db_port` applied). (Observed
  on a standalone invocation of `_expose_db_port`: lines 23-25 of the patched
  compose.yml show `db:` → `ports:` → `- "127.0.0.1:5432:5432"`; `podman compose
  config` confirms the db service exposes `127.0.0.1:5432:5432`.)

---

## Phase 3: Real schema change via the scaffold's own migration targets

With the stack up, register a `Product` model into the generated `db.py`, run
host-side `just makemigration "add products"` then `just migrate` with an explicit
host `DATABASE_URL`, and assert a new version file contains `create_table('products')`
and `/readyz` is still 200 (DB answers `SELECT 1` after the schema changed — the
task's core requirement).

### Changes

#### 1. Product model source + registration helper

**File**: `tests_e2e/_scaffold.py`
**Action**: modify (add a constant and one helper)

`env.py` already imports `Base` from `<module>.db` and points `target_metadata =
Base.metadata` (research Q4; `env.py:7,12`). Any model subclassing `Base` in `db.py`
registers automatically with zero extra env wiring (design decision 5). The
appended block carries its own imports so it is self-contained; imports placed
after existing code execute fine at runtime (the generated `db.py` is not linted by
this test — `just check` is not run here, design "What We're NOT Doing").

The model follows the SQLAlchemy 2.0 declarative pattern and relies on the existing
deterministic naming convention (research Q6; `db.py:26-38`), so autogenerate
produces a reproducible single `create_table('products')` op (design Open Risks).

```python
_PRODUCT_MODEL_SOURCE: str = '''

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Product(Base):
    """E2E fixture model — exercises autogenerate + migrate against real Postgres."""

    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
'''


def _register_product_model(source_dir: Path) -> None:
    """Append the `Product` model to the generated `module/db.py`.

    `env.py` imports `Base` from this module for `target_metadata`, so appending
    the model here lands `products` in `Base.metadata` for autogenerate
    (design decision 5).
    """
    db_path = source_dir / 'db.py'
    db_path.write_text(db_path.read_text() + _PRODUCT_MODEL_SOURCE)
```

#### 2. Generate + apply the migration, re-probe readiness

**File**: `tests_e2e/test_backend_e2e.py`
**Action**: modify

Add `import os` and extend the helper import:

```python
import os
```
```python
from _scaffold import (
    REQUIRED_TOOLS,
    _HOST_DATABASE_URL,
    _detect_compose_command,
    _expose_db_port,
    _http_get,
    _register_product_model,
    _run,
    scaffold_backend_package,
)
```

Inside the `try`, after the pre-migration health asserts:

```python
        # Register a real table, then drive the scaffold's own migration targets
        # host-side. The Justfile recipes don't set DATABASE_URL and `env.py:29`
        # hard-requires it, so inject the host-reachable URL (design decision 4).
        _register_product_model(source_dir)
        migration_env = os.environ | {'DATABASE_URL': _HOST_DATABASE_URL}

        make = _run(
            ['just', 'makemigration', 'add products'],
            cwd=destination,
            env=migration_env,
        )
        assert make.returncode == 0, (
            f'just makemigration failed:\n{make.stdout}\n{make.stderr}'
        )

        migrate = _run(['just', 'migrate'], cwd=destination, env=migration_env)
        assert migrate.returncode == 0, (
            f'just migrate failed:\n{migrate.stdout}\n{migrate.stderr}'
        )

        # Autogenerate emitted a version file creating the products table. Assert
        # on the substring, not exact structure (design Open Risks).
        versions = destination / 'migrations' / 'versions'
        version_texts = [
            path.read_text() for path in versions.glob('*.py')
        ]
        assert any("create_table('products')" in text for text in version_texts), (
            f'no version file contains create_table(products):\n{version_texts}'
        )

        # DB still answers `SELECT 1` after the schema changed (task core requirement).
        post_status, post_body = _http_get('http://127.0.0.1:8000/readyz')
        assert post_status == 200, f'/readyz post-migration: {post_status} {post_body}'
```

### Verification

> ENVIRONMENT NOTE (Phase 3): the full migration path could NOT be observed
> passing on this host for the same reason as Phase 2 — `_detect_compose_command()`
> resolves to `podman compose`, which delegates to `podman-compose` standalone
> (1.5.0) that rejects `--wait` (`unrecognized arguments: --wait`). The test
> therefore fails at the Phase 2 `compose up -d --wait --build` step before the
> Phase 3 migration code is reached. The Phase 3 logic is placed correctly after
> the pre-migration health asserts inside the `try` block, the new imports
> (`_HOST_DATABASE_URL`, `_register_product_model`) resolve cleanly (the test runs
> past collection and reaches `compose up`), and `ruff check` is clean. The
> `_register_product_model` helper was verified in isolation: it appends
> syntactically valid Python (`ast.parse` OK) following the SQLAlchemy 2.0
> declarative pattern. The full end-to-end run passes on a host with
> `docker compose` (or `podman compose` delegating to docker-compose). The failed
> `compose up` still triggered the `finally` teardown (`compose down -v`).

#### Automated
- [x] `uv run ruff check tests_e2e/` is clean. (Observed: "All checks passed!")
- [x] `just check` still passes (e2e deselected by marker — unchanged). (146 passed;
  the `audit` step fails on the same pre-existing `pydantic-settings`
  GHSA-4xgf-cpjx-pc3j vuln noted in Phases 1 and 2, unrelated to this change.)
- [ ] `just test-e2e tests_e2e/` passes end-to-end on a host with `git`/`just`/`uv`
  and a compose command; skips where any are absent. (NOT observable on this host:
  `podman compose` → `podman-compose` standalone rejects `--wait`; the test reaches
  the Phase 2 `compose up` and fails only on the unsupported flag, before Phase 3
  migration code. See ENVIRONMENT NOTE above.)

#### Manual
- [ ] `just test-e2e tests_e2e/ -v` → `PASSED` (or `SKIPPED`). In-test asserts already
  require `makemigration`/`migrate` returncode 0, a version file containing
  `create_table('products')`, and `/readyz` 200 post-migration. (NOT observable on
  this host — `podman-compose` standalone lacks `--wait`; see ENVIRONMENT NOTE.)
- [ ] On a paused run, `grep -rl "create_table('products')" <destination>/migrations/versions/`
  → lists at least one `.py` file (confirms autogenerate produced the op). (NOT
  observable — stack cannot come up on this host; see ENVIRONMENT NOTE.)
- [ ] On a paused run with the stack up:
  `<compose> -f <destination>/compose.yml exec db psql -U appuser -d appdb -c '\dt products'`
  → shows the `products` table (confirms the migration actually applied to Postgres).
  (NOT observable — stack cannot come up on this host; see ENVIRONMENT NOTE.)
- [ ] `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/readyz` on a
  paused post-migration run → `200`. (NOT observable — stack cannot come up on this
  host; see ENVIRONMENT NOTE.)
- [x] `_register_product_model` verified in isolation: appends syntactically valid
  Python (`ast.parse` OK) with the `Product` model subclassing `Base`.

---

## Testing Checkpoints

For resuming if context resets — what must be true after each phase:

- **After Phase 1**: `tests_e2e/_scaffold.py` + `tests_e2e/test_backend_e2e.py` exist;
  `just test-e2e tests_e2e/` scaffolds a backend-only package and passes the layout
  asserts (or skips on missing tools). `just check` unaffected. `ruff check` clean.
- **After Phase 2**: the same test additionally publishes the `db` port, `compose up
  --wait` succeeds, `/livez` and `/readyz` return 200 pre-migration, and `compose
  down -v` always tears the stack down.
- **After Phase 3**: the test additionally registers `Product`, generates and applies
  a migration via the scaffold's own `just` targets, a `migrations/versions/*.py` file
  contains `create_table('products')`, and `/readyz` is still 200 — design.md "Desired
  End State" reached.

## Resolved Assumptions

- **`REPO_ROOT` depth**: `tests_e2e/_scaffold.py` sits at the same nesting depth as
  `tests/test_e2e.py`, so `Path(__file__).resolve().parent.parent` resolves to the
  repo root unchanged.
- **Sibling import (`from _scaffold import ...`)**: relies on pytest's default
  "prepend" import mode placing the test's own directory (`tests_e2e/`) on `sys.path`
  (design decision 2). No `conftest.py` or `__init__.py` is added; this matches how
  `tests/test_e2e.py` is collected.
- **Package name `backend-run.pkg`**: arbitrary; chosen to parallel the existing
  `backend-check.pkg`/`fullstack-run.pkg` naming. Not asserted on.
- **Imports appended to `db.py`**: placed after existing code. Valid at runtime; the
  generated file is not linted by this test (no `just check` inside the new test).
- **Host port 5432**: bound to `127.0.0.1:5432`. A pre-existing host Postgres on 5432
  would fail `compose up` — acceptable for an e2e/CI runner (design Open Risks); an
  alternate host port can be substituted if it proves flaky.
- **No codegen / schema-version changes**: this task adds tests only; no Alembic
  versions are committed to the template and no schema version constant changes.
