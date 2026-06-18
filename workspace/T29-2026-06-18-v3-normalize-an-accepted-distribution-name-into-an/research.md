# Research Findings

Scope covered: `modernpackage/main.py`, root `Justfile`, `tests/test_main.py`,
`tests/test_e2e.py`, `modernpackage/__init__.py`. The codebase is small and was
read directly rather than via fan-out agents.

## Q1: How is the user-supplied package name accepted, validated, and passed through to scaffolding subprocesses?

### Findings
- Accepted as a single positional CLI argument `package_name` in `parse_args`
  (`main.py:82-87`), `nargs='?'` (optional), with `type=validate_package_name`
  (`main.py:86`) so argparse validates at parse time.
- Validated by `validate_package_name(value)` (`main.py:64-69`): matches against
  `_PACKAGE_NAME_RE`; on mismatch raises `ArgumentTypeError('Invalid package name: ...')`,
  otherwise returns `value` unchanged (no transformation).
- `main()` (`main.py:151-165`) reads `parsed_args.package_name` (`main.py:158`)
  and calls `init_new_package(package_name=parsed_args.package_name)` (`main.py:160`).
- In `init_new_package` (`main.py:91-148`) the raw name is consumed three ways:
  1. Destination directory: `new_package_path = Path.cwd() / package_name` (`main.py:93`),
     passed as the `git clone` target (`main.py:96`).
  2. Passed verbatim as an argument to `just init`: `['just', 'init', package_name]`
     (`main.py:112`), with `cwd=new_package_path` (`main.py:116`).
  3. Used in user-facing print messages (`main.py:141`, `main.py:145`).
- A third subprocess `['just', 'check']` runs in the new dir (`main.py:131-137`);
  it does not re-consume the name except in reporting.
- Errors from clone are humanized via `humanize_git_clone_error` (`main.py:106`);
  RuntimeErrors bubble to `main` which prints to stderr and returns 1 (`main.py:161-163`).

## Q2: What does the `just init` recipe do with the name — substitutions, renames, edits, and assumed character set?

### Findings
Recipe `init package_name="modernpackage"` (`Justfile:59-73`); default is the literal `modernpackage`.
- Step echo announcement (`Justfile:60`).
- Text substitution (OS-branched): `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'`
  on Linux (`Justfile:61-63`) and the BSD `sed -i ''` variant on Darwin (`Justfile:64-66`).
  Replaces every literal `modernpackage` occurrence in all git-tracked files that contain it
  (imports, pyproject, README, etc.).
- Version reset: `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py`
  (`Justfile:67`) — rewrites the `X.Y.Z` version (currently `0.0.9`, `__init__.py:3`) to `0.0.1`.
  Note this runs on the path `modernpackage/__init__.py` *before* the rename.
- Directory rename: `mv modernpackage {{package_name}}` (`Justfile:68`) — renames the source-package
  directory to the new name.
- `rm -fr .git/ .venv` (`Justfile:69`); fresh repo `git init -b main` (`Justfile:70`),
  `git add .` (`Justfile:71`), `git commit -m "Initial modern {{package_name}} package setup"` (`Justfile:72`).
- Final echo (`Justfile:73`).

Assumed character set per step:
- The `sed s/modernpackage/{{package_name}}/g` uses `/` as the delimiter, so the name is assumed to
  contain no `/`; sed replacement metacharacters (`&`, `\`) are also assumed absent.
- `mv` / directory name / `git commit -m` treat the name as a shell + filesystem token (no quoting in
  the recipe), so spaces/shell-special chars are assumed absent.
- No normalization or lowercasing occurs in the recipe — the value from validation is used as-is.
  A name with `.` or `-` becomes a literal directory name and is substituted into Python import lines.

## Q3: What does the validation regex permit, and which standards does it cite?

### Findings
- `_PACKAGE_NAME_RE = re.compile(r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$', re.IGNORECASE)`
  (`main.py:58-61`).
- Permits: alphanumeric at both first and last position; internally `.`, `_`, `-` allowed. A
  single-character name must be alphanumeric. Case-insensitive (so uppercase accepted).
- Disallows: leading/trailing `.`, `_`, `-`; spaces; empty string.
- Cited standards (comment `main.py:56-57`): "PEP 503 / PEP 508 valid distribution name". The
  docstring of `validate_package_name` says "PEP 508 / PyPI distribution name" (`main.py:65`).
- The function only validates; it does **not** apply PEP 503 normalization (lowercasing, collapsing
  runs of `._-` into a single `-`). No normalization helper exists in the module.

## Q4: Where is the name used as an import path / source-dir name vs. a distribution/display name, and are they distinguished?

### Findings
- A single `package_name` value is reused for all roles; there is **no distinction** in code.
- Import path / source directory: `mv modernpackage {{package_name}}` (`Justfile:68`) makes the name
  the Python package directory; the global `sed` substitution (`Justfile:62`/`65`) rewrites
  `from modernpackage import ...` (e.g. `main.py:9`, `__init__` references) into `from {{package_name}} import ...`.
- Filesystem destination: clone target dir `Path.cwd() / package_name` (`main.py:93`).
- Distribution/display name: same value flows into pyproject/README via the literal substitution and
  into the commit message (`Justfile:72`) and CLI print messages (`main.py:141`,`145`).
- Consequence (factual): regex permits `.` and `-` (valid distribution chars) but those are invalid in
  Python import names; the code does not separate or convert them. e2e test only exercises the simple
  all-lowercase-alpha name `scaffoldcheck` (`test_e2e.py:56`).

## Q5: Helper-function patterns in `main.py` for transforming/classifying strings

### Findings
- `humanize_git_clone_error(stderr_text: str) -> str | None` (`main.py:47-53`): lowercases input
  (`main.py:49`), iterates the module constant `_GIT_CLONE_ERROR_MESSAGES` in order, returns the first
  matching friendly message or `None` if none match. Return contract documented in docstring (`main.py:48`).
- Backing constant `_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern[str], str]]` (`main.py:12-44`):
  list of (compiled regex, message) tuples, "Ordered most-specific first" (`main.py:11`), with inline
  comments per category and an explicit ordering caveat ("must precede broad 'permission denied'",
  `main.py:26`; "broad, intentionally last", `main.py:39`).
- `validate_package_name(value: str) -> str` (`main.py:64-69`): classifier/validator that returns the
  value unchanged or raises `ArgumentTypeError`.
- Module-level regex constants use the `_RE` suffix and leading-underscore privacy convention:
  `_GIT_CLONE_ERROR_MESSAGES`, `_PACKAGE_NAME_RE` (`main.py:58`). Both are explicitly type-annotated.
- No existing function *transforms* a string into a new value (e.g. normalizes/slugifies); the two
  helpers either map error text → message or validate-and-passthrough.

## Q6: How are name-handling / string-transformation functions tested?

### Findings
- Assertion style: plain `assert` and `pytest.raises(..., match=...)`; top-level `def test_*` functions,
  no test classes (`tests/test_main.py`).
- Validation success: `test_validate_package_name_valid` (`test_main.py:28-33`) asserts identity return
  for `mypackage`, `my-package`, `my_package`, `my.package`, `a`.
- Validation failure: `test_validate_package_name_invalid` (`test_main.py:36-39`) loops bad names
  `('-bad', 'bad-', 'has space', '')` expecting `ArgumentTypeError` matching `'Invalid package name'`.
- Humanizer: one test per category — network (`test_main.py:170`), repo-not-found (`175`), auth (`184`),
  directory-exists (`191`), and unknown→`None` (`201`). Each asserts the exact returned message.
- Mocking: `unittest.mock` `patch`/`MagicMock`; `Popen` patched on the module object
  (`patch('modernpackage.main.Popen')`), with `side_effect` lists to sequence clone/init/check
  (`test_main.py:84-85`, `97-98`, `233`). No custom fixtures; only built-in `tmp_path` in e2e.
- e2e (`test_e2e.py:50-74`) scaffolds from the local checkout with `package_name = 'scaffoldcheck'`
  (`test_e2e.py:56`) and asserts the generated `__init__.py` contains `0.0.1` (`test_e2e.py:71`).
- Edge cases covered: leading/trailing hyphen, embedded space, empty string. **No** tests exercise
  normalization, case-folding, run-collapsing of `._-`, or import-vs-distribution name divergence.

## Cross-Cutting Observations
- PEP 503/508 are referenced in comments/docstrings (`main.py:56-57`, `65`) but only *validation* is
  implemented — no normalization exists anywhere in `main.py` or the `Justfile`.
- One raw `package_name` value serves every role (clone dir, `just init` arg, source dir via `mv`,
  substituted distribution/import text, commit message, print output) with no transformation.
- Conventions: `_`-prefixed module-private symbols, `_RE` suffix for compiled regex constants,
  explicit type annotations on module constants, ordered most-specific-first pattern lists.
- Justfile substitution is a literal whole-string `sed` replace keyed on the exact token `modernpackage`;
  it assumes the new name is a clean shell/filesystem/sed-safe token.

## Open Areas
- The task title references "normalize an accepted distribution name into an [import name]"; the current
  codebase has **no normalization step** — only `validate_package_name` (validate + passthrough). This is
  an observed absence, not a located implementation.
- No code currently derives a Python-import-safe name from a distribution name; `mv`/substitution use the
  validated value directly (`Justfile:62-68`), so the gap between PEP 503 distribution chars (`.`, `-`)
  and legal Python identifiers is presently unhandled.
