# Implementation Plan

## Overview

When `validate_package_name` refuses a name, the `ArgumentTypeError` message must
state the *specific* reason (empty, disallowed character, or leading/trailing
separator) instead of the current generic `Invalid package name: {value!r}`. The
regex `_PACKAGE_NAME_RE` stays the sole accept/reject gate; a new module-private
helper `_explain_invalid_package_name` only *explains* a rejection after the
regex has already said no.

## Conventions to honor (from `Code Best Practices` / `CLAUDE.md`)

- Module-private symbols are `_`-prefixed; compiled regex constants are suffixed
  `_RE`.
- Validation messages stay capitalized and embed the value via `{value!r}` (NOT
  lowercased like the git-clone strings).
- Tests: top-level `def test_*`, `pytest.raises(..., match=...)` substring
  assertions; no test classes; helper imported directly from the module.
- Surgical changes only — do not touch `normalize_module_name`, `parse_args`,
  the stdlib-collision branch, or any adjacent code.
- Reason precedence is **first-match-wins, most-specific-first**:
  empty → disallowed character → leading/trailing separator.

## Verification commands (from `Justfile`)

- Full gate: `just check` (= check-format, check-lint, check-complexity,
  check-typecheck, test, audit).
- Targeted tests: `just test tests/test_main.py`.
- The manual `python -c ...` probes below run the helper through the public
  `validate_package_name`. Because `ArgumentTypeError` is raised (not caught) the
  process exits non-zero and prints a traceback to stderr containing the message;
  `2>&1 | grep -q '...'` confirms the phrase.

---

## Phase 1: Helper scaffold + empty-value reason

Establishes the explain-after-reject seam: the helper exists, is wired into
`validate_package_name`, and handles the most distinct case (empty string). The
final fallback returns the separator phrase so the helper is *total* even before
Phases 2-3 fill the middle branches.

### Changes

#### 1. New helper `_explain_invalid_package_name`
**File**: `modernpackage/main.py`
**Action**: modify (add helper directly above `validate_package_name`, after the
`_STDLIB_MODULE_NAMES` block at line 66)

```python
def _explain_invalid_package_name(value: str) -> str:
    """Return a precise reason a name failed `_PACKAGE_NAME_RE`.

    Caller guarantees `_PACKAGE_NAME_RE.match(value)` is falsy. Reasons are
    checked most-specific-first (empty → disallowed char → separator); the
    first match wins. The function is total: the final branch is the residual
    leading/trailing-separator case.
    """
    if value == '':
        return 'name must not be empty'
    # Residual case (filled out in later phases): regex failed, non-empty.
    return 'name must start and end with a letter or digit'
```

#### 2. Wire helper into `validate_package_name`
**File**: `modernpackage/main.py`
**Action**: modify the regex-failure branch (currently lines 71-73)

```python
    if not _PACKAGE_NAME_RE.match(value):
        reason = _explain_invalid_package_name(value)
        message = f'Invalid package name: {value!r} — {reason}'
        raise ArgumentTypeError(message)
```

Leave the stdlib-collision branch (lines 74-80) and `return value` untouched.

#### 3. New test for the empty case
**File**: `tests/test_main.py`
**Action**: modify (add new test after `test_validate_package_name_invalid`,
line 57; import the helper in the existing `from modernpackage.main import (...)`
block)

Add `_explain_invalid_package_name` to the import block, then:

```python
def test_explain_invalid_package_name_empty() -> None:
    with pytest.raises(ArgumentTypeError, match='name must not be empty'):
        validate_package_name('')
```

### Verification
#### Automated
- [x] `just test tests/test_main.py` passes (new test + all pre-existing).
- [x] `test_validate_package_name_invalid` (substring `Invalid package name`)
      still passes unchanged.
- [x] `test_validate_package_name_rejects_stdlib_collision` still passes.
- [x] `test_validate_package_name_valid` still passes (valid names returned
      unchanged).
- [x] `just check` passes (format, lint, complexity, typecheck, test, audit).

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import validate_package_name as v; v('')" 2>&1 | grep -q 'name must not be empty'` → exit 0 (phrase present).
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import _explain_invalid_package_name as e; print(e(''))"` → prints `name must not be empty`.

---

## Phase 2: Disallowed-character reason

Adds the second precedence branch: the first character outside `[a-z0-9._-]`
(case-insensitive — `A-Z` treated as allowed to match `re.IGNORECASE`) is named
via `!r` alongside the allowed-set hint.

### Changes

#### 1. Allowed-set regex constant
**File**: `modernpackage/main.py`
**Action**: modify (add a compiled constant near `_PACKAGE_NAME_RE`, after line
61, per the `_RE` naming convention)

```python
# Matches the first character that is NOT a permitted package-name character.
# Permits A-Z via re.IGNORECASE to stay consistent with _PACKAGE_NAME_RE.
_DISALLOWED_CHAR_RE: re.Pattern[str] = re.compile(r'[^a-z0-9._-]', re.IGNORECASE)
```

#### 2. Disallowed-character branch in the helper
**File**: `modernpackage/main.py`
**Action**: modify `_explain_invalid_package_name` — insert **after** the empty
check, **before** the separator fallback

```python
    match = _DISALLOWED_CHAR_RE.search(value)
    if match:
        bad_char = match.group()
        return (
            f'name contains a disallowed character: {bad_char!r} '
            f"(only letters, digits, '.', '_', '-' are allowed)"
        )
```

#### 3. New test for disallowed char + uppercase regression guard
**File**: `tests/test_main.py`
**Action**: modify (add test after `test_explain_invalid_package_name_empty`)

```python
def test_explain_invalid_package_name_disallowed_char() -> None:
    with pytest.raises(ArgumentTypeError, match="disallowed character: ' '"):
        validate_package_name('has space')
    # uppercase stays valid (re.IGNORECASE; A-Z must not be flagged)
    assert validate_package_name('MyPackage') == 'MyPackage'
```

### Verification
#### Automated
- [x] `just test tests/test_main.py` passes (new test + all prior).
- [x] All Phase 1 tests still pass.
- [x] `just check` passes.

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import validate_package_name as v; v('has space')" 2>&1 | grep -q "disallowed character: ' '"` → exit 0.
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import validate_package_name as v; print(v('MyPackage'))"` → prints `MyPackage`, exit 0.

---

## Phase 3: Leading/trailing separator reason

Promotes the Phase 1 fallback into the explicit, documented final branch. A name
that is non-empty and contains only allowed characters but still failed the regex
must have a misplaced leading/trailing `.`, `_`, or `-`. (The phrase is already
in place from Phase 1; this phase confirms/documents it as the residual branch
and adds the dedicated tests + precedence guard.)

### Changes

#### 1. Confirm/document the residual branch
**File**: `modernpackage/main.py`
**Action**: modify — the final `return` of `_explain_invalid_package_name` keeps
the phrase and gains a clarifying comment

```python
    # Residual case: regex failed, value is non-empty and contains only
    # allowed characters, so a leading/trailing '.', '_', or '-' is to blame.
    return 'name must start and end with a letter or digit'
```

No new branch is added — Phases 1 and 2 already left this as the fallback.

#### 2. New test for separators + precedence guard
**File**: `tests/test_main.py`
**Action**: modify (add test after
`test_explain_invalid_package_name_disallowed_char`)

```python
def test_explain_invalid_package_name_separator() -> None:
    for bad_name in ('-bad', 'bad-', '.bad', '_bad'):
        with pytest.raises(
            ArgumentTypeError, match='name must start and end with a letter or digit'
        ):
            validate_package_name(bad_name)
    # precedence: disallowed char wins over separator (design decision 3)
    with pytest.raises(ArgumentTypeError, match='disallowed character'):
        validate_package_name('-has space')
```

### Verification
#### Automated
- [x] `just test tests/test_main.py` passes (new test + all prior).
- [x] `just check` passes.

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import validate_package_name as v; v('-bad')" 2>&1 | grep -q 'name must start and end with a letter or digit'` → exit 0.
- [x] `cd /home/niekas/tools/modernpackage && python -c "from modernpackage.main import validate_package_name as v; v('-has space')" 2>&1 | grep -q 'disallowed character'` → exit 0 (precedence: char beats separator).

---

## Final acceptance (matches design "Desired End State")

- [x] Each of the four categories yields a distinct message:
  - `''` → `name must not be empty`
  - `'has space'` → `disallowed character: ' '`
  - `'-bad'` → `name must start and end with a letter or digit`
  - `'json'` → `collides with the Python standard-library module` (unchanged)
- [x] Acceptance set unchanged: `mypackage`, `my-package`, `my_package`,
      `my.package`, `a`, `my-json`, `jsonschema`, `email_utils`, `MyPackage`,
      `a--b`, `a..b` all still pass (`a--b`/`a..b` via `validate_package_name`).
- [x] Precedence empty → disallowed-char → separator verified by `'-has space'`.
- [x] `just check` and `just test` are green.

## Assumptions / resolved decisions

- **No new behavior beyond messaging**: out-of-scope cases (`9lives`, `class`)
  remain accepted; no new rejection categories added (design Decision 6 / "What
  We're NOT Doing").
- **No argparse exit-code test added** — pre-existing gap, not in scope
  (`research.md:193-198`); manual probes above suffice to confirm the message
  reaches stderr.
- **Helper imported directly** from `modernpackage.main` in tests, per the
  private-API testing convention.
- **`bad_char!r` for whitespace** renders readably (`' '`, `'\t'`, `'\n'`) —
  accepted per design Open Risks.
```