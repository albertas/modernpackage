# Implementation Plan

## Overview

Add a `shutil.which`-based preflight check at the top of `init_new_package` that
verifies `git`, `just`, and `uv` resolve on `PATH` before any subprocess runs or
any directory is created. A missing tool raises a single `RuntimeError` naming
all absent tools, funneled through `main`'s existing `except RuntimeError`
handler to a stderr message and exit code 1.

## Assumptions (resolved)

- **Test environment has `git`, `just`, `uv` on PATH.** The existing happy-path
  tests (`test_main.py:280-310`) patch only `Popen`, not `shutil.which`. With the
  preflight inserted, those tests will call the real `shutil.which`, which
  returns a truthy path and lets them proceed unchanged. This is safe: the
  Justfile drives everything through `uv`, and `test_e2e.py:55-57` already
  requires these tools — any environment running `just test` has them. Per the
  surgical-change rule (`CLAUDE.md` §3) and `structure.md`, these tests are left
  **unchanged**.
- **Message wording (Open Risk in design.md, Decision 4).** Resolved to a single
  combined line that names all missing tools plus one generic remedy and the
  `just` install URL already used at `main.py:516-519` — avoids three per-tool
  URLs while staying in the em-dash + install-pointer style.

---

## Phase 1: Preflight check that fails fast before any subprocess

Adds the production PATH check end-to-end (import, constant, helper, call site)
plus unit tests. After this phase, a missing tool aborts scaffolding **before**
any `Popen` runs and before the clone directory is created.

### Changes

#### 1. Add `shutil` import
**File**: `modernpackage/main.py`
**Action**: modify (stdlib import block, `main.py:3-6`)

Insert `import shutil` in alphabetical position within the existing stdlib block:

```python
import os
import re
import shutil
import sys
import tomllib
```

#### 2. Add `_REQUIRED_TOOLS` module constant
**File**: `modernpackage/main.py`
**Action**: modify (module scope, near `_GIT_CLONE_ERROR_MESSAGES` at
`main.py:19`; place it after the `_GIT_CLONE_ERROR_MESSAGES` table or directly
above `humanize_git_clone_error`)

Mirrors `test_e2e.py:28` exactly so the two tuples never drift:

```python
# Required executables that must resolve on PATH before scaffolding begins.
_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')
```

#### 3. Add `_verify_required_tools` helper
**File**: `modernpackage/main.py`
**Action**: create (new module-private function; place directly above
`init_new_package` at `main.py:470`)

For Phase 1 the message simply names the missing tool(s); Phase 2 refines the
wording (no signature change). Collect **all** missing tools so one run reports
every gap:

```python
def _verify_required_tools() -> None:
    """Raise RuntimeError if any required executable is absent from PATH."""
    missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f'required tool(s) not found on PATH: {", ".join(missing)}')
```

#### 4. Call the helper first in `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify (`init_new_package`, insert after `new_package_path = ...` at
`main.py:481`, **before** the `git clone` `Popen` at `main.py:483`)

```python
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

    _verify_required_tools()

    pipe = Popen(  # noqa: S603
        ['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path],  # noqa: S607
```

#### 5. Add unit tests
**File**: `tests/test_main.py`
**Action**: modify (add `_verify_required_tools` and `_REQUIRED_TOOLS` to the
`from modernpackage.main import (...)` block at `test_main.py:9-25`; append new
tests near the existing `init_new_package` tests, after `test_main.py:341`)

Patch the seam `modernpackage.main.shutil.which` (per design Patterns + Open
Risk). Each per-tool test also patches `modernpackage.main.Popen` and asserts it
is never called (no subprocess, no directory created):

```python
def test_verify_required_tools_missing_git() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'git' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
    ):
        with pytest.raises(RuntimeError, match='git'):
            init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_missing_just() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'just' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
    ):
        with pytest.raises(RuntimeError, match='just'):
            init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_missing_uv() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'uv' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
    ):
        with pytest.raises(RuntimeError, match='uv'):
            init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_all_present() -> None:
    with patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool') as which_mock:
        _verify_required_tools()
    assert which_mock.call_count == len(_REQUIRED_TOOLS)
```

### Verification

#### Automated
- [x] `cd /home/niekas/tools/modernpackage && just check` exits 0 (format, lint,
  complexity ≤ 10, typecheck, test, audit).
- [x] `cd /home/niekas/tools/modernpackage && just test -k verify_required_tools`
  exits 0 and reports the four new tests as `passed`.
- [x] `cd /home/niekas/tools/modernpackage && just test -k init_new_package`
  exits 0 — existing happy-path / failure tests (`test_main.py:280-341`) remain
  green.

#### Manual
- [x] `grep -q 'import shutil' /home/niekas/tools/modernpackage/modernpackage/main.py`
  → exit 0.
- [x] `grep -q "_REQUIRED_TOOLS: tuple\[str, ...\] = ('git', 'just', 'uv')" /home/niekas/tools/modernpackage/modernpackage/main.py`
  → exit 0.
- [x] `grep -q '_verify_required_tools()' /home/niekas/tools/modernpackage/modernpackage/main.py`
  → exit 0 (call site present).
- [x] Confirm fail-fast ordering — the helper call appears before the first
  `Popen`:
  `cd /home/niekas/tools/modernpackage && python -c "import re,inspect; from modernpackage import main; src=inspect.getsource(main.init_new_package); assert src.index('_verify_required_tools()') < src.index('Popen('), 'check must precede first Popen'; print('ok')"`
  → prints `ok`.
- [x] No directory created when a tool is missing:
  `cd /home/niekas/tools/modernpackage && python -c "from unittest.mock import patch; from modernpackage.main import init_new_package; import pytest
with patch('modernpackage.main.shutil.which', side_effect=lambda t: None if t=='git' else '/usr/bin/'+t):
    try:
        init_new_package('probe_pkg_xyz'); print('NO RAISE')
    except RuntimeError as e:
        print('raised:', e)"`
  → prints `raised: required tool(s) not found on PATH: git`, and
  `test ! -e /home/niekas/tools/modernpackage/probe_pkg_xyz` → exit 0.

---

## Phase 2: Report all missing tools with actionable install pointers

Upgrades the Phase 1 message to the project's em-dash + install-pointer wording,
listing all absent tools in one message (Design Decision 4). No signature
change.

### Changes

#### 1. Refine the `_verify_required_tools` message
**File**: `modernpackage/main.py`
**Action**: modify (the `raise` inside `_verify_required_tools`, from Phase 1)

```python
def _verify_required_tools() -> None:
    """Raise RuntimeError if any required executable is absent from PATH."""
    missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(
            f'required tool(s) not found on PATH: {", ".join(missing)}'
            ' — install the missing tool(s) before scaffolding.'
            ' See https://github.com/casey/just#installation'
        )
```

The single-tool names (`git`, `just`, `uv`) remain present in the message, so
the Phase 1 `match=` patterns still hold.

#### 2. Add a multiple-missing test; verify single-missing tests still pass
**File**: `tests/test_main.py`
**Action**: modify (append after the Phase 1 tests)

Mirrors the `str(exc_info.value)` substring style at `test_main.py:512-515`:

```python
def test_verify_required_tools_reports_all_missing() -> None:
    def which(tool: str) -> str | None:
        return None if tool in {'git', 'uv'} else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            init_new_package('mypackage')
    error_message = str(exc_info.value)
    assert 'git' in error_message
    assert 'uv' in error_message
    assert 'install' in error_message
    assert popen_mock.call_count == 0
```

### Verification

#### Automated
- [x] `cd /home/niekas/tools/modernpackage && just check` exits 0.
- [x] `cd /home/niekas/tools/modernpackage && just test -k verify_required_tools`
  exits 0 — all Phase 1 and Phase 2 tests `passed` (single-missing `match=`
  patterns still hold against the refined wording).

#### Manual
- [x] Combined message names both missing tools and includes a remedy:
  `cd /home/niekas/tools/modernpackage && python -c "from unittest.mock import patch; from modernpackage.main import _verify_required_tools
with patch('modernpackage.main.shutil.which', side_effect=lambda t: None if t in {'git','uv'} else '/usr/bin/'+t):
    try:
        _verify_required_tools()
    except RuntimeError as e:
        m=str(e); assert 'git' in m and 'uv' in m and 'install' in m, m; print('ok:', m)"`
  → prints `ok: required tool(s) not found on PATH: git, uv — install the missing tool(s) before scaffolding. See https://github.com/casey/just#installation`.
- [x] `grep -q 'install the missing tool' /home/niekas/tools/modernpackage/modernpackage/main.py`
  → exit 0.

---

## Testing Checkpoints

After **Phase 1** (resume-safe state):
- [x] `modernpackage/main.py` imports `shutil`, defines `_REQUIRED_TOOLS` and
  `_verify_required_tools`, and calls the helper first in `init_new_package`.
- [x] `just test -k verify_required_tools` reports the per-tool fail-fast tests
  as `passed`; `popen_mock.call_count == 0` holds in each.
- [x] Existing happy-path and `FileNotFoundError`-defense tests
  (`test_main.py:280-341`) remain green — the `just init` `FileNotFoundError`
  handler (`main.py:515-520`) is untouched.

After **Phase 2**:
- [x] A run with two missing tools produces one `RuntimeError` naming both, in
  the em-dash + install-pointer style.
- [x] `just check` passes with no new `# noqa` (the helper launches no
  subprocess).
- [x] No changes to `main`, `parse_args`, `_GIT_CLONE_ERROR_MESSAGES`, or the
  three existing subprocess call sites.
