# Implementation Plan

## Overview

Reject any package name whose normalized module name equals a Python stdlib
top-level module **inside the argparse `type=` callback** `validate_package_name`,
so the failure happens before any scaffolding (no `git clone`) and uses the
existing argparse input-error exit code 2, with a distinct collision message.

> **Single-layer note (from structure.md).** This feature has no DB/service/API/UI
> stack — the only layer is the CLI input-validation path in
> `modernpackage/main.py`. The two phases below are independently-testable
> increments of that one path (constant + check + tests; then regression +
> coverage lock-in), not layer-crossing slices. The whole change is one
> module-level constant plus a few lines in `validate_package_name`.

> **Verification command note.** The Justfile drives everything through `uv run`
> (`Justfile:13-14`, `52`). Use `just test` / `just check` as the canonical
> commands. The scoped/probe commands below use `uv run python ...` so they share
> the same interpreter/venv as the suite. (structure.md wrote `.venv/bin/python`;
> `uv run python` is the project-consistent equivalent — substitute freely if a
> `.venv` is present.)

---

## Phase 1: Reject stdlib-colliding names in the validation callback

Add the reserved-name constant and the collision check to `validate_package_name`,
then prove rejection with unit tests. This is the complete functional deliverable:
a colliding name fails at parse time with a specific message and exit code 2.

### Changes

#### 1. Reserved-name constant
**File**: `modernpackage/main.py`
**Action**: modify (add module-level constant next to `_PACKAGE_NAME_RE`, after
line 61, before `validate_package_name` at line 64)

No new import is required — `sys` is already imported (`main.py:4`).

```python
# All Python standard-library top-level module names for the running
# interpreter (a frozenset; available since 3.10). A normalized module name
# equal to any of these would shadow a stdlib module on import, so reject it.
_STDLIB_MODULE_NAMES: frozenset[str] = sys.stdlib_module_names
```

#### 2. Collision check in `validate_package_name`
**File**: `modernpackage/main.py`
**Action**: modify (`validate_package_name`, lines 64-69)

Keep the regex (composition) check first; add the collision check second so
malformed input still reports "Invalid package name" and only well-formed names
reach the collision branch. Reuse `normalize_module_name` (do not re-implement
separator substitution) — it is the form that actually gets imported.

```python
def validate_package_name(value: str) -> str:
    """Validate value is a PEP 508 / PyPI distribution name not shadowing stdlib."""
    if not _PACKAGE_NAME_RE.match(value):
        message = f'Invalid package name: {value!r}'
        raise ArgumentTypeError(message)
    module_name = normalize_module_name(value)
    if module_name in _STDLIB_MODULE_NAMES:
        message = (
            f'Package name {value!r} collides with the Python '
            f'standard-library module {module_name!r}'
        )
        raise ArgumentTypeError(message)
    return value
```

> **Forward-reference note.** `validate_package_name` (line 64) now calls
> `normalize_module_name`, which is defined later (line 72). This is safe: the
> call happens at runtime, not import time, so definition order does not matter.
> Do not reorder the two functions (surgical-change rule).

#### 3. Rejection unit test
**File**: `tests/test_main.py`
**Action**: modify (add a new table-driven test after
`test_validate_package_name_invalid`, lines 49-52). `ArgumentTypeError` is
already imported (`test_main.py:1`); `validate_package_name` already imported
(line 14).

```python
def test_validate_package_name_rejects_stdlib_collision() -> None:
    for colliding_name in ('json', 'os', 'email'):
        with pytest.raises(
            ArgumentTypeError, match='collides with the Python standard-library module'
        ):
            validate_package_name(colliding_name)
```

### Verification
#### Automated
- [x] `just test` passes (runs `uv run pytest -n ... -m 'not e2e'`, `Justfile:13-14`).
- [x] Scoped: `uv run pytest tests/test_main.py -q` passes, including the new
      `test_validate_package_name_rejects_stdlib_collision`.

#### Manual
- [x] Colliding name fails at parse time with exit code 2 and the collision
      message (repeat for `os`, `email`):
      `uv run modernpackage json 2> /tmp/mp_err.txt; echo "exit=$?"`
      → prints `exit=2`, and
      `grep -q 'collides with the Python standard-library module' /tmp/mp_err.txt`
      succeeds (exit 0).
- [x] Negative control — no scaffolding ran (no clone dir created in cwd):
      after the above, `test ! -e ./json` succeeds (exit 0). Repeat:
      `test ! -e ./os && test ! -e ./email`.
- [x] Malformed input still reports the original message (regex runs first):
      `uv run modernpackage 'has space' 2>&1 | grep -q 'Invalid package name'`
      succeeds.

---

## Phase 2: Lock in near-miss acceptance and the coverage gate

Add regression assertions that near-miss names still pass through unchanged, and
confirm the new branch keeps total coverage ≥ 95%. Guards against the check being
too broad and against the coverage gate regressing.

### Changes

#### 1. Near-miss acceptance assertions
**File**: `tests/test_main.py`
**Action**: modify (extend `test_validate_package_name_valid`, lines 41-46).
`normalize_module_name` is already imported (line 12).

Add assertions that names *containing* a stdlib name but not equal to it after
normalization are accepted unchanged, plus the normalization sanity check that
`my-json` normalizes to `my_json` (not in the reserved set):

```python
def test_validate_package_name_valid() -> None:
    assert validate_package_name('mypackage') == 'mypackage'
    assert validate_package_name('my-package') == 'my-package'
    assert validate_package_name('my_package') == 'my_package'
    assert validate_package_name('my.package') == 'my.package'
    assert validate_package_name('a') == 'a'
    # near-misses: contain a stdlib name but do not normalize to one
    assert validate_package_name('my-json') == 'my-json'
    assert validate_package_name('jsonschema') == 'jsonschema'
    assert validate_package_name('email_utils') == 'email_utils'
    assert normalize_module_name('my-json') == 'my_json'
```

### Verification
#### Automated
- [x] `just check` passes — includes format, lint, complexity (≤10), typecheck,
      `test` with `--cov-fail-under=95.0` (`pyproject.toml:40`), and audit
      (`Justfile:52`).
- [x] `just test` reports no failures and the coverage line shows ≥ 95%
      (default run excludes e2e via `-m 'not e2e'`, `pyproject.toml:40`).

#### Manual
- [x] Near-misses are accepted and returned unchanged (exit 0):
      `uv run python -c "from modernpackage.main import validate_package_name as v; print(v('my-json'), v('jsonschema'), v('email_utils'))"`
      prints `my-json jsonschema email_utils` and exits 0
      (append `; echo exit=$?` to confirm).
- [x] Pre-existing tests stay green — confirm the named tests run and pass:
      `uv run pytest tests/test_main.py -q -k 'validate_package_name or normalize_module_name or init_new_package_normalizes_name'`
      succeeds with no failures. (Coverage gate fails in the scoped run because
      only 5 of 26 tests run — expected; `just check` with the full suite hits
      100%.)

---

## Testing Checkpoints (from structure.md)

After **Phase 1**: a normalized name matching `sys.stdlib_module_names` is
rejected by `validate_package_name` with the distinct collision message and exit
code 2; no `git clone` occurs for `json`/`os`/`email`. The "Invalid package name"
path is unchanged for malformed input (regex runs first).

After **Phase 2**: near-miss names (`my-json`, `jsonschema`, `email_utils`) are
still accepted unchanged; all pre-existing tests remain green; `just check`
passes with coverage ≥ 95%. If context resets, re-run `just check` — green means
both phases are complete and verified.

## Resolved Assumptions

- **Verification interpreter.** structure.md used `.venv/bin/python`; this plan
  uses `uv run python`/`just` to match how the Justfile invokes the suite
  (`Justfile:13-14`, `52`). Either reaches the same venv; prefer `just`.
- **Case-sensitivity / keywords / leading-digit names.** Out of scope per
  design.md "What We're NOT Doing" and Open Risks. Comparison is
  `module_name in _STDLIB_MODULE_NAMES` (case-sensitive), and no `keyword`/
  builtins check is added. Not handled here.
- **No new argparse exit-code-2 integration test** beyond covering the new
  branch (design.md "What We're NOT Doing"); the manual probe in Phase 1 exercises
  the exit-code-2 path without adding a brittle suite test.
