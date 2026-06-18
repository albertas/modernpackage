# Implementation Plan

## Overview

Before scaffolding, the CLI prints a concise one-line-per-check preflight
checklist to **stdout** (`[ok]` / `[FAIL]`) covering every environment check,
then proceeds (happy path) or aborts before `Popen` (any check fails) with the
existing `RuntimeError` remediation still going to stderr. Single module change:
`modernpackage/main.py`, exercised by `tests/test_main.py`. Stdlib-only, no new
dependency, no styling.

## Context anchors (verify before editing — line numbers may have drifted)

- `_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')` — `main.py:56`.
- Three verifiers: `_verify_required_tools` (`main.py:484`),
  `_verify_target_directory_absent(target_path)` (`main.py:496`),
  `_verify_template_remote_reachable` (`main.py:506`). All return `None` on
  success, raise `RuntimeError` on failure. **Leave them unchanged.**
- The three direct calls to replace are inside `init_new_package`,
  `main.py:555-557`:
  ```python
  _verify_required_tools()
  _verify_target_directory_absent(new_package_path)
  _verify_template_remote_reachable()
  ```
  with `new_package_path = Path.cwd() / module_name` at `main.py:553`.
- `Callable` is imported **only under `TYPE_CHECKING`** (`main.py:14-15`) and the
  module has **no** `from __future__ import annotations`. The dataclass field
  annotation referencing `Callable` MUST be a string forward-reference, or it
  raises `NameError` at class-definition time. (Code Best Practices: forward-ref
  strings for types not available at runtime.)
- `@dataclass` is already imported from `dataclasses` (`main.py:9`).
- Every `print` carries `# noqa: T201` (ruff `flake8-print`).

---

## Phase 1: Happy-path checklist emitter

Introduce the check registry data model + orchestrator and emit the full `[ok]`
checklist on a clean run. Wire it into `init_new_package`, replacing the three
direct verifier calls. After this phase a successful scaffold prints the
checklist and proceeds to `Popen` exactly as before.

### Changes

#### 1. `PreflightCheck` dataclass + checklist constant/helper
**File**: `modernpackage/main.py`
**Action**: modify — add new definitions immediately **above** `_verify_required_tools`
(currently `main.py:484`), so the data model and helpers sit with the verifiers.

```python
@dataclass(frozen=True)
class PreflightCheck:
    label: str  # text shown after the status marker on the checklist line
    run: 'Callable[[], None]'  # verifier; returns None on success, raises RuntimeError on failure


_PREFLIGHT_HEADER: str = 'Preflight checks:'


def _format_check_line(label: str, *, ok: bool) -> str:
    """Return one indented checklist line; marker right-padded to width 6 so labels align."""
    marker = '[ok]' if ok else '[FAIL]'
    return f'  {marker:<6} {label}'
```

Notes:
- `run: 'Callable[[], None]'` is a **string** (forward-ref) because `Callable`
  is `TYPE_CHECKING`-only. Do not unquote it.
- `:<6` left-justifies the marker in a 6-char field: `[ok]` → `'[ok]  '` (then
  the literal space yields 3 spaces before the label); `[FAIL]` → `'[FAIL]'`
  (1 space before the label). This reproduces the design's sample output exactly.
- `ok` is keyword-only to read clearly at call sites (`ok=False`).

#### 2. `_run_preflight_checks` orchestrator
**File**: `modernpackage/main.py`
**Action**: modify — add immediately **after** `_verify_template_remote_reachable`
(currently ends `main.py:539`) and **before** `init_new_package` (currently
`main.py:542`).

```python
def _run_preflight_checks(target_path: Path) -> None:
    """Print the preflight checklist to stdout, running each check in order.

    The registry is built per-call so `_verify_target_directory_absent` binds
    `target_path` via closure. Each check's verifier raises RuntimeError on
    failure; Phase 1 emits only the success path (all `[ok]`).
    """
    checks = (
        PreflightCheck('package name valid', lambda: None),
        PreflightCheck(
            f'required tools on PATH ({", ".join(_REQUIRED_TOOLS)})',
            _verify_required_tools,
        ),
        PreflightCheck(
            'target directory available',
            lambda: _verify_target_directory_absent(target_path),
        ),
        PreflightCheck('template remote reachable', _verify_template_remote_reachable),
    )
    print(_PREFLIGHT_HEADER)  # noqa: T201
    for check in checks:
        check.run()
        print(_format_check_line(check.label, ok=True))  # noqa: T201
```

Notes:
- The `package name valid` check is display-only (Decision 5): the name is
  already validated at argparse time, so its `run` is a no-op `lambda: None`.
- The tools label is **derived** from `_REQUIRED_TOOLS`, never hardcoded
  (Decision / Open Risk: label drift).
- Phase 1 deliberately has no `try/except`; a raising verifier propagates as
  today (no `[FAIL]` line yet). Phase 2 adds the failure marking.

#### 3. Wire into `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify — replace the three direct calls at `main.py:555-557` with a
single orchestrator call.

```python
    _run_preflight_checks(new_package_path)
```

(Replaces exactly:)
```python
    _verify_required_tools()
    _verify_target_directory_absent(new_package_path)
    _verify_template_remote_reachable()
```

#### 4. New happy-path test
**File**: `tests/test_main.py`
**Action**: modify — add a test (place it near the existing
`test_init_new_package_reports_check_passed`, ~`test_main.py:569`). Optionally add
`_run_preflight_checks` to the import block (`test_main.py:10-30`) if calling it
directly; the test below drives it through `init_new_package` and does not need
the extra import.

Use `capsys` rather than mocking `print`, so the assertion reads real stdout and
verifies both ordering and the leading-spaces formatting:

```python
def test_run_preflight_checks_prints_full_checklist_on_clean_run(capsys) -> None:
    with (
        patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'),
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    out = capsys.readouterr().out
    expected = [
        'Preflight checks:',
        '  [ok]   package name valid',
        '  [ok]   required tools on PATH (git, just, uv)',
        '  [ok]   target directory available',
        '  [ok]   template remote reachable',
    ]
    # each expected line present and in order
    indices = [out.index(line) for line in expected]
    assert all(line in out for line in expected)
    assert indices == sorted(indices)
    assert popen_mock.call_count >= 1  # reached scaffolding
```

### Verification
#### Automated
- [x] `just test` passes (default `-m 'not e2e'`).
- [x] `uv run pytest tests/test_main.py::test_run_preflight_checks_prints_full_checklist_on_clean_run -q` passes.
- [x] Existing happy-path tests still reach `Popen`:
      `uv run pytest tests/test_main.py::test_init_new_package_reports_check_passed -q` passes.

#### Manual
- [x] Orchestrator wired in (no leftover direct calls):
      `grep -n '_run_preflight_checks(new_package_path)' modernpackage/main.py` prints one line, and
      `grep -c '_verify_required_tools()' modernpackage/main.py` returns `1` (only the function definition; the bare call site in `init_new_package` is gone).
- [x] Forward-ref annotation is a string:
      `grep -q "run: 'Callable\[\[\], None\]'" modernpackage/main.py && echo OK` prints `OK`.
- [x] Header + 4 ok-lines emitted in order on a clean run:
      ```
      uv run python -c "
      from unittest.mock import patch, MagicMock
      from modernpackage.main import init_new_package
      with patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'), \
           patch('modernpackage.main.Popen') as p, \
           patch('modernpackage.main.run') as r:
          r.return_value = MagicMock(returncode=0, stderr='')
          p.return_value.returncode = 0
          p.return_value.communicate.return_value = (b'', b'')
          init_new_package('mypackage')
      "
      ```
      Output contains, in order: `Preflight checks:`, `  [ok]   package name valid`,
      `  [ok]   required tools on PATH (git, just, uv)`, `  [ok]   target directory available`,
      `  [ok]   template remote reachable`. ✓ Verified.

---

## Phase 2: Failure-path `[FAIL]` marking

Extend the orchestrator so the first verifier that raises is marked `[FAIL]`,
prior checks already printed `[ok]`, the `RuntimeError` re-propagates to `main()`
(stderr remediation unchanged), and `Popen` is never reached. Delivers the
"at a glance what failed" value on top of Phase 1.

### Changes

#### 1. Wrap each check; mark `[FAIL]` then re-raise
**File**: `modernpackage/main.py`
**Action**: modify — change the loop body of `_run_preflight_checks` to catch
`RuntimeError`, print the `[FAIL]` line, and bare-`raise`.

```python
    print(_PREFLIGHT_HEADER)  # noqa: T201
    for check in checks:
        try:
            check.run()
        except RuntimeError:
            print(_format_check_line(check.label, ok=False))  # noqa: T201
            raise
        print(_format_check_line(check.label, ok=True))  # noqa: T201
```

Notes:
- Bare `raise` preserves the original message and the `__cause__` chain
  (e.g. the `raise ... from error` timeout case).
- Checks after the failing one never run and are never printed (Decision 3:
  abort on first failure; printed lines reflect exactly what ran).
- Only `RuntimeError` is caught — the verifiers' sole failure type. Other
  exceptions propagate untouched.

#### 2. Failure-path test (last check fails)
**File**: `tests/test_main.py`
**Action**: modify — add near `test_init_new_package_aborts_when_remote_unreachable`
(~`test_main.py:627`).

```python
def test_run_preflight_checks_marks_failing_check_and_aborts(capsys) -> None:
    with (
        patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'),
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(
            returncode=2, stderr='fatal: Could not resolve host: github.com'
        )
        with pytest.raises(RuntimeError, match='repository unreachable'):
            init_new_package('mypackage')
    captured = capsys.readouterr()
    out = captured.out
    assert '  [ok]   package name valid' in out
    assert '  [ok]   required tools on PATH (git, just, uv)' in out
    assert '  [ok]   target directory available' in out
    assert '  [FAIL] template remote reachable' in out
    assert popen_mock.call_count == 0
```

Note: the remediation text travels via the raised `RuntimeError` (re-raised out
of `init_new_package`); in production `main()` prints it to **stderr**. This test
asserts on the raise (via `pytest.raises(match=...)`) and on the stdout checklist
separately, keeping `.out`/`.err` concerns distinct (Open Risk: stream split).

#### 3. Failure-path test (earlier check fails)
**File**: `tests/test_main.py`
**Action**: modify — add adjacent to the test above. Confirms only lines up to and
including the `[FAIL]` line are printed (later checks absent).

```python
def test_run_preflight_checks_aborts_on_earlier_check_without_later_lines(capsys) -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'git' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        with pytest.raises(RuntimeError, match='git'):
            init_new_package('mypackage')
    out = capsys.readouterr().out
    assert '  [ok]   package name valid' in out
    assert '  [FAIL] required tools on PATH (git, just, uv)' in out
    # later checks did not run, so their lines are absent
    assert 'target directory available' not in out
    assert 'template remote reachable' not in out
    assert popen_mock.call_count == 0
```

### Verification
#### Automated
- [x] `just test` passes.
- [x] `uv run pytest tests/test_main.py::test_run_preflight_checks_marks_failing_check_and_aborts tests/test_main.py::test_run_preflight_checks_aborts_on_earlier_check_without_later_lines -q` passes.
- [x] Existing preflight-abort tests still green:
      `uv run pytest tests/test_main.py -k "aborts_when or missing_git or missing_just or missing_uv or reports_all_missing" -q` passes.

#### Manual
- [x] `try/except RuntimeError` with bare re-raise is present in the orchestrator:
      `grep -n 'except RuntimeError' modernpackage/main.py` shows a line inside `_run_preflight_checks`.
- [x] Failing last check prints `[FAIL]` and never reaches `Popen`:
      ```
      uv run python -c "
      from unittest.mock import patch, MagicMock
      from modernpackage.main import init_new_package
      with patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'), \
           patch('modernpackage.main.Popen') as p, \
           patch('modernpackage.main.run') as r:
          r.return_value = MagicMock(returncode=2, stderr='fatal: Could not resolve host: github.com')
          try:
              init_new_package('mypackage')
          except RuntimeError as e:
              print('RAISED:', str(e).splitlines()[0])
          assert p.call_count == 0, 'Popen must not be reached'
      "
      ```
      stdout contains `  [ok]   target directory available` and `  [FAIL] template remote reachable`
      followed by a `RAISED: repository unreachable ...` line; no traceback (assertion holds). ✓ Verified.

---

## Phase 3: Regression hardening of existing output assertions

No new feature. Confirm the inserted checklist lines do not break existing
print/`capsys` assertions, and fix any index-based ones. Keep the full suite green.

### Changes

#### 1. Audit existing output-inspecting assertions
**File**: `tests/test_main.py`
**Action**: modify only if an audit finds a positional assertion (no production code).

Audit findings from the current tree (these already filter by **content**, so they
tolerate the extra checklist lines — expected to need **no change**):
- `test_main_surfaces_stderr_on_failure` (`test_main.py:485-499`): asserts on
  `print_mock.call_args.args[0]` of `main()`, which mocks `init_new_package`
  entirely — checklist never prints here. Unaffected.
- `test_init_new_package_reports_check_passed` (`test_main.py:569-581`): uses
  `any('just check passed' in call for call in printed_calls)`. Content filter — unaffected.
- `test_init_new_package_reports_check_failed` (`test_main.py:584-605`): uses
  `any('just check failed' in call ...)` / `any('1' in call ...)`. Content filter — unaffected.

Note: `any('1' in call ...)` at `test_main.py:604` matches the digit `1` anywhere in
any printed call. The checklist lines contain no stray `1`, but even if they did this
assertion only needs **one** match and still passes. No change required.

- `popen_mock.call_count == 0` preflight-abort tests (`test_main.py:385, 400, 415,
  442, 637`, plus the directory-exists abort ~`test_main.py:1087`): these assert
  abort-before-`Popen`, which the orchestrator preserves (first raise propagates
  before `Popen`). Unaffected.

If — and only if — `just test` surfaces a failure tied to a positional/index-based
output assertion, convert that assertion to a content filter (`any(<substring> in
call for call in printed_calls)`) matching its original target message. Do not
otherwise touch these tests.

### Verification
#### Automated
- [x] `just test` passes with zero failures.
- [x] `just check` passes end-to-end (format, lint, complexity ≤ 10, typecheck,
      test, audit). This confirms `_run_preflight_checks` stays under McCabe ≤ 10
      (`check-complexity`) and the new `# noqa: T201` prints raise no lint
      regressions (`check-lint`).

#### Manual
- [x] No positional output assertion was silently broken — every print-inspecting
      test still passes:
      `uv run pytest tests/test_main.py -k "surfaces_stderr or reports_check or checklist or preflight" -q` passes.
- [x] Complexity gate specifically green on the new orchestrator:
      `uv run ruff check --select C901 modernpackage tests` exits 0.
- [x] Lint clean on the new prints:
      `uv run ruff check modernpackage/main.py` exits 0 (no `T201` escapes).

---

## Testing Checkpoints (from structure.md)

- **After Phase 1**: `_run_preflight_checks` exists; a clean run prints
  `Preflight checks:` + four `[ok]` lines (registry order; tools label derived
  from `_REQUIRED_TOOLS`) to stdout and still reaches `Popen`. `init_new_package`
  has a single preflight call site. Failure behavior unchanged from baseline.
- **After Phase 2**: a failing check prints its line as `[FAIL]` with prior lines
  `[ok]`; the `RuntimeError` propagates (to stderr via `main()`); `Popen` is never
  reached (`popen_mock.call_count == 0`). Checklist `.out` and remediation `.err`
  on separate streams.
- **After Phase 3**: entire suite (`just test`) and `just check` pass; no existing
  print-assertion test broken by the added checklist lines.

## Resolved assumptions

- **`capsys` over `patch('...print')` for new tests** — the design's verification
  asks for ordered-line assertions; `capsys` reads real stdout and naturally
  verifies ordering and the leading-spaces formatting. Existing tests that mock
  `print` are left as-is.
- **`ok` is keyword-only** in `_format_check_line` for call-site readability; not
  mandated by the structure but consistent with the codebase's explicit style.
- **No new import needed in tests** — the new tests drive `_run_preflight_checks`
  through `init_new_package` (already imported). Add a direct import only if a
  future unit test calls the orchestrator in isolation.
- **Phase 3 likely touches no code** — all current output assertions filter by
  content; the phase is a verification gate. The audit instruction stands in case
  the suite reveals an index-based assertion not visible in the sampled lines.
