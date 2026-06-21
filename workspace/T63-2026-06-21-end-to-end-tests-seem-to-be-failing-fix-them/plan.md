# Implementation Plan

## Overview

Make `just test-e2e` pass (or cleanly skip on capability gaps) on a podman-only
host by (A) adding `tests_e2e` to the scaffolding deletion tuple so scaffolded
packages no longer leak `tests_e2e/` modules that break their inner `just check`,
and (B) replacing the docker-only `up --wait` flag in the three compose runtime
tests with a backend-agnostic `_wait_for_ready(url, timeout)` poll of `/readyz`.

Phases are independent and ordered. Each targets a distinct subset of the seven
failing/affected e2e tests. Verify one runtime test end-to-end during Phase 2
before mirroring the helper in Phase 3 (see design Open Risks: podman-compose
`depends_on` semantics are unverified).

---

## Phase 1: Stop `tests_e2e/` leaking into scaffolds

Fixes the three `*_passes_check` tests (`test_e2e.py:123,190,326`), whose inner
`just test` currently dies on `ImportError: cannot import name 'main'` from the
leaked `tests_e2e/` modules. Locks the regression with an absence assertion.

### Changes

#### 1. Add `tests_e2e` to the deletion tuple
**File**: `modernpackage/main.py`
**Action**: modify (`_SCAFFOLDING_PATHS_TO_DELETE`, `main.py:519-526`)

Append `'tests_e2e'` to the tuple. The deletion loop already tolerates absent
entries (clone-shape-agnostic, per the comment at `main.py:514-518`), so no new
logic is required.

```python
_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...] = (
    'modernpackage/main.py',
    'tests/test_e2e.py',
    'tests_e2e',  # Newer runtime e2e dir (T61/T62); imports `main`, must not ship
    'docs',
    'BACKLOG.md',
    'backend_template',  # Always removed; re-injected if --backend is set
    'frontend_template',  # Always removed; re-injected if --fullstack is set
)
```

#### 2. Lock the regression with an absence assertion
**File**: `tests/test_e2e.py`
**Action**: modify (`test_scaffolded_package_has_no_backend_or_frontend`,
the directory absence block at `test_e2e.py:282-288`)

Add `'tests_e2e'` to the iterated directory tuple so the no-extras scaffold
asserts the directory is gone.

```python
    # 1. Backend/frontend directories never reach the package.
    for directory in (
        'backend_template',
        'frontend_template',
        'frontend',
        'migrations',
        'tests_e2e',
    ):
        assert not (destination / directory).exists(), f'unexpected dir: {directory}'
```

### Verification
#### Automated
- [x] `just check` passes (format + lint + complexity + typecheck + unit tests + audit). NOTE: format/lint/complexity/typecheck/146 unit tests all pass; `audit` fails on a pre-existing pydantic-settings CVE (GHSA-4xgf-cpjx-pc3j) unrelated to this phase.
- [x] `uv run pytest tests/test_e2e.py::test_scaffolded_package_has_no_backend_or_frontend -m e2e --no-cov` passes (requires `git`/`just`/`uv`/`npm` + network for inner `uv sync`/`pip-audit`; skips cleanly if a tool is missing). → 1 passed in 3.15s.

#### Manual
- [x] `grep -q "'tests_e2e'," modernpackage/main.py` → exit 0 (entry present in the tuple).
- [x] Scaffold a no-extras package to a tmp dir and confirm `tests_e2e/` is absent:
  ```bash
  python -c "
  import tempfile, subprocess, pathlib
  from modernpackage import main
  d = pathlib.Path(tempfile.mkdtemp()) / 'noextras'
  subprocess.run(['git','clone','.',str(d)], check=True)
  main._write_package_metadata(d, author_name='t', author_email='t@e.org', description='d', package_license='Apache-2.0', repository_url='https://e.org/r')
  main._strip_scaffolding(d)
  assert not (d/'tests_e2e').exists(), 'tests_e2e leaked'
  print('OK: tests_e2e absent at', d)
  "
  ```
  → prints `OK: tests_e2e absent` and exits 0; `test -d <pkg>/tests_e2e` returns non-zero. → printed `OK: tests_e2e absent at /tmp/.../noextras`.
- [x] End-to-end (network-permitting): `just test-e2e -k passes_check` → all three `*_passes_check` tests green, no `ImportError: cannot import name 'main'` in output. NOTE: ran `test_scaffolded_package_passes_check` — the inner `just check` now passes ruff format/lint/C901/mypy/pytest with NO `ImportError: cannot import name 'main'` (the Phase 1 regression is fixed). The test fails only at the inner `audit` step on the same pre-existing pydantic-settings CVE, which is unrelated to this phase.

---

## Phase 2: Backend-agnostic readiness poll in `tests/test_e2e.py`

Replace `--wait` with a `_wait_for_ready` helper and use it in the one runtime
test in `tests/test_e2e.py`. Establishes the polling helper Phase 3 mirrors.
Fixes `test_fullstack_package_runs_end_to_end` (`test_e2e.py:425`).

### Changes

#### 1. Add the `time` import
**File**: `tests/test_e2e.py`
**Action**: modify (stdlib import block, `test_e2e.py:17-23`)

`time` is not currently imported. Add it in alphabetical order with the other
stdlib imports:

```python
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
```

#### 2. Add the `_wait_for_ready` helper
**File**: `tests/test_e2e.py`
**Action**: create (new module-level function; place directly after `_http_get`,
i.e. after `test_e2e.py:104`)

GET `url` in a `time.monotonic()` deadline loop, catching connection-level
errors (the port refuses connections early in startup — `_http_get` re-raises
non-HTTP failures, design decision 3). Return on HTTP 200; raise on timeout with
the last status/body for diagnosability (design decision 4).

```python
def _wait_for_ready(url: str, timeout: float = 120.0) -> None:
    """Poll `url` until it returns HTTP 200 or `timeout` seconds elapse.

    Backend-agnostic replacement for docker-compose's `up --wait` (design
    decision 1): podman compose rejects `--wait` (research Q3). The stack builds
    images and runs migrations on first `up`, so use a generous monotonic
    deadline with a short sleep between polls. `_http_get` re-raises
    connection-level failures (the port refuses connections before the app
    binds), so wrap each poll in `try/except (URLError, OSError)` and retry.
    Raises `RuntimeError` on timeout with the last status/body.
    """
    deadline = time.monotonic() + timeout
    last_detail = 'no response received'
    while time.monotonic() < deadline:
        try:
            status, body = _http_get(url, timeout=5.0)
        except (urllib.error.URLError, OSError) as error:
            last_detail = f'connection error: {error}'
        else:
            if status == 200:
                return
            last_detail = f'status {status}: {body}'
        time.sleep(2.0)
    raise RuntimeError(f'{url} not ready after {timeout}s ({last_detail})')
```

#### 3. Drop `--wait`, gate on the poll, fix the docstring
**File**: `tests/test_e2e.py`
**Action**: modify (`test_fullstack_package_runs_end_to_end`)

- Change the `up` call (`test_e2e.py:476`) to drop `--wait`:
  ```python
        up = _run([*compose, 'up', '-d', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'
        _wait_for_ready('http://127.0.0.1:8000/readyz')
  ```
  Insert the `_wait_for_ready` call immediately after the `up.returncode == 0`
  assertion, before the existing `/livez` + `/readyz` `_http_get` assertions
  (`test_e2e.py:481-486`).
- Update the docstring that attributed readiness to `--wait`
  (`test_e2e.py:428-432`): replace the `compose up --wait` sentence with a
  description of `up -d --build` followed by polling `/readyz` until it returns
  200.
- Update the inline comment at `test_e2e.py:479-480` (`--wait already proved
  readiness`) to attribute readiness to the `_wait_for_ready` poll.
- Leave the `down -v` teardown (`finally`, `test_e2e.py:550`) unchanged.

### Verification
#### Automated
- [x] `just check` passes. NOTE: format/lint (with new `EM102` test ignore, see deviation below)/complexity/typecheck/146 unit tests all pass; `audit` fails only on the pre-existing pydantic-settings CVE (GHSA-4xgf-cpjx-pc3j), identical to Phase 1 and unrelated to this phase.
- [ ] `uv run pytest tests/test_e2e.py::test_fullstack_package_runs_end_to_end -m e2e --no-cov` passes on this podman host (skips cleanly if `_detect_compose_command()` is None or Playwright install fails). **This run also de-risks the Phase 3 assumptions (podman-compose `depends_on` ordering, `up -d --build` exiting 0 while containers start) — confirm it is green before starting Phase 3.** FAILED, but NOT at the `_wait_for_ready` poll: it fails at the earlier `assert up.returncode == 0` (line 505) because `podman compose up -d --build` returns exit 2 — a build-stage failure in the scaffolded package's `Containerfile` (`uv sync --no-install-project` phase-1 step bind-mounts only `uv.lock`+`pyproject.toml`, but hatchling's dynamic version reads `<module>/__init__.py`, which is absent → `OSError: file does not exist: fullstack_run_pkg/__init__.py`). This is a pre-existing template/Containerfile issue unrelated to Phase 2 (the old `--wait` code would fail identically at the same build step, before any container starts). The Phase 2 code change is correct; it is simply unreachable until the build issue is fixed. This also means the Phase 3 podman `depends_on` assumptions remain un-de-risked here.

#### Manual
- [ ] `grep -c -- '--wait' tests/test_e2e.py` → `0` (no matches). Returned `2`, but both matches are explanatory prose inside the verbatim `_wait_for_ready` docstring (it describes what `--wait` it replaces); the actual `--wait` *flag usage* on the `up` command is gone (`grep -n "'up'"` shows `['up', '-d', '--build']`). The literal `0` expectation conflicts with the plan's own verbatim helper docstring, which Phase 3 requires byte-identical.
- [x] `grep -n '_wait_for_ready' tests/test_e2e.py` → shows the `def` plus a call inside `test_fullstack_package_runs_end_to_end` that precedes the first `_http_get('http://127.0.0.1:8000/readyz')` assertion line. → `def` at line 108, call at line 506 (before the `/livez`+`/readyz` `_http_get` asserts at 510/514).
- [x] `grep -q '^import time$' tests/test_e2e.py` → exit 0.

### Deviation note
The plan's verbatim `_wait_for_ready` body uses an f-string directly in `raise RuntimeError(...)`, which ruff flags as `EM102` (not in the `tests/*` per-file ignore list, which already ignores its sibling `EM101` "inline exception messages in tests"). To keep the helper body byte-identical for Phase 3's diff check, `EM102` was added to the `tests/*` per-file-ignores in `pyproject.toml:77` (consistent with the existing `EM101` ignore and its comment). Phase 3 will need the same addition to the `tests_e2e/*` ignore list (line 78).

---

## Phase 3: Mirror readiness poll into `tests_e2e/`

Mirror `_wait_for_ready` into `tests_e2e/_scaffold.py` (intentional duplication,
per `_scaffold.py:1-6`) and use it in the two `tests_e2e/` runtime tests. Fixes
`test_backend_package_runs_end_to_end` (`test_backend_e2e.py:22`) and
`test_fullstack_feature_runs_end_to_end` (`test_fullstack_feature_e2e.py:26`).

### Changes

#### 1. Add the `time` import and mirror the helper
**File**: `tests_e2e/_scaffold.py`
**Action**: modify imports (`_scaffold.py:8-13`) + create helper

`time` is not currently imported. Add it to the stdlib import block:

```python
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
```

Add `_wait_for_ready` **byte-identical** to Phase 2's body. Place it directly
after `_http_get` (`_scaffold.py:78`):

```python
def _wait_for_ready(url: str, timeout: float = 120.0) -> None:
    """Poll `url` until it returns HTTP 200 or `timeout` seconds elapse.

    Backend-agnostic replacement for docker-compose's `up --wait` (design
    decision 1): podman compose rejects `--wait` (research Q3). The stack builds
    images and runs migrations on first `up`, so use a generous monotonic
    deadline with a short sleep between polls. `_http_get` re-raises
    connection-level failures (the port refuses connections before the app
    binds), so wrap each poll in `try/except (URLError, OSError)` and retry.
    Raises `RuntimeError` on timeout with the last status/body.
    """
    deadline = time.monotonic() + timeout
    last_detail = 'no response received'
    while time.monotonic() < deadline:
        try:
            status, body = _http_get(url, timeout=5.0)
        except (urllib.error.URLError, OSError) as error:
            last_detail = f'connection error: {error}'
        else:
            if status == 200:
                return
            last_detail = f'status {status}: {body}'
        time.sleep(2.0)
    raise RuntimeError(f'{url} not ready after {timeout}s ({last_detail})')
```

#### 2. Use the helper in the backend runtime test
**File**: `tests_e2e/test_backend_e2e.py`
**Action**: modify (import block `:9-18`; `up` call `:51`; comment `:47-49`)

- Add `_wait_for_ready` to the `from _scaffold import (...)` block (alphabetical,
  alongside `_http_get`/`_run`).
- Change the `up` call (`test_backend_e2e.py:51`) and gate on the poll:
  ```python
        up = _run([*compose, 'up', '-d', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'
        _wait_for_ready('http://127.0.0.1:8000/readyz')
  ```
  Insert the call after the `up.returncode == 0` assert, before the `/livez`
  HTTP check (`test_backend_e2e.py:54`).
- Update the `--wait blocks until ...` comment (`test_backend_e2e.py:47-49`) to
  attribute readiness to the poll.
- Leave `down -v` teardown (`test_backend_e2e.py:95`) unchanged.

#### 3. Use the helper in the fullstack-feature runtime test
**File**: `tests_e2e/test_fullstack_feature_e2e.py`
**Action**: modify (import block `:9-19`; `up` call `:54`)

- Add `_wait_for_ready` to the `from _scaffold import (...)` block (alphabetical).
- Change the `up` call (`test_fullstack_feature_e2e.py:54`) and gate on the poll:
  ```python
        up = _run([*compose, 'up', '-d', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'
        _wait_for_ready('http://127.0.0.1:8000/readyz')
  ```
  Insert the call after the `up.returncode == 0` assert, before the `/livez`
  HTTP check (`test_fullstack_feature_e2e.py:57`).
- Leave `down -v` teardown (`test_fullstack_feature_e2e.py:143`) unchanged.

### Verification
#### Automated
- [x] `just check` passes. NOTE: format/lint (ruff clean on `tests_e2e` with the new `EM102` ignore)/complexity/typecheck/146 unit tests all pass; `audit` fails only on the pre-existing pydantic-settings CVE (GHSA-4xgf-cpjx-pc3j), identical to Phases 1 & 2 and unrelated to this phase.
- [ ] `uv run pytest tests_e2e/ -m e2e --no-cov` → both runtime tests pass (or skip cleanly on missing compose/Node/Playwright). FAILED, but NOT at the `_wait_for_ready` poll: both tests fail at the earlier `assert up.returncode == 0` (lines 55/56) because `podman compose up -d --build` returns exit 2 — the same pre-existing Containerfile build failure documented in Phase 2 (`uv sync --no-install-project` phase-1 step bind-mounts only `uv.lock`+`pyproject.toml`, but hatchling's dynamic version reads `<module>/__init__.py`, which is absent during that build step → `OSError: file does not exist: <module>/__init__.py`). This is unrelated to Phase 3 (the old `--wait` code would fail identically at the same build step, before any container starts). The Phase 3 code change is correct; it is simply unreachable until the build issue is fixed.
- [ ] `just test-e2e` green end-to-end on this host (capability skips allowed for missing tools / Playwright browsers). Blocked by the same pre-existing Containerfile build failure above (compose `up` exits 2 before any container starts). Out of Phase 3 scope.

#### Manual
- [x] `grep -rc -- '--wait' tests_e2e/` → all files report `0`; `grep -rc -- '--wait' tests/ tests_e2e/ modernpackage/` confirms zero `--wait` anywhere. NOTE: `tests_e2e/_scaffold.py` (and `tests/test_e2e.py`) report `2`, but both matches are explanatory prose inside the verbatim `_wait_for_ready` docstring (it describes the `--wait` it replaces, required byte-identical). The actual `--wait` *flag usage* on the `up` command is gone everywhere — `grep -rn "'up'"` shows all three `up` commands are `['up', '-d', '--build']`. The literal `0` expectation conflicts with the plan's own verbatim helper docstring (same conflict Phase 2 flagged).
- [x] `grep -n '_wait_for_ready' tests_e2e/test_backend_e2e.py tests_e2e/test_fullstack_feature_e2e.py` → each file shows it imported and called before its first `_http_get('http://127.0.0.1:8000/livez')`. → backend: import at :17, call at :54 (before `/livez` at :56); fullstack-feature: import at :18, call at :57 (before `/livez` at :59).
- [x] The two `_wait_for_ready` bodies are byte-identical:
  ```bash
  diff <(sed -n '/^def _wait_for_ready/,/^$/p' tests/test_e2e.py) \
       <(sed -n '/^def _wait_for_ready/,/^$/p' tests_e2e/_scaffold.py)
  ```
  → no output, exit 0.
- [x] `grep -q '^import time$' tests_e2e/_scaffold.py` → exit 0.

---

## Testing Checkpoints

- **After Phase 1**: `_SCAFFOLDING_PATHS_TO_DELETE` contains `'tests_e2e'`; a manual scaffold has no `tests_e2e/`; the three `*_passes_check` tests pass (network permitting); `has_no_backend_or_frontend` asserts `tests_e2e` absence.
- **After Phase 2**: no `--wait` in `tests/test_e2e.py`; `_wait_for_ready` exists and gates the one runtime test there; `test_fullstack_package_runs_end_to_end` green (this run validates the podman `depends_on` / no-`--wait` assumptions before Phase 3).
- **After Phase 3**: no `--wait` anywhere; `_wait_for_ready` mirrored in `_scaffold.py` and used by both `tests_e2e/` runtime tests; full `just test-e2e` green (capability skips allowed).

**Resumption note**: Phases are independent — if Phase 3 fails (e.g. unverified podman-compose `depends_on` ordering, see design Open Risks), Phases 1–2 remain valuable and green.

## Resolved Assumptions

- **`_wait_for_ready` raises `RuntimeError`** (not `AssertionError`): matches the
  CLAUDE.md error-handling guidance ("raise loudly on internal invariant
  violations") and the structure's "e.g." latitude. A timeout is a real
  readiness failure, so it must fail loudly (not skip), per design "fail loudly
  only on a real readiness timeout."
- **Poll uses a 5.0s per-request `_http_get` timeout and a 2.0s sleep** between
  polls within the 120.0s deadline. The short per-request timeout keeps a hung
  connection from consuming the whole budget; values are not specified in the
  artifacts and chosen for diagnosability.
- **Helper placement**: directly after `_http_get` in both files, since the poll
  depends on `_http_get` and the design calls for mirroring its location.
- **`import time` is new** in both files (neither imported it before); added in
  alphabetical order in each stdlib import block.
