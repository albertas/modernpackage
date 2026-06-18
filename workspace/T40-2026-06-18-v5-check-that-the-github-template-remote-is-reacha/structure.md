# Structure Outline

## Approach

Add a pre-flight probe that confirms the template remote is reachable with
`git ls-remote <url>` (via the existing `run(check=False, capture_output=True,
text=True)` idiom) *before* the clone `Popen`, reusing
`humanize_git_clone_error` for friendly messages. Introduce a single
`_TEMPLATE_REPOSITORY_URL` constant (plus a timeout constant) to feed both the
probe and the clone. All changes live in `modernpackage/main.py` +
`tests/test_main.py`.

This is a naturally small, single-module feature, so "vertical slices" are thin:
each slice still crosses logic → error-humanization → tests and is
independently runnable. Slice 1 delivers a standalone, tested helper; Slice 2
wires it into the flow and repairs the test cascade.

---

## Phase 1: Constants + reachability helper (standalone, unit-tested)

Introduce the module-level constants and the `_verify_template_remote_reachable`
helper, fully tested in isolation by patching `modernpackage.main.run`. The
helper is callable and verifiable even before it is wired into the flow, and the
URL constant immediately replaces the metadata-replacement literal.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'`
  — new module-level constant (near `_REQUIRED_TOOLS`, `main.py:56`).
- `_REMOTE_REACHABILITY_TIMEOUT_SECONDS: int = 10` — new module-level constant.
- `_verify_template_remote_reachable() -> None` — new helper. Runs
  `run(['git', 'ls-remote', _TEMPLATE_REPOSITORY_URL], check=False,
  capture_output=True, text=True, timeout=_REMOTE_REACHABILITY_TIMEOUT_SECONDS)`
  with `# noqa: S603` on the call / `# noqa: S607` on the argv. On
  `returncode != 0`: `raw = f'template remote unreachable (git ls-remote exit
  code {result.returncode}): {result.stderr.strip()}'`,
  `friendly = humanize_git_clone_error(result.stderr)`, raise `RuntimeError`
  with `f'{friendly}\n\n{raw}'` if matched else `raw`. On
  `subprocess.TimeoutExpired`: raise `RuntimeError` with the network/unreachable
  friendly message directly. Returns `None` silently when reachable.
- Update `_write_package_metadata` replacement target (`main.py:448`) to
  reference `_TEMPLATE_REPOSITORY_URL` instead of the bare literal.

**Verify**: `just test` passes. New direct unit tests (mirroring
`tests/test_main.py:586-606`, the `_git_config_default` `run`-seam tests):
- `patch('modernpackage.main.run')` → `MagicMock(returncode=0, stderr='')`:
  `_verify_template_remote_reachable()` returns `None`, does not raise.
- `returncode=2, stderr='fatal: Could not resolve host: github.com'`:
  `pytest.raises(RuntimeError, match='repository unreachable')`; message also
  contains `'git ls-remote exit code 2'`.
- `returncode=128, stderr='remote: Repository not found'`: raises, message
  contains the repo-not-found friendly fragment + raw fragment.
- `run` raising `subprocess.TimeoutExpired`: raises `RuntimeError` with the
  network friendly fragment.
- `just check` passes (lint/format/typecheck green: constant typed, helper
  annotated `-> None`, `# noqa` present).

---

## Phase 2: Wire the probe into `init_new_package` + repair test cascade

Call `_verify_template_remote_reachable()` after the two existing pre-flight
checks and before the clone `Popen`, and switch the clone argv to the URL
constant. Update every existing `init_new_package` test to also patch
`modernpackage.main.run` so it no longer makes a live `ls-remote` call.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- In `init_new_package`, insert `_verify_template_remote_reachable()` between
  `_verify_target_directory_absent(new_package_path)` (`main.py:511`) and the
  clone `Popen` (`main.py:513`).
- Replace the bare URL literal in the clone argv (`main.py:514`) with
  `_TEMPLATE_REPOSITORY_URL`.
- Existing tests that `patch('modernpackage.main.Popen')`
  (`tests/test_main.py:284,292,307,317,328,341,353,366,379,399,537,559,571,
  1024,1037`) gain `patch('modernpackage.main.run')` returning
  `MagicMock(returncode=0, stderr='')` so the probe passes by default.
- New end-to-end test: probe fails (`run` → `returncode=2,
  stderr='fatal: Could not resolve host: github.com'`) with `Popen` patched →
  `RuntimeError` raised AND `popen_mock.call_count == 0` (clone never reached),
  mirroring the existing pre-flight assertion style
  (`tests/test_main.py:357,370`).

**Verify**: `just check` (runs `format`, `lint`, `typecheck`, `test`) all green.
Specifically:
- `just test` passes — the 3-`Popen`-count assertion (`tests/test_main.py:288`)
  and clone-as-`call_args_list[0]` index (`:297`) still hold (probe uses `run`,
  not `Popen`).
- New failing-probe test: `popen_mock.call_count == 0` and
  `pytest.raises(RuntimeError, match='repository unreachable')`.
- Grep check: `rg -c 'https://github.com/albertas/modernpackage'
  modernpackage/main.py` returns 0 (no remaining bare literal in `main.py`;
  both uses now go through `_TEMPLATE_REPOSITORY_URL`).
- Confirm `tests/test_e2e.py` is untouched and still green (it does not call
  `init_new_package`; research.md:152-154) — `just test` covers it.

---

## Testing Checkpoints

- **After Phase 1**: `_verify_template_remote_reachable` exists and is fully
  unit-tested via the `run` seam (reachable, resolve-host, repo-not-found,
  timeout cases). The URL constant exists and is used by the metadata
  replacement. The helper is NOT yet called by `init_new_package`, so the clone
  flow is unchanged and all prior tests still pass. `just check` green.
- **After Phase 2**: `init_new_package` fails fast on an unreachable remote
  before any `Popen`; the clone argv uses the constant; no bare URL literal
  remains in `main.py`; every `init_new_package` test patches `run`; the
  3-`Popen` count and clone-index assertions still hold. `just check` green.
- **Resume cue**: if context resets, check whether
  `_verify_template_remote_reachable` is called inside `init_new_package`
  (Phase 2 done) vs. only defined (Phase 1 done), and whether
  `rg 'https://github.com/albertas/modernpackage' modernpackage/main.py`
  returns any hits (should be 0 after Phase 2).
