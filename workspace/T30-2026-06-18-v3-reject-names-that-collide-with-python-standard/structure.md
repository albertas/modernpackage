# Structure Outline

## Approach

Reject names whose normalized module name equals a Python stdlib top-level
module **inside the argparse `type=` callback** `validate_package_name`, so the
failure happens before any scaffolding and uses the existing input-error exit
code 2. The check normalizes the raw name with the existing
`normalize_module_name`, then tests membership in an annotated module-level
`frozenset` constant (`sys.stdlib_module_names`). Regex composition check runs
first; collision check second, with a distinct error message.

> **Single-layer note.** This feature has no DB/service/API/UI stack — the only
> layer is the CLI input-validation path in `modernpackage/main.py`. "Vertical
> slices" below therefore means independently-testable increments of that path
> (constant + check + tests), each green on its own, not layer-crossing slices.
> The whole change is a constant plus a few lines, as `design.md` states.

---

## Phase 1: Reject stdlib-colliding names in the validation callback

Add the reserved-name constant and the collision check to
`validate_package_name`, then prove rejection with unit tests. This is the
complete functional deliverable: a colliding name fails at parse time with a
specific message and exit code 2.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_STDLIB_MODULE_NAMES: frozenset[str] = sys.stdlib_module_names` — new
  annotated module-level constant, placed next to `_PACKAGE_NAME_RE`
  (`main.py:58`). No new import (`sys` already imported).
- `validate_package_name(value: str) -> str` — modified. After the existing
  regex check, compute `module_name = normalize_module_name(value)` and, if
  `module_name in _STDLIB_MODULE_NAMES`, raise
  `ArgumentTypeError(f'Package name {value!r} collides with the Python '
  f'standard-library module {module_name!r}')`. Regex check stays first.
- New unit test(s) asserting `validate_package_name('json')`, `'os'`, `'email'`
  raise `ArgumentTypeError` matching the collision message (table-driven, dict/
  tuple style per `tests/test_main.py:29-38`).

**Verify**:
- `just test` passes (or scoped: `.venv/bin/python -m pytest tests/test_main.py -q`).
- Behavior probe (must fail before any clone):
  `.venv/bin/python -m modernpackage json; echo "exit=$?"` →
  exit code is `2` and stderr contains `collides with the Python standard-library module`.
  Repeat for `os` and `email`.
- Negative-control that no scaffolding ran: after the above, `test ! -e ./json`
  (no clone directory was created in cwd).

---

## Phase 2: Lock in near-miss acceptance and the coverage gate

Add regression assertions that near-miss names still pass through unchanged, and
confirm the new branch keeps total coverage ≥ 95%. Guards against the check being
too broad and against the coverage gate regressing.

**Files**: `tests/test_main.py`

**Key changes**:
- Extend the accept-cases test (alongside `test_validate_package_name_valid`,
  `tests/test_main.py:41-46`) to assert these return identical strings:
  `my-json`, `jsonschema`, `email_utils` (and confirm
  `normalize_module_name('my-json') == 'my_json'`, which is not in the reserved
  set).
- Confirm existing tests stay green: `test_validate_package_name_valid/invalid`,
  `test_normalize_module_name`, `test_init_new_package_normalizes_name`.

**Verify**:
- `just check` passes, including `--cov-fail-under=95.0` (`pyproject.toml:40`).
- Probe near-misses are accepted (exit 0):
  `.venv/bin/python -c "from modernpackage.main import validate_package_name as v; \
  print(v('my-json'), v('jsonschema'), v('email_utils'))"` prints
  `my-json jsonschema email_utils` and exits `0`.
- `just test` (default `-m 'not e2e'`) reports no failures and coverage line
  shows ≥ 95%.

---

## Testing Checkpoints

After **Phase 1**: a normalized name matching `sys.stdlib_module_names` is
rejected by `validate_package_name` with the distinct collision message and exit
code 2; no `git clone` occurs for `json`/`os`/`email`. The earlier
"Invalid package name" path is unchanged for malformed input (regex runs first).

After **Phase 2**: near-miss names (`my-json`, `jsonschema`, `email_utils`) are
still accepted unchanged; all pre-existing tests remain green; `just check`
passes with coverage ≥ 95%. If context resets, re-run `just check` — green means
both phases are complete and verified.
