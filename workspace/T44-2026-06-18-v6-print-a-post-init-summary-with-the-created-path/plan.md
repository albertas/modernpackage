# Implementation Plan

## Overview

On a successful scaffold, `init_new_package` prints an additive summary block —
created directory path, package (distribution) name, and the reset version
(`0.0.1`) — to stdout after the preserved `just check passed` line. First the
duplicated `0.0.1` literal is extracted into a `_RESET_VERSION` constant, then
the summary formatter/printer helpers are added and wired into the success
branch. All changes are confined to `modernpackage/main.py` and
`tests/test_main.py`.

## Phase 1: Extract `_RESET_VERSION` constant

Replace the hardcoded `'0.0.1'` literal in the dry-run formatter with a single
documented module constant so Phase 2 and the dry-run line share one source of
truth. Pure refactor — the rendered dry-run text is byte-identical.

### Changes

#### 1. New module constant `_RESET_VERSION`
**File**: `modernpackage/main.py`
**Action**: modify

Add the constant beside the existing header constants (`main.py:510-511`):

```python
_PREFLIGHT_HEADER: str = 'Preflight checks:'
_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'
# Version the template is reset to by `just init` (mirrors the Justfile sed
# value at Justfile:67; coupled by convention, not programmatically).
_RESET_VERSION: str = '0.0.1'
```

#### 2. Reference the constant in the dry-run plan
**File**: `modernpackage/main.py`
**Action**: modify

Change the version-reset line in `_format_dry_run_plan` (`main.py:555`) from the
literal to the constant:

```python
    lines.append(f'  run just init: reset version to {_RESET_VERSION}')
```

The resulting string is identical (`...reset version to 0.0.1`), so existing
assertions stay green.

### Verification
#### Automated
- [x] `just check` passes (format / lint / complexity / typecheck / test / audit).
- [x] `just test tests/test_main.py` passes — the dry-run test asserting
      `'0.0.1' in plan` (`tests/test_main.py:1360`) still passes unchanged.

#### Manual
- [x] `rg "0\.0\.1" modernpackage/main.py` prints exactly one match — the
      `_RESET_VERSION: str = '0.0.1'` definition line (no other literal remains
      in `main.py`).
- [x] `python -c "from modernpackage.main import _format_dry_run_plan; from pathlib import Path; print('0.0.1' in _format_dry_run_plan('demo', Path('/tmp/demo'), author_name=None, author_email=None, description=None, package_license=None, repository_url=None))"`
      prints `True`.

---

## Phase 2: Add and wire the init summary block

Introduce `_format_init_summary` (pure) + `_print_init_summary` (prints to
stdout) and call the printer in the success branch, immediately after the
existing `just check passed — ...` line and before `return 0`.

### Changes

#### 1. New module constant `_INIT_SUMMARY_HEADER`
**File**: `modernpackage/main.py`
**Action**: modify

Add beside the other header constants (after `_RESET_VERSION` from Phase 1):

```python
_INIT_SUMMARY_HEADER: str = 'Created package:'
```

#### 2. New formatter `_format_init_summary`
**File**: `modernpackage/main.py`
**Action**: create (add after `_print_dry_run_plan`, ending `main.py:580`)

Pure formatter returning a header line followed by 2-space-indented fields,
matching the dry-run plan body indentation (`main.py:544-555`). Do NOT copy the
stale `main.py:592` citation from `_print_dry_run_plan`'s docstring (design "Do
NOT follow").

```python
def _format_init_summary(package_name: str, created_path: Path) -> str:
    """Return the multi-line post-scaffold summary (design Decision 1).

    Reports the package/distribution name, the created directory path, and the
    version the template was reset to (`_RESET_VERSION`).
    """
    lines = [
        _INIT_SUMMARY_HEADER,
        f'  package name: {package_name}',
        f'  path: {created_path}',
        f'  version: {_RESET_VERSION}',
    ]
    return '\n'.join(lines)
```

#### 3. New printer `_print_init_summary`
**File**: `modernpackage/main.py`
**Action**: create (add directly after `_format_init_summary`)

Thin wrapper that prints the formatted block to stdout, mirroring
`_print_dry_run_plan` (`main.py:559-580`).

```python
def _print_init_summary(package_name: str, created_path: Path) -> None:
    """Print the formatted init summary to stdout."""
    print(_format_init_summary(package_name, created_path))  # noqa: T201
```

#### 4. Wire the printer into the success branch
**File**: `modernpackage/main.py`
**Action**: modify (`main.py:754-756`)

Add the summary call after the preserved `just check passed` line, before
`return 0`. The failure branch (`main.py:757-762`) and all return codes are
untouched.

```python
    if pipe.returncode == 0:
        print(f'just check passed — {module_name} scaffold is valid.')  # noqa: T201
        _print_init_summary(package_name, new_package_path)
        return 0
```

#### 5. New tests
**File**: `tests/test_main.py`
**Action**: create (add near the existing `test_init_new_package_reports_check_passed`, `tests/test_main.py:629`)

Unit test for the pure formatter:

```python
def test_format_init_summary_contains_all_fields() -> None:
    summary = _format_init_summary('demo-pkg', Path('/tmp/demo_pkg'))
    assert 'demo-pkg' in summary
    assert '/tmp/demo_pkg' in summary
    assert '0.0.1' in summary
```

Success-path test (mirrors `test_init_new_package_reports_check_passed`,
`tests/test_main.py:629-641`, using `patch('modernpackage.main.print')`):

```python
def test_init_new_package_prints_summary_on_success() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        result = init_new_package('mypackage')
    printed_calls = [str(call) for call in print_mock.call_args_list]
    assert any('just check passed' in call for call in printed_calls)
    assert any('mypackage' in call for call in printed_calls)
    assert any(str(Path.cwd() / 'mypackage') in call for call in printed_calls)
    assert any('0.0.1' in call for call in printed_calls)
    assert popen_mock.call_count == 3  # noqa: PLR2004
    assert result == 0
```

Ensure `_format_init_summary` is imported in the test module's import block
(alongside the other `from modernpackage.main import ...` symbols) and that
`Path` and `MagicMock`/`patch` are already imported (they are — used by existing
tests).

### Verification
#### Automated
- [x] `just check` passes (format / lint / complexity / typecheck / test / audit).
- [x] `just test tests/test_main.py::test_format_init_summary_contains_all_fields`
      passes.
- [x] `just test tests/test_main.py::test_init_new_package_prints_summary_on_success`
      passes.
- [x] `just test tests/test_main.py::test_init_new_package_reports_check_passed`
      still passes (existing `'just check passed'` substring assertion intact).
- [x] `just test tests/test_main.py::test_init_new_package_reports_check_failed`
      still passes (failure branch unchanged; no summary printed on failure).

#### Manual
- [x] `python -c "from modernpackage.main import _format_init_summary; from pathlib import Path; print(_format_init_summary('demo-pkg', Path('/tmp/demo_pkg')))"`
      prints a block whose stdout contains `demo-pkg`, `/tmp/demo_pkg`, and
      `0.0.1`.
- [x] `python -c "from modernpackage.main import _format_init_summary; from pathlib import Path; s=_format_init_summary('demo-pkg', Path('/tmp/demo_pkg')); assert s.startswith('Created package:'); print('ok')"`
      prints `ok` (header line present and first).
- [x] `rg "_print_init_summary\(package_name, new_package_path\)" modernpackage/main.py`
      shows the call wired in the success branch.

---

## Testing Checkpoints

- **After Phase 1**: `_RESET_VERSION` is the sole `'0.0.1'` source in
  `main.py`; dry-run plan text is byte-identical; `just check` green. Feature
  not yet user-visible — a safe, self-contained refactor that can ship alone.
- **After Phase 2**: A successful `init_new_package` run prints the additive
  summary block (created path + package name + reset version) to stdout after
  the preserved `just check passed` line; new unit + success-path tests pass;
  failure branch and return codes (`0` success, `1` failure) unchanged; full
  `just check` green.

If context resets: verify state by grepping `_RESET_VERSION`,
`_INIT_SUMMARY_HEADER`, `_format_init_summary`, and `_print_init_summary` in
`modernpackage/main.py`. Phase 2 depends on `_RESET_VERSION` from Phase 1.
