# Structure Outline

## Approach

Add an additive post-`just check` success summary to `init_new_package` that
reports the created directory path, the package (distribution) name, and the
reset version (`0.0.1`). Follow the existing formatter/printer split
(`_format_*` builds text, `_print_*` prints to stdout) and the header-constant
convention. First extract the duplicated `0.0.1` literal into a
`_RESET_VERSION` constant (so the summary doesn't add a third hardcoded copy),
then build the summary helpers and wire them into the success branch. All
changes are confined to `modernpackage/main.py` and `tests/test_main.py`.

---

## Phase 1: Extract `_RESET_VERSION` constant

Replace the hardcoded `'0.0.1'` literal in the dry-run formatter with a single
documented module constant, so later phases (and the dry-run line) share one
source of truth. Pure refactor — no behavior change.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_RESET_VERSION: str = '0.0.1'` — new module constant, placed next to
  `_PREFLIGHT_HEADER` / `_DRY_RUN_HEADER` (`main.py:510-511`), with a comment
  noting it mirrors the `Justfile:67` sed value (coupled by convention, not
  programmatically — design Decision 4).
- `_format_dry_run_plan(...)` — modify the version-reset line
  (`main.py:555`) from the literal to
  `f'  run just init: reset version to {_RESET_VERSION}'`.

**Verify**: `just check` passes. `just test` passes — existing dry-run test
asserting `'0.0.1' in plan` (`tests/test_main.py:1360`) still passes unchanged,
confirming the rendered text is identical. Confirm no remaining `'0.0.1'`
literal in `main.py` outside the constant:
`rg "0\.0\.1" modernpackage/main.py` shows only the `_RESET_VERSION`
definition line.

---

## Phase 2: Add and wire the init summary block

Introduce `_format_init_summary` (pure) + `_print_init_summary` (prints to
stdout) and call the printer in the success branch, immediately after the
existing `just check passed — ...` line and before `return 0`. Delivers the
end-to-end feature: a successful scaffold now prints the created path, package
name, and reset version.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_INIT_SUMMARY_HEADER: str = 'Created package:'` — new module constant beside
  the other header constants (exact wording at author's discretion; must be a
  stable header line).
- `_format_init_summary(package_name: str, created_path: Path) -> str` — new
  pure formatter. Returns a multi-line block: header line, then 2-space-indented
  fields for the package/distribution name (`package_name`), the created
  directory path (`str(created_path)`), and the reset version
  (`_RESET_VERSION`). Indentation mirrors the dry-run plan body
  (`main.py:544-555`). Do NOT copy the stale `main.py:592` citation into the
  docstring (design "Do NOT follow").
- `_print_init_summary(package_name: str, created_path: Path) -> None` — thin
  wrapper that `print(...)`s the formatted block to stdout with `# noqa: T201`,
  mirroring `_print_dry_run_plan` (`main.py:559-580`).
- `init_new_package` success branch (`main.py:754-756`) — after the existing
  `print(f'just check passed — {module_name} scaffold is valid.')`, add
  `_print_init_summary(package_name, new_package_path)`, then `return 0`.
  Failure branch (`main.py:757-762`) and all return codes untouched.

**Verify**: `just check` passes. `just test` passes. New unit test on
`_format_init_summary` asserts the returned string contains all three values —
`str(new_package_path)`, `package_name`, and `_RESET_VERSION` (`'0.0.1'`). New
success-path test (using `patch('modernpackage.main.Popen')` /
`modernpackage.main.run` per `research.md` Q5, asserting via `capsys` or
`patch('modernpackage.main.print')`) confirms the created path string and
package name appear in stdout, the existing `'just check passed'` substring is
still present, and `popen_mock.call_count == 3` is unchanged. Manual probe:
from the repo root run
`python -c "from modernpackage.main import _format_init_summary; from pathlib import Path; print(_format_init_summary('demo-pkg', Path('/tmp/demo_pkg')))"`
and confirm stdout contains `demo-pkg`, `/tmp/demo_pkg`, and `0.0.1`.

---

## Testing Checkpoints

- **After Phase 1**: `_RESET_VERSION` is the sole `'0.0.1'` source in
  `main.py`; dry-run plan text is byte-identical to before; `just check` and
  `just test` green. Feature not yet user-visible — this phase is a safe,
  self-contained refactor.
- **After Phase 2**: A successful `init_new_package` run prints the additive
  summary block (created path + package name + reset version) to stdout after
  the preserved `just check passed` line; new unit + success-path tests pass;
  failure branch and return codes (`0` success, `1` failure) unchanged; full
  `just check` (format/lint/typecheck/test) green.

If context resets: Phase 1 is independently valuable (de-duplication) and can
ship alone; Phase 2 depends on `_RESET_VERSION` from Phase 1. Verify state by
grepping `_RESET_VERSION`, `_INIT_SUMMARY_HEADER`, and `_format_init_summary`
in `modernpackage/main.py`.
