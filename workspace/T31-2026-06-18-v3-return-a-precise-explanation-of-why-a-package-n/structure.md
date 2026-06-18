# Structure Outline

## Approach

Keep `_PACKAGE_NAME_RE` (`modernpackage/main.py:58-61`) as the sole accept/reject
gate. Add a module-private helper `_explain_invalid_package_name(value) -> str`
that runs **only** after the regex has already rejected a name, returning a
precise reason phrase. `validate_package_name` appends ` — <reason>` to the
existing `Invalid package name: {value!r}` prefix, so old substring assertions
keep passing. Reason detection is an ordered, first-match-wins sequence
(empty → disallowed character → leading/trailing separator), mirroring the
most-specific-first precedence of `_GIT_CLONE_ERROR_MESSAGES` (`main.py:11`).

The work is genuinely small (one helper + one call-site edit + tests). Each
phase below adds **one reason branch** end-to-end: helper branch → integration
in `validate_package_name` → a dedicated test asserting the distinct phrase. The
helper's contract is defined in Phase 1 and only extended (never reshaped) by
later phases, so each phase is independently valuable and independently testable.

---

## Phase 1: Helper scaffold + empty-value reason

Establishes the explain-after-reject seam: the helper exists, is wired into
`validate_package_name`, and handles the most distinct case (empty string). After
this phase the message machinery is proven end-to-end with one reason.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_explain_invalid_package_name(value: str) -> str` — new module-private helper.
  Contract: caller guarantees `_PACKAGE_NAME_RE.match(value)` is falsy. Returns a
  short reason phrase (no prefix, no em-dash). First branch: `if value == ''`
  → `'name must not be empty'`. Final fallback returns the separator phrase (so
  the function is total even before Phases 2-3 fill the middle branches).
- `validate_package_name` (`main.py:69-81`) — modified regex-failure branch:
  ```python
  if not _PACKAGE_NAME_RE.match(value):
      reason = _explain_invalid_package_name(value)
      message = f'Invalid package name: {value!r} — {reason}'
      raise ArgumentTypeError(message)
  ```
- `test_explain_invalid_package_name_empty` — new: asserts
  `validate_package_name('')` raises `ArgumentTypeError` matching
  `'name must not be empty'`.

**Verify**: `just test` and `just check` pass. The existing
`test_validate_package_name_invalid` (substring `Invalid package name`) and
`test_validate_package_name_rejects_stdlib_collision` still pass unchanged.
Manual: `python -c "from modernpackage.main import validate_package_name as v; v('')"`
exits non-zero and stderr contains `name must not be empty`.

---

## Phase 2: Disallowed-character reason

Adds the second precedence branch: the first character outside `[a-z0-9._-]`
(case-insensitive) is named via `!r` alongside the allowed-set hint.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_explain_invalid_package_name` — insert branch **after** the empty check,
  **before** the separator fallback: scan `value` for the first character not in
  the allowed set (treat `A-Z` as allowed to match `re.IGNORECASE`); if found,
  return
  `f"name contains a disallowed character: {bad_char!r} (only letters, digits, '.', '_', '-' are allowed)"`.
  Detection may reuse a small allowed-set check (e.g. a compiled
  `[^a-z0-9._-]` pattern with `re.IGNORECASE`, suffixed `_RE` per conventions).
- `test_explain_invalid_package_name_disallowed_char` — new: `'has space'` →
  match `"disallowed character: ' '"`; add an uppercase-stays-valid guard, e.g.
  `validate_package_name('MyPackage') == 'MyPackage'` (regression for the
  `A-Z`-in-allowed-set risk, design Open Risks).

**Verify**: `just test` and `just check` pass. Manual:
`python -c "from modernpackage.main import validate_package_name as v; v('has space')"`
stderr contains `disallowed character: ' '`;
`python -c "from modernpackage.main import validate_package_name as v; print(v('MyPackage'))"`
prints `MyPackage` (exit 0).

---

## Phase 3: Leading/trailing separator reason

Promotes the Phase 1 fallback into the explicit, documented final branch: a name
that is non-empty and contains only allowed characters but still failed the regex
must have a misplaced leading/trailing `.`, `_`, or `-`.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_explain_invalid_package_name` — the final branch returns
  `'name must start and end with a letter or digit'` (one phrase covering
  leading/trailing `.`/`_`/`-`). Add a brief comment documenting that this is the
  residual case (regex failed, non-empty, all chars allowed).
- `test_explain_invalid_package_name_separator` — new: iterate `'-bad'`, `'bad-'`,
  `'.bad'`, `'_bad'` asserting match `'name must start and end with a letter or digit'`.
- Optional precedence guard: `'-has space'` reports the space (disallowed-char
  wins over separator), pinning Design Decision 3.

**Verify**: `just test` and `just check` pass. Manual:
`python -c "from modernpackage.main import validate_package_name as v; v('-bad')"`
stderr contains `name must start and end with a letter or digit`;
`python -c "from modernpackage.main import validate_package_name as v; v('-has space')"`
stderr contains `disallowed character`.

---

## Testing Checkpoints

- **After Phase 1**: helper exists and is wired in; empty name produces a
  distinct reason; all pre-existing tests (invalid-name substring, stdlib
  collision, valid names returning input unchanged) still green. The
  explain-after-reject seam is proven.
- **After Phase 2**: disallowed characters are named exactly with the allowed-set
  hint; uppercase names still accepted (no false rejection from the allowed-set
  check).
- **After Phase 3**: leading/trailing separators get their positive-rule phrase;
  precedence empty → disallowed-char → separator is verified by `-has space`.
- **End state matches design "Desired End State"**: each of the four categories
  (empty, separator, disallowed char, stdlib collision) yields a distinct
  message; acceptance set is unchanged (valid names, near-miss names, uppercase,
  `a--b`/`a..b` all still pass); `just check` and `just test` are green.

**Note on slicing**: this feature does not span DB/API/UI layers — it is a single
CLI validation function. "Vertical" here means each phase carries one reason
fully from helper logic → `validate_package_name` integration → a passing test,
rather than splitting into "all logic" then "all tests". No part of the design
resists this slicing.
