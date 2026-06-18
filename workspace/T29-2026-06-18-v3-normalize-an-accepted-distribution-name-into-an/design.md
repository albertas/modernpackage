# Design Discussion

## Current State

The CLI accepts a single positional `package_name` argument validated at parse
time by `validate_package_name` via `type=` (`main.py:82-87`). Validation matches
`_PACKAGE_NAME_RE = ^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$` (case-insensitive)
(`main.py:58-61`) and returns the value **unchanged** on success or raises
`ArgumentTypeError` (`main.py:64-69`). The regex permits PEP 508/PyPI characters:
alphanumeric ends with `.`, `_`, `-` allowed internally.

One raw value then serves every role with **no transformation** (research Q4):

- Clone/destination directory: `Path.cwd() / package_name` (`main.py:93`, `:96`).
- Passed verbatim to scaffolding: `['just', 'init', package_name]` (`main.py:112`).
- Inside `just init` it becomes the source package directory via
  `mv modernpackage {{package_name}}` (`Justfile:68`) and is substituted into
  every git-tracked occurrence of the literal token `modernpackage` —
  including `from modernpackage import ...` import lines and `pyproject.toml`'s
  `name` — by `git grep -l 'modernpackage' | xargs sed ...` (`Justfile:61-66`).
- User-facing print messages (`main.py:141`, `:145`).

**The gap:** a valid distribution name like `my-cool.package` becomes a literal
directory name and is injected into Python `import` statements, producing an
invalid module path. No normalization helper exists anywhere (research Q3, Q5,
"Open Areas"). PEP 503/508 are cited in comments only as *validation* intent
(`main.py:56-57`, `:65`); normalization was never implemented.

## Desired End State

A small pure helper converts a validated distribution name into an import-safe
module identifier (`my-cool.package` → `my_cool_package`) by replacing `.` and
`-` with `_`. `init_new_package` derives this module name once and uses it for
the destination directory, the `just init` argument, and its messages, so the
scaffolded package directory and all generated import paths are valid Python.

Verify it is correct:

- New unit tests for the helper assert mappings: `my-cool.package` →
  `my_cool_package`, `my_package` → `my_package`, `a` → `a`, mixed
  `my-cool_pkg.v2` → `my_cool_pkg_v2`.
- Existing `test_validate_package_name_valid` identity-return assertions stay
  green (validation is **not** changed) (`test_main.py:28-33`).
- `init_new_package` unit tests (mocked `Popen`) confirm the normalized name is
  the clone target and the `just init` argument when input contains `-`/`.`.
- The e2e scaffold (`test_e2e.py:50-74`) still passes with `scaffoldcheck`;
  optionally extend it (or add a unit assertion) to prove a `-`/`.` input yields
  an underscore source directory.
- `just check` passes (format, lint, complexity ≤10, typecheck, tests).

## Patterns to Follow

- **Pure string helper shape** — mirror `humanize_git_clone_error`
  (`main.py:47-53`): typed signature, one-line docstring stating the return
  contract, no side effects. The new helper returns `str` (never `None`; input is
  already validated).
- **Module-private naming** — `_`-prefix for internals, `_RE` suffix for compiled
  regex constants (`main.py:58`), explicit type annotations on module constants
  (research Q5, Cross-Cutting). If a regex is used, name it e.g.
  `_MODULE_NAME_SEPARATOR_RE` and annotate it `re.Pattern[str]`.
- **Validation stays validation** — `validate_package_name` returns the value
  unchanged (`main.py:64-69`); do not fold transformation into it (see Decision 3).
- **Test conventions** (`tests/test_main.py`, research Q6): top-level `def test_*`,
  plain `assert`, simple input/expected loops like `test_validate_package_name_valid`
  (`test_main.py:28-33`); patch `Popen` on the module object
  (`patch('modernpackage.main.Popen')`) with `side_effect` sequencing
  (`test_main.py:84-85`).

**Do NOT follow / avoid:** do not extend the blanket `git grep | sed` token
replacement in the Justfile to thread a second name through — it cannot
distinguish import-role from distribution-role occurrences of `modernpackage`
(they are the same literal token), and doing so would be a large, fragile change
(see Decision 2 and "What We're NOT Doing").

## Design Decisions

1. **Normalization mapping = replace `.` and `-` with `_`; keep `_`; no
   lowercasing.** Matches the task example exactly (`my-cool.package` →
   `my_cool_package`). Uppercase is already a *valid* Python identifier, so
   lowercasing is a style preference, not an import-safety requirement; omitting
   it keeps the change minimal and avoids surprising the user. (Assumption: the
   task wants import-*safety*, not full PEP 8 module-style enforcement.)

2. **Single normalized name for all roles (no dist/import split).** Use the
   module name as the clone directory, `just init` arg, source dir, and pyproject
   `name`. Justification: `my-cool.package` and `my_cool_package` PEP 503-normalize
   to the *same* canonical PyPI project name, so installation identity is
   preserved; and this requires **zero Justfile changes** (surgical, per CLAUDE.md
   §3). The alternative — preserving the distribution form in `pyproject.toml`
   while using the module form for imports — needs two args plus split
   substitution logic in the Justfile and is out of scope (Decision rejected).

3. **Normalize inside `init_new_package`, not in `validate_package_name`.** Keeps
   the validator a pure validate-and-passthrough (preserving the identity-return
   contract and `test_main.py:28-33`) and keeps the argparse `type=` value the raw
   user input. Derive `module_name = normalize_module_name(package_name)` at the
   top of `init_new_package` (`main.py:91-93`) and use it thereafter.

4. **Implementation = simple `str`-based transform** (e.g. chained `.replace()` or
   `str.translate`), not a regex, unless a regex reads more clearly. The mapping
   is a fixed two-character substitution; a constant/regex adds ceremony without
   value. (If a regex is preferred for the `_RE` convention, that is acceptable.)

5. **Helper name = `normalize_module_name(value: str) -> str`.** Full words, no
   abbreviations (CLAUDE.md §6); "module name" names the output role precisely.

6. **Messages use the module name.** Since the created directory *is* the module
   name, `print` output (`main.py:141`, `:145`) should reference it for accuracy
   and consistency.

## What We're NOT Doing

- Not changing `_PACKAGE_NAME_RE` or the accepted character set (`main.py:58-61`).
- Not touching the `Justfile` (`Justfile:59-73`).
- Not implementing full PEP 503 normalization (lowercasing, collapsing runs of
  `._-` into a single separator). Runs become runs of `_` (e.g. `a--b` → `a__b`),
  which is a valid identifier.
- Not splitting distribution name vs. import name into two threaded values.
- Not adding leading-digit / keyword remediation (see Open Risks).

## Open Risks

- **Leading-digit names.** The regex permits names starting with a digit
  (`9lives`, `main.py:58-61`); `import 9lives` is a `SyntaxError` and separator
  replacement does not fix it. Out of scope here, but it means "always valid
  Python" has an edge the mapping alone cannot guarantee. Flag in the
  implementation; consider a follow-up to tighten validation or prefix such names.
- **Python keyword names.** Distribution names like `class` or `import` are
  PyPI-valid but unusable as module names. Same status as above: not handled.
- **Display divergence.** With Decision 2, a user who typed `my-cool.package` sees
  a directory named `my_cool_package`; confirm this is acceptable UX (it is
  PEP 503-equivalent and predictable).
- **e2e coverage gap.** The only e2e exercises an all-lowercase-alpha name
  (`test_e2e.py:56`); add at least one normalization assertion so the conversion
  is regression-protected.
