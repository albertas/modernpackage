# Implementation Plan

## Overview

Add a pre-flight `git ls-remote` reachability probe that fails fast (with the
existing friendly + raw clone-error message style) before `init_new_package`
attempts to clone, and replace the duplicated bare template-URL literal with a
single `_TEMPLATE_REPOSITORY_URL` constant.

All production changes live in `modernpackage/main.py`; all test changes live in
`tests/test_main.py`.

---

## Phase 1: Constants + reachability helper (standalone, unit-tested)

Introduce the module-level constants and the `_verify_template_remote_reachable`
helper, fully tested in isolation by patching `modernpackage.main.run`. The
helper is NOT yet wired into `init_new_package` in this phase, so the clone flow
and all existing tests are unchanged. The URL constant immediately replaces the
metadata-replacement literal at `main.py:447`.

### Changes

#### 1. Import `TimeoutExpired`
**File**: `modernpackage/main.py`
**Action**: modify (line 11)

The helper catches `subprocess.TimeoutExpired`, which is not currently imported.

```python
from subprocess import PIPE, Popen, TimeoutExpired, run
```

#### 2. New module-level constants
**File**: `modernpackage/main.py`
**Action**: modify — add immediately after `_REQUIRED_TOOLS` (currently
`main.py:56`).

```python
# Required executables that must resolve on PATH before scaffolding begins.
_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')


# Template repository cloned to scaffold a new package; used by the reachability
# probe and the clone, and as the metadata-replacement target.
_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'

# Upper bound (seconds) on the pre-flight `git ls-remote` reachability probe so a
# hung DNS/connect cannot defeat fail-fast.
_REMOTE_REACHABILITY_TIMEOUT_SECONDS: int = 10
```

#### 3. New reachability helper
**File**: `modernpackage/main.py`
**Action**: modify — add a new `_verify_*` helper. Place it alongside the other
pre-flight validators, immediately after `_verify_target_directory_absent`
(currently ends `main.py:494`) and before `init_new_package`.

Mirrors the `run`-as-probe idiom of `_git_config_default` (`main.py:222-227`):
`run(check=False, capture_output=True, text=True)` so `result.stderr` is already
`str` (no double-decode). Reuses `humanize_git_clone_error` — no new patterns.
On `TimeoutExpired` there is no stderr to classify, so the network friendly
message is built directly.

```python
def _verify_template_remote_reachable() -> None:
    """Raise RuntimeError if the template remote cannot be reached.

    Pre-flight probe (design Decision 1): `git ls-remote` contacts the remote
    without cloning, and its stderr is already classified by
    `humanize_git_clone_error`. Returns None silently when reachable. Bounded by
    `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` so a hung connect still fails fast.
    """
    try:
        result = run(  # noqa: S603
            ['git', 'ls-remote', _TEMPLATE_REPOSITORY_URL],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=_REMOTE_REACHABILITY_TIMEOUT_SECONDS,
        )
    except TimeoutExpired as error:
        friendly = 'repository unreachable — check your network connection'
        raw = (
            'template remote unreachable (git ls-remote timed out after'
            f' {_REMOTE_REACHABILITY_TIMEOUT_SECONDS}s)'
        )
        raise RuntimeError(f'{friendly}\n\n{raw}') from error

    if result.returncode != 0:
        stderr_text = result.stderr.strip()
        raw = (
            'template remote unreachable (git ls-remote exit code'
            f' {result.returncode}): {stderr_text}'
        )
        friendly = humanize_git_clone_error(stderr_text)
        message = f'{friendly}\n\n{raw}' if friendly else raw
        raise RuntimeError(message)
```

#### 4. Use the constant in `_write_package_metadata`
**File**: `modernpackage/main.py`
**Action**: modify (currently `main.py:446-449`). Replace the bare literal
`str.replace` target with the constant.

```python
    if repository_url is not None:
        updated = updated.replace(
            _TEMPLATE_REPOSITORY_URL,
            _toml_escape(repository_url),
        )
```

#### 5. Unit tests for the helper
**File**: `tests/test_main.py`
**Action**: modify — add tests mirroring the `_git_config_default` `run`-seam
tests (`tests/test_main.py:585-606`). Add `_verify_template_remote_reachable` to
the `from modernpackage.main import (...)` block (`tests/test_main.py:9-28`).
`MagicMock` and `patch` are already imported (`tests/test_main.py:4`).

Note: `result.stderr.strip()` is called on the mock, so set `stderr` to a real
`str` (not a bare `MagicMock`) in every mock.

```python
def test_verify_template_remote_reachable_returns_none_when_reachable() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        assert _verify_template_remote_reachable() is None


def test_verify_template_remote_reachable_raises_on_resolve_host() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(
            returncode=2, stderr='fatal: Could not resolve host: github.com'
        )
        with pytest.raises(RuntimeError, match='repository unreachable') as exc_info:
            _verify_template_remote_reachable()
    message = str(exc_info.value)
    assert 'check your network' in message
    assert 'git ls-remote exit code 2' in message
    assert 'Could not resolve host' in message


def test_verify_template_remote_reachable_raises_on_repo_not_found() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(
            returncode=128, stderr='remote: Repository not found'
        )
        with pytest.raises(RuntimeError) as exc_info:
            _verify_template_remote_reachable()
    message = str(exc_info.value)
    assert 'template repository not found' in message
    assert 'git ls-remote exit code 128' in message


def test_verify_template_remote_reachable_raises_on_timeout() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.side_effect = TimeoutExpired(cmd='git ls-remote', timeout=10)
        with pytest.raises(RuntimeError, match='repository unreachable') as exc_info:
            _verify_template_remote_reachable()
    message = str(exc_info.value)
    assert 'check your network' in message
    assert 'timed out' in message
```

`TimeoutExpired` must be imported in the test module:

```python
from subprocess import TimeoutExpired
```

### Verification
#### Automated
- [x] `just test` passes (all existing tests still green; helper not yet wired).
- [x] `just check` passes (format, lint, complexity, typecheck, test, audit).
- [x] `uv run pytest tests/test_main.py -k verify_template_remote_reachable`
      runs the 4 new tests and they pass.

#### Manual
- [x] `rg -n "_TEMPLATE_REPOSITORY_URL" modernpackage/main.py` → matches on the
      constant definition, the `_write_package_metadata` replacement, and (after
      Phase 2) the clone argv; in Phase 1 expect 2 hits (definition + metadata).
      NOTE: 3 hits observed — definition (L61), metadata replacement (L456), and
      the `git ls-remote` call inside `_verify_template_remote_reachable` (L516).
      All 3 are valid Phase 1 uses of the constant.
- [x] `rg -n "TimeoutExpired" modernpackage/main.py` → import line (L11) +
      `except TimeoutExpired` in the helper (L522).
- [x] `rg -n "_verify_template_remote_reachable\(\)" modernpackage/main.py` →
      1 hit on the definition line (`def _verify_template_remote_reachable() -> None:`);
      no call sites outside the definition — confirms Phase 1 scope.

---

## Phase 2: Wire the probe into `init_new_package` + repair test cascade

Call `_verify_template_remote_reachable()` after the two existing pre-flight
checks and before the clone `Popen`, switch the clone argv to the URL constant,
and update every existing `init_new_package` test to also patch
`modernpackage.main.run` so no test makes a live `ls-remote` call.

### Changes

#### 1. Wire the probe and use the constant in the clone argv
**File**: `modernpackage/main.py`
**Action**: modify (currently `main.py:510-514`). Insert the probe call between
`_verify_target_directory_absent(...)` and the clone `Popen`, and replace the
bare URL literal in the clone argv.

```python
    _verify_required_tools()
    _verify_target_directory_absent(new_package_path)
    _verify_template_remote_reachable()

    pipe = Popen(  # noqa: S603
        ['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
```

#### 2. Patch `run` in every existing `init_new_package` test
**File**: `tests/test_main.py`
**Action**: modify. Every test that calls `init_new_package` while patching
`Popen` must now also patch `modernpackage.main.run` to return
`MagicMock(returncode=0, stderr='')` so the probe passes by default. Without
this, these tests would execute a real `git ls-remote` network call.

Tests to update (each currently patches only `Popen` — add a `run` patch in the
same `with`):
- `test_init_new_package` (`:283`)
- `test_init_new_package_normalizes_name` (`:291`)
- `test_init_new_package_runs_just_check` (`:306`)
- `test_init_new_package_git_clone_failure` (`:316`)
- `test_init_new_package_just_not_installed` (`:324`)
- `test_init_new_package_just_init_failure` (`:334`)
- `test_verify_required_tools_missing_git` (`:347`)
- `test_verify_required_tools_missing_just` (`:360`)
- `test_verify_required_tools_missing_uv` (`:373`)
- `test_verify_required_tools_reports_all_missing` (`:394`)
- `test_init_new_package_reports_check_passed` (`:535`)
- `test_init_new_package_reports_check_failed` (`:548`)
- `test_init_new_package_git_clone_network_failure` (`:570`)
- `test_init_new_package_aborts_when_target_directory_exists` (`:1019`)
- `test_init_new_package_proceeds_when_target_directory_absent` (`:1033`)

Pattern for each — add the `run` patch line and set its return value. Example
for the simple uniform-mock case (`test_init_new_package`):

```python
def test_init_new_package() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    assert popen_mock.call_count == 3  # noqa: PLR2004
```

Notes for the missing-tool tests (`test_verify_required_tools_missing_*`,
`test_verify_required_tools_reports_all_missing`,
`test_init_new_package_aborts_when_target_directory_exists`): these raise before
the probe is reached, so a `run` patch is defensive but harmless. Add it anyway
for consistency and to guarantee no live call if call order ever shifts.

The probe uses `run`, not `Popen`, so the `popen_mock.call_count == 3`
assertion (`:288`, `:1045`), the `call_args_list[0]`-is-clone index
(`:297`), and the `popen_mock.call_count == 0` pre-flight assertions
(`:357,370,383,408,1030`) all remain correct.

#### 3. New end-to-end probe-failure test
**File**: `tests/test_main.py`
**Action**: modify — add a test (next to the other `init_new_package` failure
tests, e.g. after `test_init_new_package_git_clone_network_failure` at `:582`)
asserting the probe fails before any clone, mirroring the pre-flight assertion
style (`:357`).

```python
def test_init_new_package_aborts_when_remote_unreachable() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(
            returncode=2, stderr='fatal: Could not resolve host: github.com'
        )
        with pytest.raises(RuntimeError, match='repository unreachable'):
            init_new_package('mypackage')
    assert popen_mock.call_count == 0
```

### Verification
#### Automated
- [x] `just check` passes (format, lint, complexity, typecheck, test, audit).
- [x] `just test` passes — specifically the 3-`Popen`-count assertions
      (`tests/test_main.py:288`, `:1045`) and the clone-as-`call_args_list[0]`
      index (`:297-299`) still hold.
- [x] `uv run pytest tests/test_main.py -k init_new_package` passes, including
      the new `test_init_new_package_aborts_when_remote_unreachable`.

#### Manual
- [x] `rg -c 'https://github.com/albertas/modernpackage' modernpackage/main.py`
      → `1` (the constant definition itself; all code uses go through the
      constant — no bare literal remains in any code path). Plan said `0` but
      the constant definition line always contains the URL; the intent is met.
- [x] `rg -n "_verify_template_remote_reachable\(\)" modernpackage/main.py` →
      2 hits: definition (L506) + call site (L557) inside `init_new_package`.
      Plan said "exactly 1" but the definition also matches `\(\)`; the 1 call
      site is correctly placed between the dir check and the clone `Popen`.
- [x] `rg -n "_TEMPLATE_REPOSITORY_URL" modernpackage/main.py` → 4 hits
      (definition, metadata replacement, ls-remote probe, clone argv). Plan
      said 3 because Phase 1 already added the ls-remote use; 4 is correct.
- [x] `git -C /home/niekas/tools/modernpackage diff --stat tests/test_e2e.py` →
      empty (e2e suite untouched; it does not call `init_new_package`,
      research.md:152-154, and is covered by `just test`).

---

## Testing Checkpoints

- **After Phase 1**: `_verify_template_remote_reachable` exists and is fully
  unit-tested via the `run` seam (reachable, resolve-host, repo-not-found,
  timeout). The URL constant exists and is used by the metadata replacement. The
  helper is NOT yet called by `init_new_package`, so the clone flow is unchanged
  and all prior tests pass. `just check` green.
- **After Phase 2**: `init_new_package` fails fast on an unreachable remote
  before any `Popen`; the clone argv uses the constant; no bare URL literal
  remains in `main.py`; every `init_new_package` test patches `run`; the
  3-`Popen` count and clone-index assertions still hold. `just check` green.
- **Resume cue**: if context resets, check whether
  `_verify_template_remote_reachable()` is called inside `init_new_package`
  (Phase 2 done) vs. only defined (Phase 1 done), and whether
  `rg 'https://github.com/albertas/modernpackage' modernpackage/main.py`
  returns any hits (should be 0 after Phase 2).
