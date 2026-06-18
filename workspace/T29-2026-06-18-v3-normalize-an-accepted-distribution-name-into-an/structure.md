# Structure Outline

## Approach
Add one pure helper, `normalize_module_name(value: str) -> str`, that replaces
`.` and `-` with `_` (keeping `_`, no lowercasing), then derive
`module_name = normalize_module_name(package_name)` once at the top of
`init_new_package` and use it for the clone directory, the `just init` argument,
and the print messages. Validation (`validate_package_name`) and the `Justfile`
are left unchanged (per design Decisions 2 & 3).

This is genuinely small (single-module change in `modernpackage/main.py` plus
tests). It still slices into two vertical phases: the helper is independently
shippable and testable, and the wiring builds on it. Phase 1 is valuable on its
own (a tested, correct conversion function) even if Phase 2 is deferred.

---

## Phase 1: `normalize_module_name` helper + unit tests
Adds the pure transform that converts a validated distribution name into an
import-safe Python module identifier. No call sites yet; fully unit-testable in
isolation.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `normalize_module_name(value: str) -> str` — new. Returns `value` with every
  `.` and `-` replaced by `_`; existing `_` preserved; no case change. Never
  returns `None` (input is pre-validated). One-line docstring stating the return
  contract, mirroring `humanize_git_clone_error` shape (`main.py:47-53`).
  Implementation = chained `str.replace()` or `str.translate` (Decision 4); a
  regex constant is optional and, if used, must be named `_MODULE_NAME_*_RE` and
  annotated `re.Pattern[str]` (`main.py:58` convention).
- `test_normalize_module_name` — new. Input/expected loop (style of
  `test_validate_package_name_valid`, `test_main.py:28-33`) asserting:
  `my-cool.package → my_cool_package`, `my_package → my_package`, `a → a`,
  `my-cool_pkg.v2 → my_cool_pkg_v2`, and run case `a--b → a__b`
  (design "What We're NOT Doing").
- Note as a code comment near the helper: leading-digit names (`9lives`) and
  Python keywords remain invalid module names — out of scope (Open Risks).

**Verify**: `just test tests/test_main.py::test_normalize_module_name` passes.
Also confirm the helper is import-clean:
`uv run python -c "from modernpackage.main import normalize_module_name as n; assert n('my-cool.package')=='my_cool_package'; assert n('my_package')=='my_package'; print('ok')"`
prints `ok`.

---

## Phase 2: Wire the module name into `init_new_package` (+ tests)
Derives the normalized name once inside `init_new_package` and uses it for the
clone destination directory, the `just init` argument, and both print messages,
so the scaffolded source directory and all generated `import` paths are valid
Python. Validator and Justfile untouched.

**Files**: `modernpackage/main.py`, `tests/test_main.py`, `tests/test_e2e.py`

**Key changes**:
- `init_new_package(package_name: str) -> int` — modified. Add first line
  `module_name = normalize_module_name(package_name)` (`main.py:91-93`). Replace
  downstream uses:
  - `new_package_path = Path.cwd() / module_name` (was `package_name`, `:93`)
  - `['just', 'init', module_name]` (was `package_name`, `:112`)
  - both `print(...)` messages reference `module_name` (`:141`, `:145`)
    (Decision 6). Signature unchanged.
- `test_init_new_package_normalizes_name` (or extend existing init tests) — new.
  Patch `Popen` on the module object (`patch('modernpackage.main.Popen')`) with a
  `side_effect` sequence for clone/init/check (`test_main.py:84-85`). Call with a
  `-`/`.` input (e.g. `my-cool.package`) and assert the `git clone` target path
  ends with `my_cool_package` and the `just init` arg list is
  `['just', 'init', 'my_cool_package']`.
- `tests/test_e2e.py` — extend (or add) one assertion proving a `-`/`.` input
  yields an underscore source directory: scaffold with a name containing `-`/`.`
  and assert the created package directory name contains `_` and no `-`/`.`
  (regression guard for design "e2e coverage gap").

**Verify**: `just test` passes (includes new init + existing
`test_validate_package_name_valid` identity assertions, which must stay green).
Then `just check` passes end-to-end (format, lint, complexity ≤10, typecheck,
tests, audit). For the e2e path specifically:
`just test-e2e` passes and the scaffolded directory name matches `^[a-z0-9_]+$`.

---

## Testing Checkpoints
- **After Phase 1**: `normalize_module_name` exists and is correct in isolation;
  the four design-specified mappings plus the `a--b → a__b` run case pass. No
  call sites changed yet — `init_new_package` still uses the raw name, so the
  rest of the suite is unaffected. Independently valuable.
- **After Phase 2**: `init_new_package` uses the normalized name for the clone
  dir, `just init` arg, and messages. Mocked-`Popen` unit test confirms a
  `-`/`.` input produces an underscore directory and `just init` arg; e2e
  confirms the same end-to-end. `validate_package_name` identity-return tests
  (`test_main.py:28-33`) remain green (validator untouched). `just check` green.
- **Out of scope (flagged, not fixed)**: leading-digit names (`9lives`) and
  Python-keyword names (`class`) still yield invalid module names; the Justfile
  and `_PACKAGE_NAME_RE` are unchanged.
