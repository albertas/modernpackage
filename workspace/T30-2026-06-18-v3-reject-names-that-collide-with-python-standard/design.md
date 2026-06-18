# Design Discussion

## Current State

The whole CLI lives in one module, `modernpackage/main.py` (178 lines); there is
no separate validation or name module (research.md Q-scope).

- **Validation is composition-only.** A user-supplied `package_name` is validated
  by the argparse `type=` callback `validate_package_name`
  (`modernpackage/main.py:64-69`), which matches a single regex `_PACKAGE_NAME_RE`
  (`modernpackage/main.py:58-61`): PEP 503/508 distribution-name shape
  (alphanumeric ends; `-`, `_`, `.` allowed internally; case-insensitive). On
  failure it raises `ArgumentTypeError('Invalid package name: ...')`; argparse
  then prints usage + error to stderr and exits with **code 2**.
- **No semantic check exists.** There is no check against Python keywords,
  builtins, or standard-library module names. The `normalize_module_name`
  docstring explicitly documents leading-digit (`9lives`) and keyword (`class`)
  names as out of scope (`modernpackage/main.py:76-79`); stdlib collisions are
  absent rather than partially implemented (research.md "Open Areas").
- **Two name forms.** The raw validated `package_name` is transformed to an
  import-safe `module_name` by `normalize_module_name`
  (`modernpackage/main.py:72-80`): `.` and `-` → `_`; `_` preserved; case
  unchanged; runs not collapsed (`a--b` → `a__b`). Normalization happens later, at
  the start of `init_new_package` (`modernpackage/main.py:104`), after `main()`
  decides to scaffold — well after argparse validation.
- **`module_name` is what shadows stdlib.** It becomes the clone directory
  (`modernpackage/main.py:105`), the `just init <module_name>` argument
  (`modernpackage/main.py:124`), and ultimately the inner source-package directory
  (`tests/test_e2e.py:72-76`). So an `import <module_name>` in the generated
  project is what would collide with a stdlib module — the normalized form is the
  correct thing to check.
- **Python baseline.** `requires-python = ">= 3.14"` (`pyproject.toml:8`); no
  runtime dependencies (`pyproject.toml:18`). `sys.stdlib_module_names` (a
  `frozenset`, available since 3.10) enumerates all stdlib top-level module names
  (research.md Q6). `main.py` already imports `sys` (research.md Q6).

## Desired End State

Running the scaffolder with a name whose normalized module name equals a Python
stdlib top-level module is rejected **before any scaffolding begins**, with a
clear message naming the collision, and exits with the existing input-error
code 2. Examples: `modernpackage json`, `modernpackage os`, `modernpackage email`
all fail at parse time; no `git clone` is attempted.

Verify by:
1. `validate_package_name('json')` / `'os'` / `'email'` raise `ArgumentTypeError`
   with a collision message (new unit tests).
2. Near-miss names still pass: `my-json` → `my_json`, `jsonschema`, `email_utils`
   are accepted unchanged (regression assertions).
3. Existing tests (`test_validate_package_name_valid/invalid`,
   `test_normalize_module_name`) remain green.
4. `just check` passes, including `--cov-fail-under=95.0` (`pyproject.toml:40`).

## Patterns to Follow

- **Reject input in the argparse `type=` callback.** Add the collision check
  inside `validate_package_name`, raising `ArgumentTypeError`, mirroring the
  existing regex rejection (`modernpackage/main.py:64-69`). This keeps the
  input-error → exit-code-2 tier intact (research.md Q4) and satisfies "fail
  before any scaffolding."  Do NOT push this into `init_new_package` (that tier is
  for subprocess/runtime errors → `RuntimeError` → exit 1, `main.py:116-141`), and
  do NOT add a separate validation pass in `main()`.
- **Reuse `normalize_module_name`.** Inside `validate_package_name`, compute the
  module name with the existing `normalize_module_name(value)`
  (`modernpackage/main.py:72-80`) and test membership — do not re-implement
  separator substitution. This is the only safe way to know what will actually be
  imported.
- **Module-level constant, annotated.** Define the reserved set as an annotated
  module-level constant next to `_PACKAGE_NAME_RE`, following the leading-`_`
  module-private convention and the "annotate module-level constants" rule
  (Code Best Practices; `modernpackage/main.py:58`).
- **Table-driven tests.** Add cases following the existing dict/tuple style
  (`tests/test_main.py:29-38`, `49-52`), importing symbols directly from
  `modernpackage.main`.

## Design Decisions

1. **Check location: `validate_package_name`** — The task requires failing
   "clearly before any scaffolding work begins." The argparse callback is the
   earliest point and already the home of input rejection. Assumption: exit code 2
   (argparse) is the correct surface for this, consistent with the existing
   invalid-name path; no new exit code is introduced.
2. **Check the normalized form, not the raw name** — Collisions arise from the
   `module_name` that gets imported, so we normalize first then compare. `e-mail`
   → `e_mail` is correctly allowed; `email` → `email` is correctly rejected. This
   requires `validate_package_name` to depend on `normalize_module_name` (a pure
   function), which is acceptable.
3. **Reserved set = `sys.stdlib_module_names`** — A `frozenset` covering all
   stdlib top-level names (and builtins, which it subsumes). Stored as an
   annotated constant `_STDLIB_MODULE_NAMES: frozenset[str] =
   sys.stdlib_module_names`. No new import (sys already present). Decision: do NOT
   also reject `keyword.kwlist` or leading-digit names — the task scope is stdlib
   collisions only, and those are documented out of scope
   (`modernpackage/main.py:76-79`).
4. **Case-sensitive comparison** — stdlib names are all lowercase and the
   codebase intentionally preserves case in normalization (research.md Q3). We
   compare `module_name in _STDLIB_MODULE_NAMES` directly. `JSON` → `JSON` does not
   match `json`; on case-sensitive filesystems it genuinely does not shadow. The
   case-insensitive-filesystem edge is recorded under Open Risks rather than
   handled, to stay surgical and match the given lowercase examples.
5. **Distinct, specific error message** — Raise
   `ArgumentTypeError(f'Package name {value!r} collides with the Python '
   f'standard-library module {module_name!r}')`. A separate message (not
   "Invalid package name") lets tests match it precisely and tells the user
   exactly which module is shadowed.
6. **Order: regex first, collision second** — Run the existing composition check
   before the collision check so malformed input still reports "Invalid package
   name" and only well-formed-but-colliding input reports the collision.

## What We're NOT Doing

- Not rejecting Python keywords, soft keywords, or leading-digit names (out of
  scope per `modernpackage/main.py:76-79`).
- Not doing case-insensitive or per-segment (`json.tools`) collision matching.
- Not checking against third-party/installed package names — stdlib only.
- Not changing `normalize_module_name`, the regex, exit codes, or the
  raw-vs-normalized two-form discipline.
- Not splitting `main.py` into separate modules; the change is a few lines plus a
  constant in the existing file.
- Not adding the argparse exit-code-2 integration test that the suite currently
  lacks (research.md "Open Areas") beyond what is needed to cover the new branch.

## Open Risks

- **Case-insensitive filesystems (macOS/Windows).** `Json`/`OS` normalize with
  case preserved and would pass our case-sensitive check yet could still shadow on
  such filesystems. Flagged, not handled; revisit if it bites.
- **Stdlib set is interpreter-bound.** `sys.stdlib_module_names` reflects the
  *running* interpreter, not necessarily the target 3.14. Since the project pins
  `>= 3.14` (`pyproject.toml:8`) and dev runs on 3.14.3, this is low risk, but the
  rejected set can drift across Python versions.
- **Coverage gate.** The new branch must be exercised by tests to keep coverage
  ≥ 95% (`pyproject.toml:40`); trivial to satisfy but easy to forget.
