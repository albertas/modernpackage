# Implementation Plan

## Overview

Add one new `@pytest.mark.e2e` test, `test_fullstack_package_runs_end_to_end`, to
`tests/test_e2e.py` that proves a scaffolded fullstack package is genuinely
functional: it brings the shipped `compose.yml` stack up (db + migrate + app),
asserts real host-side HTTP against `/livez` and `/readyz`, regenerates the API
client against the live backend, and builds the frontend against that client —
always tearing the stack down in `try/finally`.

## Key facts confirmed during planning

- **`compose.yml` lands at the package root** (`destination/compose.yml`), **not**
  `destination/module_name`. `_add_backend` does
  `copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` so every
  backend-template top-level file (`compose.yml`, `Containerfile`, `alembic.ini`,
  `migrations/`, `modernpackage/`) lands directly under `destination`. The
  Python source dir `destination / module_name` only holds `app.py`/`health.py`
  etc. **Deviation from structure.md** (which said `compose.yml` lands at
  `destination / module_name`): all compose commands run with `cwd=destination`.
  The `build: .` context and `Containerfile` are at `destination`, so this is
  correct and consistent with `just generate-client` / `just frontend-build`,
  which also run from `destination` (Justfile at root).
- `app` publishes `127.0.0.1:8000:8000` (`compose.yml:7`); host probes target
  `http://127.0.0.1:8000`.
- `/livez` → `200 {"status":"pass"}` (`health.py:31-34`); `/readyz` → `200`
  `{"status":"pass"}` on a real `SELECT 1`, else `503` (`health.py:37-46`).
- OperationIds in the committed schema are `livez_livez_get` and
  `readyz_readyz_get` (`frontend_template/openapi.json`); the regenerated
  `@hey-api/openapi-ts` client will contain the substrings `livez` and `readyz`.
- `openapi-ts.config.ts` input is `http://localhost:8000/openapi.json` — the
  generator reads the **live** URL, so the backend must be up first.
- Frontend build output dir is the Vite default `frontend/dist/` (`build` =
  `tsc --noEmit && vite build`).
- The placeholder client (`frontend_template/src/client/index.ts:1-4`) contains
  the marker `Record<string, unknown>` and a `regenerate` comment; after
  `generate-client` these are replaced by generated files.

---

## Phase 1: Compose-command detection + HTTP helper (foundations)

Add two module-private helpers and one module constant to `tests/test_e2e.py`.
No test body yet. Both helpers degrade gracefully at the process/network
boundary (CLAUDE.md error-handling; design "Patterns to Follow").

### Changes

#### 1. New imports
**File**: `tests/test_e2e.py`
**Action**: modify (top of file, alongside existing `import os` block at lines 17-21)

Add stdlib imports needed by `_http_get`:

```python
import urllib.error
import urllib.request
```

Keep them in alphabetical order within the existing import group (after
`subprocess`, before `from pathlib import Path`). `re`, `shutil`, `subprocess`,
`os` are already imported.

#### 2. Module constant for runtime tools
**File**: `tests/test_e2e.py`
**Action**: modify — add after `REQUIRED_TOOLS` (line 29)

```python
# Phase 2's skip guard needs the base tools plus a Node toolchain (`npm`); the
# compose command itself is detected separately via `_detect_compose_command`.
_REQUIRED_RUNTIME_TOOLS: tuple[str, ...] = (*REQUIRED_TOOLS, 'npm')
```

#### 3. Compose-command detection helper
**File**: `tests/test_e2e.py`
**Action**: modify — add near `_run` (after line 51), before the test bodies

```python
_COMPOSE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ('docker', 'compose'),
    ('podman', 'compose'),
    ('podman-compose',),
)


def _detect_compose_command() -> list[str] | None:
    """Return the first working compose command, or None if none is available.

    Probes the portability set named in `backend_template/compose.yml:1`
    (`docker compose` → `podman compose` → `podman-compose`) by running
    `<cmd> version` with `check=False`; returns the first whose returncode is 0.
    Degrades gracefully: a missing executable raises `FileNotFoundError`, which
    is treated as "not available" rather than propagated.
    """
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
```

#### 4. HTTP GET helper
**File**: `tests/test_e2e.py`
**Action**: modify — add directly after `_detect_compose_command`

```python
def _http_get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    """GET `url` via stdlib urllib; return `(status_code, body)`.

    Mirrors the `Containerfile` healthcheck's use of `urllib.request`
    (`Containerfile:25`) instead of pulling in `httpx` (a backend-template dev
    dep, not guaranteed in the outer test env — design decision 5). HTTP error
    statuses (4xx/5xx) are returned, not raised, so callers can assert on them;
    only a connection-level failure propagates.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')
```

### Verification

#### Automated
- [x] `just check` passes (helpers are lint/type clean; new imports used).
- [x] `uv run pytest tests/test_e2e.py -m e2e --no-cov -k runs_end_to_end`
  collects without error (0 tests selected so far — the test does not exist yet;
  expect "no tests ran" / exit code 5, not a collection error).

#### Manual
- [x] `uv run python -c "from tests.test_e2e import _detect_compose_command as d; print(d())"`
  prints a list (e.g. `['docker', 'compose']`) on a compose host or `None`
  otherwise, without raising. (Result: `['podman', 'compose']`)
- [x] `uv run python -c "from tests.test_e2e import _http_get; print(_http_get('http://127.0.0.1:1/'))"`
  raises a connection error (nothing listening) rather than hanging — confirms
  the connection-failure path is not swallowed. (Expected: a `URLError`
  traceback; this is the documented "only connection failure propagates"
  behavior.) (Result: `urllib.error.URLError: <urlopen error [Errno 111] Connection refused>`)

---

## Phase 2: Bring the stack up + backend HTTP assertions

Add `test_fullstack_package_runs_end_to_end`: scaffold via the verbatim
sequence reused from the existing fullstack test, `compose up -d --wait --build`,
then assert `/livez` and `/readyz` over real HTTP. Wrap the compose lifecycle in
`try/finally` with `compose down -v` (design decision 7).

### Changes

#### 1. New e2e test (skeleton through Phase 2)
**File**: `tests/test_e2e.py`
**Action**: modify — append a new test after
`test_scaffolded_fullstack_package_passes_check` (after line 369)

```python
@pytest.mark.e2e
def test_fullstack_package_runs_end_to_end(tmp_path: Path) -> None:
    """Scaffold a fullstack package and prove it runs against a real stack.

    Brings the shipped `compose.yml` up (db + migrate + app) via
    `compose up --wait` (which blocks until the app's `/readyz` healthcheck
    passes, proving DB + migrations + app readiness), then asserts host-side
    HTTP on `/livez` and `/readyz`, regenerates the API client against the live
    backend, and builds the frontend against it.

    Caveats (inherited from sibling tests, see module docstring): pulls
    `postgres:17`, builds the app image, and runs `npm ci` + `vite build` —
    minutes-long and network-dependent. Skip guards make environments lacking
    compose or Node skip rather than fail. Teardown (`compose down -v`) always
    runs in `try/finally`.
    """
    for tool in _REQUIRED_RUNTIME_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')
    compose = _detect_compose_command()
    if compose is None:
        pytest.skip('no compose command available (docker/podman compose)')

    package_name = 'fullstack-run.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e fullstack package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    main._inject_templates(destination, fullstack=True)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    # `compose.yml` lands at the package root (`destination`), not under
    # `destination / module_name` — `_add_backend` copytrees the backend
    # template into `package_path`. The `build: .` context is `destination`.
    try:
        up = _run([*compose, 'up', '-d', '--wait', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'

        # Backend HTTP assertions (design pillar 1). `--wait` already proved
        # readiness; these confirm real behavior from the host.
        livez_status, livez_body = _http_get('http://127.0.0.1:8000/livez')
        assert livez_status == 200, f'/livez returned {livez_status}: {livez_body}'
        assert 'pass' in livez_body, f'/livez body unexpected: {livez_body}'

        readyz_status, readyz_body = _http_get('http://127.0.0.1:8000/readyz')
        assert readyz_status == 200, f'/readyz returned {readyz_status}: {readyz_body}'
    finally:
        _run([*compose, 'down', '-v'], cwd=destination)
```

Phases 3 and 4 add code **inside the existing `try`** (before the `finally`);
do not introduce a second `try`.

### Verification

#### Automated
- [x] `just check` passes (the new test is excluded from `check`, but it must be
  lint/type clean so `check-format`/`check-lint`/`check-typecheck` pass).
- [ ] `uv run pytest -m e2e --no-cov -k runs_end_to_end -v` exits 0 on a
  compose+Node host, or reports `skipped` on a host without compose/npm — never
  `failed`.

#### Manual
- [ ] On a compose host, after the test run:
  `docker compose ls 2>/dev/null || podman ps -a` shows no leftover
  project containers for the scaffolded package.
- [ ] `docker volume ls 2>/dev/null || podman volume ls` shows no `pgdata`
  volume left by the run (teardown used `-v`).
- [ ] Port is freed: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/livez || echo "closed"`
  prints `closed` (connection refused) after teardown.

---

## Phase 3: Regenerate the API client against the live backend

With the stack up, run `just frontend-install` then `just generate-client` so
`@hey-api/openapi-ts` fetches `http://localhost:8000/openapi.json` and rewrites
`frontend/src/client/`. Assert the regenerated client references the real
operations and is no longer the placeholder (design pillar 2).

### Changes

#### 1. Client regeneration block
**File**: `tests/test_e2e.py`
**Action**: modify — insert inside the Phase 2 `try`, after the `/readyz`
assertion and before `finally`, while the backend is still up

```python
        # Frontend deps first: `generate-client` does not depend on
        # `frontend-install` (research Q4; test_e2e.py:321-323).
        install = _run(['just', 'frontend-install'], cwd=destination)
        assert install.returncode == 0, (
            f'just frontend-install failed:\n{install.stdout}\n{install.stderr}'
        )

        # `generate-client` reads the LIVE http://localhost:8000/openapi.json
        # (openapi-ts.config.ts:4), so the backend must be up — this is why the
        # call lives inside the `try` after `compose up`.
        generate = _run(['just', 'generate-client'], cwd=destination)
        assert generate.returncode == 0, (
            f'just generate-client failed:\n{generate.stdout}\n{generate.stderr}'
        )

        # The regenerated client references the real operations. Assert on stable
        # substrings (operationIds livez_livez_get / readyz_readyz_get) rather
        # than exact generated structure, which @hey-api versions may change
        # (design Open Risks).
        client_dir = destination / 'frontend' / 'src' / 'client'
        client_text = '\n'.join(
            path.read_text() for path in client_dir.rglob('*') if path.is_file()
        )
        assert 'livez' in client_text, f'regenerated client missing livez:\n{client_text}'
        assert 'readyz' in client_text, f'regenerated client missing readyz:\n{client_text}'
        # Placeholder marker is gone (src/client/index.ts:3-4 used this type).
        assert 'Record<string, unknown>' not in client_text, (
            'client still looks like the hand-written placeholder'
        )
```

### Verification

#### Automated
- [ ] `uv run pytest -m e2e --no-cov -k runs_end_to_end -v` passes (or skips).
- [x] `just check` still passes (lint/type clean).

#### Manual
- [ ] With teardown temporarily disabled for inspection (comment out the
  `finally` body, or run the scaffold steps by hand), after `generate-client`:
  `grep -rl livez <destination>/frontend/src/client` returns at least one file,
  and that file is **not** the 4-line placeholder
  (`wc -l <that-file>` > 4 and `grep -L 'Record<string, unknown>' <that-file>`
  lists it).
- [ ] Negative ordering check: stopping the backend (`compose down`) before
  `generate-client` makes the step fail (non-zero return / connection error),
  confirming the backend-up ordering matters (design "Patterns to NOT follow"
  item 3). This is an exploratory manual check, not an assertion added to the
  test.

---

## Phase 4: Build the frontend against the regenerated client

Run `just frontend-build` (`tsc --noEmit && vite build`) and assert it succeeds
and emits a non-empty `frontend/dist/` — proving the regenerated client
type-checks and bundles (design pillar 3). The build reads no live URL, so it
may run inside the `try` after Phase 3 (kept there for simplicity; the backend
is still up but unused by the build).

### Changes

#### 1. Frontend build block
**File**: `tests/test_e2e.py`
**Action**: modify — insert inside the Phase 2 `try`, after the Phase 3 client
assertions and before `finally`

```python
        build = _run(['just', 'frontend-build'], cwd=destination)
        assert build.returncode == 0, (
            f'just frontend-build failed:\n{build.stdout}\n{build.stderr}'
        )

        # Build emitted a non-empty dist/ (Vite default output dir).
        dist_dir = destination / 'frontend' / 'dist'
        assert dist_dir.is_dir(), 'frontend/dist not created by build'
        assert (dist_dir / 'index.html').is_file(), 'frontend/dist/index.html missing'
```

### Verification

#### Automated
- [ ] `uv run pytest -m e2e --no-cov -k runs_end_to_end -v` passes end-to-end
  on a compose+Node host.
- [ ] `just test-e2e` (full e2e suite) is green on a compose+Node host.
- [x] `just check` (no e2e) remains green.

#### Manual
- [ ] With teardown temporarily disabled: `test -f <destination>/frontend/dist/index.html`
  exits 0 after a run.
- [ ] `just frontend-build` output contains Vite build summary lines
  (e.g. a `dist/` line): rerun by hand and `grep -q 'dist/' <build-output>`.

---

## Testing Checkpoints

State that should hold after each phase, for resuming after a context reset:

- **After Phase 1**: `_detect_compose_command()` and `_http_get()` exist, are
  lint/type-clean (`just check` green), and importable/callable without raising.
  No new runtime test yet.
- **After Phase 2**: `test_fullstack_package_runs_end_to_end` exists and is green
  on a compose+Node host; skips cleanly elsewhere. `compose up --wait` proves
  db+migrate+app readiness; `/livez` returns 200 `pass`, `/readyz` returns 200.
  Teardown leaves no containers/volumes and frees port 8000.
- **After Phase 3**: `generate-client` runs against the live backend; the
  regenerated `frontend/src/client/` references `livez`/`readyz` and no longer
  contains the `Record<string, unknown>` placeholder marker.
- **After Phase 4**: `frontend-build` succeeds against the regenerated client and
  emits a non-empty `frontend/dist/` (with `index.html`). `just test-e2e` fully
  green; `just check` unaffected.

## Notes / Risks carried from design

- **Single-test caveat**: this is one test built up across phases, not four
  independent features. Each phase exercises one design pillar and is
  independently runnable via `-k runs_end_to_end`.
- **Compose location deviation**: structure.md said `compose.yml` lands at
  `destination / module_name`; it actually lands at `destination` (package
  root). All compose / `just` commands run with `cwd=destination`. This is the
  only correction made to the structure outline.
- **Port 8000 contention** (compose binds a fixed host port): if `just test-e2e`
  is flaky under parallelism, flag for a project-scoped compose project name or
  port override (design Open Risks). Not addressed here.
- **Runtime cost**: pulls `postgres:17`, builds the app image, runs `npm ci` +
  `vite build` — minutes-long and network-dependent; mitigated by skip guards
  and documented in the test docstring (matching `test_e2e.py:1-15`).
- **Hard-kill cleanup**: a process killed mid-run bypasses `finally`; a manual
  `<compose> down -v` (run from the scaffolded package dir) may be needed.
