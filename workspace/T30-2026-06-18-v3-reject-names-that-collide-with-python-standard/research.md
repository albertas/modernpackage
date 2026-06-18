# Research Findings

Scope: `modernpackage/main.py`, `tests/test_main.py`, `tests/test_e2e.py`,
`Justfile`, `pyproject.toml`. The whole CLI lives in one module
(`modernpackage/main.py`, 178 lines); no separate validation/name modules exist.

## Q1: How is a user-supplied package name validated today?

### Findings
- Validation runs **inside argparse**, via the `type=` callback on the positional
  argument: `parse_args()` registers `type=validate_package_name` for
  `package_name` (`modernpackage/main.py:93-98`).
- The rule is a single regex, `_PACKAGE_NAME_RE`
  (`modernpackage/main.py:58-61`): `^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$`
  with `re.IGNORECASE`. Comment states it is "PEP 503 / PEP 508 valid
  distribution name": alphanumeric ends, with `-`, `_`, `.` permitted internally,
  case-insensitive (`modernpackage/main.py:56-57`).
- `validate_package_name(value)` matches the regex; on failure it raises
  `ArgumentTypeError(f'Invalid package name: {value!r}')`; on success it returns
  `value` unchanged (`modernpackage/main.py:64-69`).
- Rejection reporting is delegated to argparse: an `ArgumentTypeError` raised in a
  `type=` callback makes argparse print a usage message + the error to **stderr**
  and exit with **code 2** (standard argparse behavior; not custom code in repo).
- There is **no check** against Python keywords or standard-library/builtin
  module names. The regex is purely about character composition. The docstring of
  `normalize_module_name` explicitly notes leading-digit names (`9lives`) and
  keywords (`class`) "remain invalid module names — out of scope"
  (`modernpackage/main.py:77-79`).

## Q2: How is the accepted name transformed into the module/directory name, and when relative to validation?

### Findings
- Transformation is `normalize_module_name(value)`: returns
  `value.replace('.', '_').replace('-', '_')` — only `.` and `-` become `_`; `_`
  preserved; **case unchanged** (`modernpackage/main.py:72-80`).
- Ordering: validation happens first, during argument parsing
  (`parse_args` → `validate_package_name`, `main.py:97-99`, `165`). Normalization
  happens **later**, at the start of `init_new_package`, only after `main()`
  decides to scaffold (`main.py:170-172` → `init_new_package` → `main.py:104`).
- So the flow is: parse/validate (raw name) → `main()` dispatch →
  `init_new_package(package_name)` normalizes to `module_name`. The two functions
  are independent; `normalize_module_name` assumes its input was already validated
  (`main.py:76-77`).

## Q3: Runtime relationship between validated input name and on-disk module name; where each form is consumed.

### Findings
- Two distinct forms coexist at runtime:
  - `package_name` — the raw validated string (may contain `.`/`-`, mixed case).
  - `module_name = normalize_module_name(package_name)` (`main.py:104`).
- **Case handling**: not altered by normalization (`.replace` only). A name like
  `My-Pkg` becomes module `My_Pkg`. No lowercasing anywhere.
- **Separator substitution**: `.` and `-` → `_`; runs are *not* collapsed
  (`a--b` → `a__b`), an explicit design intent asserted in tests
  (`tests/test_main.py:35`).
- Downstream consumers of `module_name` only:
  - Directory path: `new_package_path = Path.cwd() / module_name` (`main.py:105`),
    used as the `git clone` destination (`main.py:108`) and as `cwd` for the
    subprocesses (`main.py:128`, `148`).
  - `just init`: invoked as `['just', 'init', module_name]` (`main.py:124`).
  - Success/failure messages reference `module_name` (`main.py:153`, `156-157`).
- `package_name` (raw) is consumed only as the input to normalization and the
  argparse Namespace (`main.py:104`, `170-172`). The clone URL is hardcoded
  (`https://github.com/albertas/modernpackage`, `main.py:108`) — not derived from
  the name.
- `just init <name>` (Justfile:59-73) does the actual rename: `git grep`/`sed`
  replaces the string `modernpackage` everywhere, then `mv modernpackage <name>`
  creates the source package directory. So `module_name` becomes both the outer
  clone dir and the inner package dir name (verified in e2e:
  `source_dir = destination / module_name`, `tests/test_e2e.py:72-76`, which also
  asserts no `-`/`.` and presence of `_`).

## Q4: Patterns for raising/presenting input errors vs runtime/subprocess errors, and exit codes.

### Findings
- **Input errors**: raise `ArgumentTypeError` inside the argparse `type=` callback
  (`validate_package_name`, `main.py:68`). argparse handles presentation (stderr +
  usage) and exits with code **2**. Not caught in `main()`.
- **Runtime/subprocess errors**: raised as `RuntimeError` from
  `init_new_package` for git clone failure (`main.py:116-120`), `just` not
  installed (`FileNotFoundError` → re-raised `RuntimeError`, `main.py:130-135`),
  and `just init` failure (`main.py:139-141`). `main()` wraps the call in
  `try/except RuntimeError`, prints the error to stderr, and returns **1**
  (`main.py:171-175`).
- A third tier: `just check` failure does **not** raise; it prints to stderr and
  `init_new_package` **returns 1** directly (`main.py:152-160`); success returns 0
  and prints a pass message.
- Error-message humanization: `humanize_git_clone_error` maps known git stderr
  patterns to friendly text via an ordered `_GIT_CLONE_ERROR_MESSAGES` list
  (most-specific-first), and the `RuntimeError` message combines friendly + raw
  text (`main.py:12-53`, `116-120`).
- Exit-code summary: usage/validation error → 2 (argparse); scaffolding
  RuntimeError or `just check` failure → 1; success / version / no-args → 0
  (`main.py:152-177`).

## Q5: What the test suite covers for name validation and module-name normalization.

### Findings
- `test_validate_package_name_valid` — accepts `mypackage`, `my-package`,
  `my_package`, `my.package`, `a` (returns identical string)
  (`tests/test_main.py:41-46`).
- `test_validate_package_name_invalid` — rejects `-bad`, `bad-`, `has space`, `''`
  via `pytest.raises(ArgumentTypeError, match='Invalid package name')`
  (`tests/test_main.py:49-52`). No keyword/stdlib-collision cases exist.
- `test_normalize_module_name` — table of cases:
  `my-cool.package→my_cool_package`, `my_package→my_package`, `a→a`,
  `my-cool_pkg.v2→my_cool_pkg_v2`, `a--b→a__b` (runs preserved)
  (`tests/test_main.py:29-38`).
- `test_init_new_package_normalizes_name` — asserts the normalized name is used as
  clone dir and in `['just','init','my_cool_package']` and as `cwd`
  (`tests/test_main.py:75-87`).
- `parse_args` tests cover the version flag and a plain package name
  (`tests/test_main.py:55-64`) but do not exercise the argparse rejection path
  (exit code 2).
- e2e (`tests/test_e2e.py:52-83`) uses `scaffold-check.pkg` →
  `scaffold_check_pkg`, asserting `-`/`.` absent and `_` present in the on-disk
  module dir (lines 58-76).
- Coverage gate: `--cov-fail-under=95.0`, default run excludes e2e
  (`-m 'not e2e'`) (`pyproject.toml:40`).

## Q6: Targeted Python version, dependency baseline, and stdlib facilities for enumerating module names.

### Findings
- Targeted version: `requires-python = ">= 3.14"`; classifier and mypy both pin
  3.14 (`pyproject.toml:8`, `15`, `83`). Installed interpreter is CPython
  **3.14.3** (verified via `.venv/bin/python`).
- Runtime dependencies: **none** — `dependencies = []` (`pyproject.toml:18`);
  `requirements.txt` is empty (autogenerated header only). Dev/test extras:
  ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi>=0.0.7
  (`pyproject.toml:27-37`).
- Stdlib facilities available under 3.14 for enumerating module names
  (verified at runtime in this venv):
  - `sys.stdlib_module_names` — `frozenset` of all stdlib top-level module names
    (297 entries here); available since Python 3.10.
  - `sys.builtin_module_names` — `tuple` of modules compiled into the
    interpreter.
  - `keyword.kwlist` — list of 35 reserved keywords; `keyword.iskeyword('class')`
    → True.
  - `keyword.softkwlist` / `keyword.issoftkeyword('match')` → True (soft
    keywords).
- `main.py` currently imports only `re`, `sys`, `argparse`, `pathlib`,
  `subprocess` — none of the above enumeration facilities are imported/used today
  (`main.py:1-9`).

## Cross-Cutting Observations
- Single-module architecture: all validation, normalization, error humanization,
  and orchestration live in `modernpackage/main.py`. Tests import private/public
  symbols directly from `modernpackage.main` (`tests/test_main.py:8-15`).
- Two-form name discipline (raw `package_name` vs derived `module_name`) is
  consistent: validation guards the raw form; everything filesystem/subprocess
  uses the normalized form.
- Validation today is **composition-only** (regex). There is documented,
  intentional non-coverage of leading-digit and keyword names
  (`main.py:77-79`) — and, by extension, no stdlib-name collision check.
- Error style follows CLAUDE/code-style conventions: loud `RuntimeError`/
  `ArgumentTypeError` for invariants/input, graceful stderr+return-code at
  subprocess boundaries (`main.py:107-160`).

## Open Areas
- The argparse exit-code-2 path for invalid input is not directly asserted by any
  test (only the `ArgumentTypeError` raise from `validate_package_name` is).
- No existing code enumerates or rejects stdlib/keyword names; this is currently
  absent rather than partially implemented (factual, per `main.py` imports and
  the `normalize_module_name` docstring).
