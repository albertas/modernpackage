# Implementation Plan

## Overview

Add a store-true `--backend`/`--fastapi` flag to the `modernpackage` scaffolder that injects a
working async FastAPI service (app factory + lifespan engine/sessionmaker, async SQLAlchemy 2.0 +
asyncpg DI, `/livez` + `/readyz` health probes, Alembic async migrations, `Containerfile` +
`compose.yml`, and `just migrate`/`makemigration`/`migration-check` recipes) into the generated
package. Without the flag, output is byte-for-byte identical to today.

## Key cross-cutting decisions (resolved here, apply to every phase)

These resolve open points the structure left implicit. They are load-bearing — read before
implementing any phase.

1. **`backend_template/` MUST be added to `_SCAFFOLDING_PATHS_TO_DELETE` (Phase 2).** The
   scaffolder clones `_TEMPLATE_REPOSITORY_URL` (the whole modernpackage repo), which *will now
   contain* `backend_template/`. Every generated package — flag or no flag — clones it. To keep the
   no-flag path byte-for-byte identical, `_strip_scaffolding` must always delete the cloned
   `backend_template/`. `_add_backend` does **not** read the clone's copy; it copies from
   `_BACKEND_TEMPLATE_DIR` (the installed/source package's own `backend_template/`), a different
   path. So: strip removes the clone's `backend_template/`; `_add_backend` (only when `--backend`)
   re-injects the template files at the clone root.

2. **The `git add -A` Popen call is gated on `backend=True`.** This deviates from the structure's
   note about "updating existing Popen side_effect sequences": because the call only fires for
   `--backend`, the existing no-flag `Popen` tests (`test_main.py:290-407`, all `backend=False`)
   keep `call_count == 3` and need **no changes**. Only new backend tests assert the 4-call
   sequence (clone → git add → just init → just check). This is simpler and guarantees the no-flag
   path stays identical. (Justification recorded for the structure's "known mechanical change".)

3. **The backend ships its own tests AND test-only dep (`httpx`) so generated `just check` stays
   green.** The generated package's `just check` runs `ruff check <module> tests`,
   `mypy <module> tests`, and `pytest --cov=<module> --cov-fail-under=95.0`. Therefore
   `backend_template/modernpackage/{app,db,health}.py` and `backend_template/tests/test_app.py`
   **must pass ruff `ALL` (minus per-file `S101`,`D` for tests), mypy `strict`, McCabe ≤ 8,
   line-length 88, single quotes**, and the backend tests must cover ≥ 95% of the injected modules.
   `migrations/`, `alembic.ini`, `Containerfile`, `compose.yml`, `.dockerignore` live at the clone
   root (siblings of `<module>/` and `tests/`), so they are **not** linted, type-checked, or
   coverage-measured — they only need to be valid and carry the `modernpackage` token where they
   reference the package.

4. **Backend tests avoid `pytest-asyncio` and `asgi-lifespan`.** Async functions are exercised with
   `asyncio.run(...)` inside plain sync tests; HTTP routes are exercised with
   `fastapi.testclient.TestClient` (which runs lifespan via its context manager and needs `httpx`).
   So the only added test dep is `httpx` (appended to the `dev` dependency-group). Runtime deps go
   in `[project.dependencies]`.

5. **Migration recipes are appended to the clone's existing `Justfile`, not overwritten.** Copytree
   cannot merge a recipe into an existing file, and overwriting would destroy the package's `init`,
   `check`, `test`, … recipes. `_add_backend` appends a small `_BACKEND_RECIPES` constant (~12
   lines) via line surgery. The recipes are standalone (NOT added to `check`'s chain — they need a
   live DB).

---

## Phase 1: CLI flag plumbing + dry-run

Add the `--backend`/`--fastapi` store-true flag and thread it end-to-end (parse → `main` →
`init_new_package` → dry-run). No injection yet; with the flag set, `init_new_package` calls a no-op
`_add_backend` placeholder so the wiring is provable.

### Changes

#### 1. Add the flag to `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify

Add after the `--dry-run` argument block (`main.py:357-362`), mirroring the `-v/--version` alias
shape:

```python
    parser.add_argument(
        '--backend',
        '--fastapi',
        help='Include a FastAPI backend (app, async DB, migrations, container).',
        action='store_true',
        default=False,
    )
```

argparse derives `dest='backend'` from the first long option; `--fastapi` sets the same dest.

#### 2. Add the no-op placeholder
**File**: `modernpackage/main.py`
**Action**: create (add new module-private function, e.g. just before `init_new_package`)

```python
def _add_backend(package_path: Path) -> None:
    """Inject the FastAPI backend template into a generated package.

    Placeholder in Phase 1 (wiring only); implemented in Phase 2.
    """
```

In Phase 1 the body is a single `# noqa`-free statement that satisfies ruff (a docstring-only body
is allowed; no `pass` needed because the docstring is the body). If ruff flags an empty function,
keep just the docstring.

#### 3. Thread `backend` through `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify (`init_new_package`, `main.py:786-880`)

- Add keyword-only param to the signature (function already has `# noqa: PLR0913`):
  ```python
      dry_run: bool = False,
      backend: bool = False,
  ) -> int:
  ```
- In the dry-run branch, pass `backend=backend` to `_print_dry_run_plan`.
- After `_strip_scaffolding(new_package_path)` (`main.py:838`) and before the `just init` block, add:
  ```python
      if backend:
          _add_backend(new_package_path)
  ```
  (The `git add -A` staging call is added in Phase 2, inside this same `if backend:` block.)

#### 4. Thread `backend` through the dry-run formatter/printer
**File**: `modernpackage/main.py`
**Action**: modify (`_format_dry_run_plan` `main.py:599-635`, `_print_dry_run_plan` `main.py:638-659`)

- `_format_dry_run_plan`: add keyword-only `backend: bool = False` (default keeps existing direct
  test `test_format_dry_run_plan_reports_known_actions` at `test_main.py:1498` valid). Append one
  line after the version-reset line:
  ```python
      lines.append(f'  run just init: reset version to {_RESET_VERSION}')
      if backend:
          lines.append('  add FastAPI backend (app, migrations, container, recipes)')
      return '\n'.join(lines)
  ```
- `_print_dry_run_plan`: add `backend: bool = False` keyword-only param and forward it to
  `_format_dry_run_plan(...)`.

#### 5. Pass the flag from `main()`
**File**: `modernpackage/main.py`
**Action**: modify (`main.py:890-900`)

```python
            return init_new_package(
                package_name=parsed_args.package_name,
                ...
                dry_run=parsed_args.dry_run,
                backend=parsed_args.backend,
            )
```

#### 6. Tests
**File**: `tests/test_main.py`
**Action**: modify (add tests near the existing flag/dry-run tests)

```python
def test_parse_args_backend_flag() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--backend']):
        result = parse_args()
    assert result.backend is True


def test_parse_args_fastapi_alias_sets_backend() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--fastapi']):
        result = parse_args()
    assert result.backend is True


def test_parse_args_backend_defaults_false() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.backend is False


def test_format_dry_run_plan_announces_backend() -> None:
    plan = _format_dry_run_plan(
        'foo',
        Path('/tmp/foo'),  # noqa: S108
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
        backend=True,
    )
    assert 'add FastAPI backend' in plan


def test_format_dry_run_plan_omits_backend_by_default() -> None:
    plan = _format_dry_run_plan(
        'foo',
        Path('/tmp/foo'),  # noqa: S108
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert 'add FastAPI backend' not in plan


def test_init_new_package_invokes_add_backend_when_flag_set() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend') as add_backend_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage', backend=True)
    add_backend_mock.assert_called_once_with(Path.cwd() / 'mypackage')
```

Add `_add_backend` to the imports from `modernpackage.main` at the top of `test_main.py`.

### Verification
#### Automated
- [x] `just test` passes (new flag/alias/dry-run tests green; existing suite unchanged).
- [x] `just check-complexity` passes (`init_new_package` McCabe still ≤ 8 after the one new branch).
- [x] `just lint` and `just typecheck` pass.

#### Manual
- [x] `uv run modernpackage foo --backend --dry-run` exits 0 and stdout contains
      `add FastAPI backend` — verify:
      `uv run modernpackage foo --backend --dry-run | grep -q 'add FastAPI backend'`
- [x] `uv run modernpackage foo --fastapi --dry-run | grep -q 'add FastAPI backend'` (alias).
- [x] No-flag dry-run does NOT announce the backend:
      `uv run modernpackage foo --dry-run | grep -qv 'add FastAPI backend'`
      (i.e. `! uv run modernpackage foo --dry-run | grep -q 'add FastAPI backend'`).

---

## Phase 2: Injection mechanism + FastAPI app (core slice)

Build the real `_add_backend`: copy `backend_template/` into the clone, append runtime deps + the
`httpx` test dep, and stage the copied files with `git add -A` before `just init`. Ship a working
FastAPI app **and its own tests** so the generated package clears `--cov-fail-under=95.0`. Add
`backend_template` to the always-delete strip list. This is the first phase that produces a runnable
`--backend` package.

### Changes

#### 1. Backend app: async DB layer
**File**: `backend_template/modernpackage/db.py`
**Action**: create

```python
"""Async SQLAlchemy engine, session factory, and FastAPI session dependency."""

import os
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Default targets the compose `db` service; overridden via env in real deploys.
_DEFAULT_DATABASE_URL = 'postgresql+asyncpg://appuser:secret@db:5432/appdb'

# Deterministic constraint names so Alembic autogenerate stays reproducible.
_NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base carrying the shared, deterministic metadata."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


def database_url() -> str:
    """Return the configured database URL (env `DATABASE_URL` or compose default)."""
    return os.environ.get('DATABASE_URL') or _DEFAULT_DATABASE_URL


def create_engine() -> AsyncEngine:
    """Create the async engine (lazy — opens no connection until first use)."""
    return create_async_engine(database_url())


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one `AsyncSession` per request from the app-state session factory."""
    sessionmaker = cast(
        'async_sessionmaker[AsyncSession]', request.app.state.sessionmaker
    )
    async with sessionmaker() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
```

Note: the `cast` keeps mypy strict happy (Starlette `app.state` attribute access is `Any`).

#### 2. Backend app: health probes
**File**: `backend_template/modernpackage/health.py`
**Action**: create

```python
"""Kubernetes-style liveness and readiness probes."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter()

_READINESS_TIMEOUT_SECONDS = 2.0


async def database_ready(request: Request) -> bool:
    """Return True when a `SELECT 1` succeeds within the readiness timeout."""
    engine: AsyncEngine = request.app.state.engine
    try:
        async with asyncio.timeout(_READINESS_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text('SELECT 1'))
    except Exception:  # noqa: BLE001 - any failure means not-ready
        return False
    return True


@router.get('/livez')
async def livez() -> dict[str, str]:
    """Liveness probe — never touches the database."""
    return {'status': 'pass'}


@router.get('/readyz')
async def readyz(
    ready: Annotated[bool, Depends(database_ready)],
) -> JSONResponse | dict[str, str]:
    """Readiness probe — 200 when the DB answers, 503 otherwise."""
    if not ready:
        return JSONResponse(
            {'status': 'fail'},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return {'status': 'pass'}
```

#### 3. Backend app: factory + lifespan
**File**: `backend_template/modernpackage/app.py`
**Action**: create

```python
"""FastAPI application factory with async engine lifespan management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from modernpackage.db import create_engine
from modernpackage.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create engine + session factory on startup; dispose engine on shutdown."""
    engine = create_engine()
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(lifespan=lifespan)
    app.include_router(health_router)
    return app
```

All three modules use the literal `modernpackage` token in imports so the `just init` rename sed
rewrites them to `<module>`.

#### 4. Backend tests (coverage-critical — ≥95% of the three modules)
**File**: `backend_template/tests/test_app.py`
**Action**: create

```python
import asyncio
from types import SimpleNamespace
from typing import cast

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from modernpackage.app import create_app
from modernpackage.db import create_engine, get_db
from modernpackage.health import database_ready


class _FakeConnection:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    async def __aenter__(self) -> '_FakeConnection':
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        if self._fail:
            raise RuntimeError('db down')


class _FakeEngine:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    def connect(self) -> _FakeConnection:
        return _FakeConnection(fail=self._fail)


def _request_with_engine(*, fail: bool) -> Request:
    state = SimpleNamespace(engine=_FakeEngine(fail=fail))
    return cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))


def test_livez_returns_pass() -> None:
    with TestClient(create_app()) as client:
        response = client.get('/livez')
    assert response.status_code == 200
    assert response.json() == {'status': 'pass'}


def test_readyz_pass_when_database_ready() -> None:
    app = create_app()
    app.dependency_overrides[database_ready] = lambda: True
    with TestClient(app) as client:
        response = client.get('/readyz')
    assert response.status_code == 200
    assert response.json() == {'status': 'pass'}


def test_readyz_fail_when_database_unavailable() -> None:
    app = create_app()
    app.dependency_overrides[database_ready] = lambda: False
    with TestClient(app) as client:
        response = client.get('/readyz')
    assert response.status_code == 503
    assert response.json() == {'status': 'fail'}


def test_database_ready_true_on_successful_select() -> None:
    assert asyncio.run(database_ready(_request_with_engine(fail=False))) is True


def test_database_ready_false_on_error() -> None:
    assert asyncio.run(database_ready(_request_with_engine(fail=True))) is False


def test_get_db_yields_session() -> None:
    async def _run() -> object:
        engine = create_engine()
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        request = cast(
            Request,
            SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
                sessionmaker=sessionmaker,
            ))),
        )
        generator = get_db(request)
        session = await anext(generator)
        await generator.aclose()
        await engine.dispose()
        return session

    assert asyncio.run(_run()) is not None
```

This exercises: `create_app`/lifespan startup+shutdown (TestClient context), `livez`, `readyz`
(both branches via override), `database_ready` (both branches via fake engine — no live DB),
`get_db` (yields a session without connecting), and `database_url`/`create_engine`/`Base` (on
import). No real Postgres is contacted (SQLAlchemy async engine/session are lazy; the fake engine
covers the `SELECT 1` path).

#### 5. `_add_backend` real implementation + helpers
**File**: `modernpackage/main.py`
**Action**: modify

Add module constants (near the other module-level constants, e.g. after `_README_STUB`):

```python
# Top-level template tree copied into a generated package by `_add_backend`.
# Resolved relative to this file so it works from a source checkout and from an
# installed wheel (shipped as package data via [tool.hatch.build] include).
_BACKEND_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / 'backend_template'

# Runtime dependencies appended to the generated package's [project.dependencies]
# (PEP 621 — these are service runtime deps, not dev tooling). Lower bounds only.
_BACKEND_DEPENDENCIES: tuple[str, ...] = (
    'fastapi>=0.115',
    'sqlalchemy[asyncio]>=2.0',
    'asyncpg>=0.30',
    'alembic>=1.14',
    'uvicorn>=0.34',
)

# Test-only dependency appended to the dev dependency-group: TestClient needs httpx.
_BACKEND_DEV_DEPENDENCIES: tuple[str, ...] = ('httpx',)
```

Replace the Phase-1 placeholder `_add_backend` body:

```python
def _add_backend(package_path: Path) -> None:
    """Copy the FastAPI backend template into a generated package and wire its deps.

    Copies `_BACKEND_TEMPLATE_DIR` over the clone (merging into existing
    `modernpackage/` and `tests/`), then appends backend runtime/dev dependencies
    to the cloned pyproject.toml. Copied files carry the literal `modernpackage`
    token so `just init`'s rename sed rewrites their imports. Callers stage the
    copied files (`git add -A`) before `just init` so `git grep` sees them.
    """
    shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)
    _append_backend_dependencies(package_path / 'pyproject.toml')
```

Add the dependency-append helper (mirror `_remove_project_scripts` graceful-boundary style):

```python
def _append_backend_dependencies(pyproject_path: Path) -> None:
    """Populate [project.dependencies] and extend the dev group for the backend.

    Replaces the empty `dependencies = []` array with the backend runtime deps and
    prepends the dev-only deps (httpx) to the `dev` dependency-group. No-op with a
    notice if the file is absent (graceful boundary, like `_write_package_metadata`).
    """
    try:
        content = pyproject_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No pyproject.toml at {pyproject_path}; skipping backend deps.',
            file=sys.stderr,
        )
        return
    runtime = ''.join(f'    "{dep}",\n' for dep in _BACKEND_DEPENDENCIES)
    content = content.replace(
        'dependencies = []\n',
        f'dependencies = [\n{runtime}]\n',
    )
    dev = ''.join(f'    "{dep}",\n' for dep in _BACKEND_DEV_DEPENDENCIES)
    content = content.replace('dev = [\n', f'dev = [\n{dev}')
    pyproject_path.write_text(content)
```

Add the staging helper (new subprocess seam, mirrors existing `Popen` usage):

```python
def _stage_injected_files(package_path: Path) -> None:
    """Stage the injected backend files so `just init`'s `git grep` sees them.

    Runs `git add -A` in the clone. Copied files are untracked until staged; the
    rename sed (Justfile:62-67) only rewrites tracked files. Raises RuntimeError on
    a non-zero exit, matching the other subprocess steps.
    """
    pipe = Popen(  # noqa: S603
        ['git', 'add', '-A'],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        cwd=package_path,
    )
    _stdout, stderr = pipe.communicate()
    if pipe.returncode != 0:
        stderr_text = stderr.decode().strip()
        message = f'git add failed with exit code {pipe.returncode}: {stderr_text}'
        raise RuntimeError(message)
```

Update the `if backend:` block in `init_new_package` (from Phase 1) to call both:

```python
    if backend:
        _add_backend(new_package_path)
        _stage_injected_files(new_package_path)
```

#### 6. Always strip the cloned `backend_template/`
**File**: `modernpackage/main.py`
**Action**: modify (`_SCAFFOLDING_PATHS_TO_DELETE`, `main.py:502-507`)

```python
_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...] = (
    'modernpackage/main.py',
    'tests/test_e2e.py',
    'docs',
    'BACKLOG.md',
    'backend_template',
)
```

This guarantees the no-flag path is byte-for-byte identical (the cloned template dir is removed) and
that a `--backend` package has no stray nested `backend_template/` (strip removes the clone's copy;
`_add_backend` injects fresh files at the root).

#### 7. Ship `backend_template/` as package data
**File**: `pyproject.toml`
**Action**: modify (`[tool.hatch.build]`, `pyproject.toml:49-51`)

```toml
[tool.hatch.build]
include = ["**/*.py", "backend_template/**"]
exclude = ["tests/**"]
```

This ships the backend template (including non-`.py` files added in later phases) in the wheel so
real installed usage can locate `_BACKEND_TEMPLATE_DIR`. (The e2e test reaches the template via the
source checkout / git clone, so it does not depend on this; it matters only for published-wheel
installs.) Note the `exclude = ["tests/**"]` continues to keep the scaffolder's own `tests/` out of
the wheel; if a wheel build is found to drop `backend_template/tests/test_app.py`, anchor the
exclude to the repo's own tests with `exclude = ["/tests/**"]`.

#### 8. Unit tests for injection
**File**: `tests/test_main.py`
**Action**: modify (add a `_seed_clone`-based test group; import the new symbols)

Add to the imports from `modernpackage.main`: `_add_backend`, `_append_backend_dependencies`,
`_stage_injected_files`, `_BACKEND_DEPENDENCIES`.

```python
def test_add_backend_copies_template_and_appends_deps(tmp_path: Path) -> None:
    clone = _seed_clone(tmp_path)
    _add_backend(clone)
    assert (clone / 'modernpackage' / 'app.py').exists()
    assert (clone / 'modernpackage' / 'health.py').exists()
    assert (clone / 'tests' / 'test_app.py').exists()
    pyproject = (clone / 'pyproject.toml').read_text()
    assert 'fastapi' in pyproject
    assert 'sqlalchemy[asyncio]' in pyproject
    assert 'httpx' in pyproject
    assert tomllib.loads(pyproject)  # still valid TOML


def test_append_backend_dependencies_missing_file(tmp_path: Path) -> None:
    _append_backend_dependencies(tmp_path / 'pyproject.toml')  # must not raise


def test_injected_files_have_no_unrenamed_token_after_sed(tmp_path: Path) -> None:
    # Simulate just init's rename on the injected source files only.
    clone = _seed_clone(tmp_path)
    _add_backend(clone)
    for source in (clone / 'modernpackage').glob('*.py'):
        renamed = source.read_text().replace('modernpackage', 'newpkg')
        source.write_text(renamed)
    leftover = [
        p
        for p in (clone / 'modernpackage').glob('*.py')
        if 'modernpackage' in p.read_text()
    ]
    assert leftover == []


def test_strip_scaffolding_removes_backend_template(tmp_path: Path) -> None:
    clone = _seed_clone(tmp_path)
    (clone / 'backend_template').mkdir()
    (clone / 'backend_template' / 'marker.py').write_text('# x\n')
    _strip_scaffolding(clone)
    assert not (clone / 'backend_template').exists()


def test_init_new_package_backend_stages_then_inits(tmp_path: Path) -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend'),
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage', backend=True)
    assert popen_mock.call_count == 4  # clone, git add, just init, just check
    second = popen_mock.call_args_list[1]
    assert second.args[0] == ['git', 'add', '-A']
    assert second.kwargs['cwd'] == Path.cwd() / 'mypackage'
```

#### 9. Extend the existing e2e + add a backend e2e
**File**: `tests/test_e2e.py`
**Action**: modify

In `test_scaffolded_package_passes_check` (no-flag), add after the existing scaffolding-removed
assertions (`test_e2e.py:107-116`):

```python
    assert not (destination / 'backend_template').exists()  # template never leaks
```

Add a new backend e2e test (mirrors the existing flow, inserting `_add_backend` + `git add -A`
before `just init`):

```python
@pytest.mark.e2e
def test_scaffolded_backend_package_passes_check(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'backend-check.pkg'
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

    source_dir = destination / module_name
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()
    # token fully renamed in injected sources
    for source in source_dir.glob('*.py'):
        assert 'modernpackage' not in source.read_text()
    assert '/readyz' in (source_dir / 'health.py').read_text()

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'
```

### Verification
#### Automated
- [x] `just test` passes (new injection unit tests green; no-flag `Popen` tests untouched at 3 calls).
- [x] `just check` passes (repo's own ruff/mypy ignore `backend_template/`, so its strictness is not
      enforced here — the e2e is the guard).
- [ ] `just test-e2e` passes both `test_scaffolded_package_passes_check` and
      `test_scaffolded_backend_package_passes_check` (real scaffold + generated `just check`,
      requires network + git/just/uv).

#### Manual
- [x] Backend modules exist and carry the token:
      `grep -q 'from modernpackage.db import create_engine' backend_template/modernpackage/app.py`
- [x] Readiness route present:
      `grep -q "@router.get('/readyz')" backend_template/modernpackage/health.py`
- [x] `_BACKEND_TEMPLATE_DIR` resolves to a real dir:
      `uv run python -c "from modernpackage.main import _BACKEND_TEMPLATE_DIR as d; assert d.is_dir(), d; print(sorted(p.name for p in (d/'modernpackage').iterdir()))"`
      → prints `['app.py', 'db.py', 'health.py']` (plus `__init__.py` if added).
- [ ] Real scaffold smoke (network): in a scratch dir,
      `uv run modernpackage backendsmoke --backend` exits 0 and prints `just check passed`; then
      `grep -rq '/readyz' backendsmoke/backendsmoke/health.py` and
      `! grep -rq modernpackage backendsmoke/backendsmoke/`.

---

## Phase 3: Alembic async migrations + recipes

Add Alembic async migration scaffolding and the `just migrate`/`makemigration`/`migration-check`
recipes. Migration files flow through the Phase-2 copytree unchanged; recipes are appended to the
clone's `Justfile` by `_add_backend`.

### Changes

#### 1. Alembic config
**File**: `backend_template/alembic.ini`
**Action**: create

```ini
# Async Alembic config. The database URL is injected from $DATABASE_URL in env.py,
# not set here, so it can come from runtime/CI secrets.
[alembic]
script_location = migrations
prepend_sys_path = .
path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### 2. Async migration environment
**File**: `backend_template/migrations/env.py`
**Action**: create

```python
"""Alembic async migration environment (bridges sync migration API onto async)."""

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from modernpackage.db import Base

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    config_section = context.config.get_section(
        context.config.config_ini_section, {}
    )
    config_section['sqlalchemy.url'] = os.environ['DATABASE_URL']
    engine = async_engine_from_config(config_section, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
```

`from modernpackage.db import Base` carries the token (renamed by `just init`). This file lives at
the clone root (not under `<module>/` or `tests/`), so it is **not** linted/type-checked/covered —
it only needs to be valid Python and is not executed by `just check`.

#### 3. Migration script template
**File**: `backend_template/migrations/script.py.mako`
**Action**: create (standard Alembic async-template mako)

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

#### 4. Empty versions directory
**File**: `backend_template/migrations/versions/.gitkeep`
**Action**: create (empty file)

Alembic requires `migrations/versions/` to exist; `.gitkeep` makes git track the otherwise-empty
dir so it is committed (and thus cloned in the e2e) and copied by `copytree`. `alembic upgrade head`
with zero revisions is a harmless no-op.

#### 5. Append migration recipes in `_add_backend`
**File**: `modernpackage/main.py`
**Action**: modify

Add a module constant near `_BACKEND_DEPENDENCIES`:

```python
# Migration recipes appended to the generated package's Justfile (NOT added to the
# `check` chain — they need a live database). Two-space body indent matches the
# template Justfile; `: sync` follows the recipe convention (Justfile:8-42).
_BACKEND_RECIPES: str = """
migrate: sync
  uv run alembic upgrade head

makemigration message: sync
  uv run alembic revision --autogenerate -m "{{message}}"

migration-check: sync
  uv run alembic check
"""
```

Add the helper:

```python
def _append_backend_recipes(justfile_path: Path) -> None:
    """Append the migration recipes to the generated package's Justfile.

    No-op with a notice if the Justfile is absent (graceful boundary).
    """
    try:
        content = justfile_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No Justfile at {justfile_path}; skipping backend recipes.',
            file=sys.stderr,
        )
        return
    justfile_path.write_text(content + _BACKEND_RECIPES)
```

Wire it into `_add_backend` (after the dependency append):

```python
    shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)
    _append_backend_dependencies(package_path / 'pyproject.toml')
    _append_backend_recipes(package_path / 'Justfile')
```

#### 6. Unit test for recipe append
**File**: `tests/test_main.py`
**Action**: modify (import `_append_backend_recipes`)

```python
def test_add_backend_appends_migration_recipes(tmp_path: Path) -> None:
    clone = _seed_clone(tmp_path)
    (clone / 'Justfile').write_text('sync:\n  @uv sync\n')
    _add_backend(clone)
    justfile = (clone / 'Justfile').read_text()
    assert 'migrate: sync' in justfile
    assert 'makemigration message: sync' in justfile
    assert 'migration-check: sync' in justfile
```

Note: `_seed_clone` (`test_main.py:1281`) does not currently create a `Justfile`; the test creates
a minimal one before calling `_add_backend`. (If a later test needs a realistic Justfile, copy the
repo's `Justfile` the way `_seed_clone` copies `pyproject.toml`.)

#### 7. Extend the backend e2e
**File**: `tests/test_e2e.py`
**Action**: modify (`test_scaffolded_backend_package_passes_check`)

After the `just check` assertion, add:

```python
    generated_justfile = (destination / 'Justfile').read_text()
    assert 'migrate: sync' in generated_justfile
    assert 'makemigration' in generated_justfile
    assert (destination / 'migrations' / 'env.py').exists()
    assert (destination / 'alembic.ini').exists()
```

### Verification
#### Automated
- [x] `just test` passes (recipe-append unit test green).
- [ ] `just test-e2e` passes (generated `Justfile` has `migrate:`/`makemigration`; `migrations/env.py`
      and `alembic.ini` present; generated `just check` still passes).

#### Manual
- [ ] Recipes render in a scaffolded package:
      `uv run modernpackage migtest --backend && cd migtest && uv run just --list | grep -qE 'migrate|makemigration|migration-check'`
      (or, offline: `grep -q 'migrate: sync' migtest/Justfile`).
- [x] env.py carries the (renamed) token and async bridge:
      `grep -q 'run_sync(do_run_migrations)' backend_template/migrations/env.py`
- [x] `migrations/versions/` exists in the template:
      `test -d backend_template/migrations/versions`

---

## Phase 4: Containerization (Containerfile + compose + dockerignore)

Add the multi-stage `Containerfile`, `compose.yml` (app + Postgres + one-shot migration service
gated by `service_completed_successfully`), and `.dockerignore` to the template. Purely additive;
copied by the Phase-2 `copytree`.

### Changes

#### 1. Containerfile
**File**: `backend_template/Containerfile`
**Action**: create

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14

# --- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim
COPY --from=builder /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/readyz',timeout=4); sys.exit(0)"
CMD ["uvicorn", "modernpackage.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

The `modernpackage.app:create_app` token is renamed by `just init`. The HEALTHCHECK targets
`/readyz` (design Decision 5). The runtime stage copies the full `/app` (not just `.venv`) so
`alembic.ini`/`migrations/` are present for the `migrate` compose service.

#### 2. Compose stack
**File**: `backend_template/compose.yml`
**Action**: create

```yaml
# Portable across docker compose / podman compose / podman-compose.
# No top-level version: — obsolete since Compose V2.
services:
  app:
    build: .
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://appuser:secret@db:5432/appdb
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
  migrate:
    build: .
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://appuser:secret@db:5432/appdb
    depends_on:
      db:
        condition: service_healthy
  db:
    image: docker.io/library/postgres:17
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: appdb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

The one-shot `migrate` service (absent from the docs' illustrative compose) is shown explicitly and
runs `alembic upgrade head`; `app` waits on it via `service_completed_successfully` (design
Decision 6).

#### 3. dockerignore
**File**: `backend_template/.dockerignore`
**Action**: create

```
.venv
.git
__pycache__
*.pyc
.ruff_cache
.mypy_cache
```

#### 4. Extend the backend e2e
**File**: `tests/test_e2e.py`
**Action**: modify (`test_scaffolded_backend_package_passes_check`)

After the migration assertions, add:

```python
    assert (destination / 'Containerfile').exists()
    assert (destination / '.dockerignore').exists()
    compose = (destination / 'compose.yml').read_text()
    assert 'service_completed_successfully' in compose
    assert 'migrate:' in compose
    containerfile = (destination / 'Containerfile').read_text()
    assert '/readyz' in containerfile
```

### Verification
#### Automated
- [ ] `just test-e2e` passes (generated tree has `Containerfile`/`compose.yml`/`.dockerignore`;
      compose has the migration service + `service_completed_successfully`; Containerfile HEALTHCHECK
      hits `/readyz`; generated `just check` still passes).

#### Manual
- [x] Compose migration gating present:
      `grep -q service_completed_successfully backend_template/compose.yml && grep -q 'migrate:' backend_template/compose.yml`
- [x] Healthcheck targets readiness:
      `grep -q '/readyz' backend_template/Containerfile`
- [x] `.dockerignore` excludes the venv:
      `grep -qx '.venv' backend_template/.dockerignore`
- [ ] After a real `--backend` scaffold, files are renamed/present:
      `uv run modernpackage ctrtest --backend && grep -q 'ctrtest.app:create_app' ctrtest/Containerfile`

---

## Phase 5: e2e hardening + template lint guard

Solidify the comprehensive backend e2e assertion and add a lightweight guard against silent
`backend_template/` rot (the template is excluded from the repo's own ruff/mypy).

### Changes

#### 1. Consolidated e2e assertions
**File**: `tests/test_e2e.py`
**Action**: verify/consolidate

`test_scaffolded_backend_package_passes_check` now asserts the full chain (built up across Phases
2–4): scaffold `--backend` → generated `just check` passes → injected sources fully renamed →
`/readyz` route → `migrate`/`makemigration` recipes → `migrations/env.py` + `alembic.ini` →
`Containerfile`/`compose.yml`/`.dockerignore` with the migration-gated compose + `/readyz`
healthcheck. No new assertions required beyond Phases 2–4; this step confirms they are all present
in the single test.

#### 2. Template lint guard recipe
**File**: `Justfile`
**Action**: modify (add recipe; do NOT add to `check`'s chain — the repo's gates intentionally
exclude the heavyweight backend template)

```just
check-backend-template: sync
  uv run ruff check backend_template
```

This lints the template source against the repo's `ruff` config so it cannot rot undetected between
e2e runs. It is a manual/CI-optional gate, run separately from `just check`. (Note: the template
files were authored in Phases 2–3 to satisfy ruff `ALL`; `tests/*` per-file ignores apply to
`backend_template/tests/` because the ignore pattern is `tests/*`. `migrations/` and the mako/ini
files are not Python modules ruff lints by default — `script.py.mako` is skipped; `env.py` will be
linted by this recipe and was authored to pass.)

If `ruff check backend_template` surfaces rules that are impractical for inert template data (e.g.
`INP001` missing `__init__`, or import-resolution noise), scope them with a
`[tool.ruff.lint.per-file-ignores]` entry for `"backend_template/**"` in `pyproject.toml` rather
than weakening the global config — document each ignore with a comment.

#### 3. pyproject per-file-ignore (only if Phase-5 lint surfaces template-only rules)
**File**: `pyproject.toml`
**Action**: modify (conditional — add only if `check-backend-template` reports template-only noise)

```toml
[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "D"]
"backend_template/migrations/*" = ["INP001"]  # example; add real ones as found
```

### Verification
#### Automated
- [ ] `just test-e2e` is green end-to-end (both e2e tests).
- [x] `just check-backend-template` exits 0.
- [x] `just check` still passes (unchanged — backend template not in its chain).

#### Manual
- [x] The guard recipe exists and runs:
      `just --list | grep -q check-backend-template && just check-backend-template`
- [x] Single comprehensive backend e2e test exists:
      `grep -q 'def test_scaffolded_backend_package_passes_check' tests/test_e2e.py`

---

## Testing Checkpoints (cumulative)

- **After P1**: `--backend`/`--fastapi` parse to `backend=True`; dry-run announces the backend;
  no-flag dry-run unchanged. (`just test`)
- **After P2**: `--backend` produces a FastAPI package whose generated `just check` passes; all
  injected `modernpackage` tokens renamed; no-flag `Popen` tests still 3 calls; backend path 4 calls;
  `backend_template/` never leaks into a generated package. (`just test`, `just test-e2e`)
- **After P3**: generated package has Alembic async `env.py` + `migrate`/`makemigration`/
  `migration-check` recipes; generated `just check` still passes. (`just test`, `just test-e2e`)
- **After P4**: generated package has `Containerfile`/`compose.yml`/`.dockerignore` with
  migration-gated compose and a `/readyz` healthcheck. (`just test-e2e`)
- **After P5**: one comprehensive backend e2e test guards the whole feature; `check-backend-template`
  guards template source rot. (`just test-e2e`, `just check-backend-template`)

## Recovery notes (if context resets)

- The seam is `_add_backend(package_path)` (copytree + `_append_backend_dependencies` +
  `_append_backend_recipes`) plus `_stage_injected_files` (the gated `git add -A` `Popen` call),
  both inside `if backend:` in `init_new_package`, between `_strip_scaffolding` and `just init`.
- Everything backend-specific lives in top-level `backend_template/`, shipped via
  `[tool.hatch.build] include`.
- `backend_template` is in `_SCAFFOLDING_PATHS_TO_DELETE`, so the no-flag path stays byte-for-byte
  identical (clone → strip removes the cloned template) and `--backend` packages have no nested
  `backend_template/`.
- The single hard constraint is the **95% coverage + ruff `ALL` + mypy `strict`** gate the generated
  package's `just check` runs over `<module>` and `tests/`; `backend_template/modernpackage/*.py`
  and `backend_template/tests/test_app.py` must satisfy it. The backend e2e test is the only place
  this is exercised end-to-end.
