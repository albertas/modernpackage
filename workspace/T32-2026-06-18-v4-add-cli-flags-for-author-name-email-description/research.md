# Research Findings

Scope: `modernpackage/main.py`, the template `pyproject.toml`, the `just init`
recipe in `Justfile`, and tests under `tests/`. All references are to the
committed checkout.

## Q1: How is the argument parser constructed in `parse_args`, what args/flags exist, and what conventions are used?

### Findings
- `parse_args` is defined at `modernpackage/main.py:122-138`. It builds a bare
  `ArgumentParser()` with no `prog`, `description`, or `epilog`
  (`main.py:124`).
- It defines exactly two arguments:
  - `-v` / `--version` — `main.py:125-131`. Optional flag,
    `action='store_true'`, `default=False`, help `'Show package version.'`.
    Short + long option pair.
  - `package_name` — `main.py:132-137`. Positional, `nargs='?'` (optional),
    `type=validate_package_name`, help
    `'Name of a new package to initialise in a local directory.'`. No explicit
    `default`, so it defaults to `None` when omitted.
- Returns the parsed `Namespace` directly via `parser.parse_args()`
  (`main.py:138`). No subparsers, no argument groups, no metavar overrides.
- Conventions observed: single-letter short flag paired with a `--long` form for
  the optional flag; positional uses snake_case `package_name`; help strings are
  short imperative sentences ending with a period; type-level validation is
  attached via `type=` rather than checked later.

## Q2: How does a parsed argument flow from `parse_args` → `main` → `init_new_package`?

### Findings
- `main` (`main.py:202-216`) calls `parsed_args = parse_args()` (`main.py:204`).
- Branching on the Namespace attributes:
  - If `parsed_args.version` is truthy → prints `f'modernpackage {__version__}'`
    and falls through to `return 0` (`main.py:206-207, 216`).
  - `elif parsed_args.package_name` → calls
    `init_new_package(package_name=parsed_args.package_name)` inside a
    `try/except RuntimeError` (`main.py:209-214`). Passed as a **keyword**
    argument named `package_name`.
  - On `RuntimeError`, prints the error to `sys.stderr` and returns `1`
    (`main.py:212-214`).
  - If neither branch fires (no args), returns `0` (`main.py:216`).
- `init_new_package(package_name: str) -> int` (`main.py:141-199`) uses the value:
  - `module_name = normalize_module_name(package_name)` (`main.py:143`).
  - `new_package_path = Path.cwd() / module_name` (`main.py:144`).
  - `module_name`/`new_package_path` feed three `Popen` calls: `git clone … <new_package_path>`
    (`main.py:146-151`), `just init <module_name>` with `cwd=new_package_path`
    (`main.py:162-167`), and `just check` with `cwd=new_package_path`
    (`main.py:182-188`).
  - Return contract: `0` when `just check` passes (`main.py:191-193`), `1` when
    it fails (`main.py:194-199`); clone/init failures raise `RuntimeError`.
- Note: the original `package_name` (with `.`/`-`) is only used to derive
  `module_name`; everything downstream uses the normalized `module_name`.

## Q3: What patterns exist for validating/type-converting argument values, and how are invalid inputs reported?

### Findings
- Validation is wired through argparse's `type=` hook:
  `type=validate_package_name` (`main.py:136`). argparse calls it during parsing
  and converts an `ArgumentTypeError` into a usage error + exit code 2.
- `validate_package_name(value: str) -> str` (`main.py:95-108`):
  - Rejects names failing `_PACKAGE_NAME_RE` (`main.py:58-61`, PEP 503/508
    pattern, `re.IGNORECASE`); builds a reason via `_explain_invalid_package_name`
    and raises `ArgumentTypeError(f'Invalid package name: {value!r} — {reason}')`
    (`main.py:97-100`).
  - Rejects names whose normalized module name is in
    `sys.stdlib_module_names` (`_STDLIB_MODULE_NAMES`, `main.py:70`) with a
    "collides with the Python standard-library module" `ArgumentTypeError`
    (`main.py:101-107`).
  - Returns the original (un-normalized) `value` on success (`main.py:108`).
- `_explain_invalid_package_name(value)` (`main.py:73-92`) produces precise,
  most-specific-first reasons: empty (`main.py:81-82`), disallowed character via
  `_DISALLOWED_CHAR_RE` (`main.py:65, 83-89`), else leading/trailing separator
  (`main.py:92`).
- `normalize_module_name(value)` (`main.py:111-119`) is the type-conversion
  helper: replaces `.` and `-` with `_`, preserves `_`, leaves case unchanged.
  Not registered as an argparse `type`; called inside `init_new_package`.
- Reporting pattern: invalid CLI input → `ArgumentTypeError` (argparse prints to
  stderr, exits 2). Runtime/external failures → `RuntimeError` surfaced by
  `main` to stderr with exit code 1 (`main.py:155-159, 178-180, 212-214`).
  `humanize_git_clone_error` (`main.py:47-53`) maps known git stderr text to
  friendly messages, prepended to the raw error (`main.py:157-158`).

## Q4: What metadata fields exist in the template `pyproject.toml`, with their placeholder values and section locations?

### Findings
- `[project]` table (`pyproject.toml:1-18`):
  - `name = "modernpackage"` (`pyproject.toml:2`).
  - `authors = [{name = "Name Surname", email = "email@example.com"}]`
    (`pyproject.toml:3-5`) — single inline table; placeholders `Name Surname`
    and `email@example.com`.
  - `description = "Package configuration example using bleeding edge toolset."`
    (`pyproject.toml:6`).
  - `readme = "README.md"` (`pyproject.toml:7`); `requires-python = ">= 3.14"`
    (`pyproject.toml:8`).
  - License is expressed as a **classifier**, not a `license` field:
    `"License :: OSI Approved :: MIT License"` (`pyproject.toml:11`). No
    `[project] license = …` key exists.
  - `dynamic = ["version"]` (`pyproject.toml:17`) — version comes from
    `modernpackage/__init__.py` via `[tool.hatch.version]` (`pyproject.toml:53-54`).
- `[project.urls]` (`pyproject.toml:20-21`): only
  `homepage = "https://github.com/albertas/modernpackage"`. No separate
  `repository` key.
- Related literal: the hardcoded clone URL
  `https://github.com/albertas/modernpackage` in `main.py:147` (independent of
  pyproject).
- `__version__ = '0.0.9'` in `modernpackage/__init__.py:3` (current template
  version literal).

## Q5: How does the `just init` recipe transform the clone, and when is it invoked?

### Findings
- Recipe `init package_name="modernpackage":` is in `Justfile:59-73`.
- Steps:
  1. Echo `Initializing {{package_name}}...` (`Justfile:60`).
  2. Linux branch (`Justfile:61-63`):
     `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'`
     — rewrites the string `modernpackage` to the new name across every tracked
     file that contains it.
  3. macOS/Darwin branch (`Justfile:64-66`): same but BSD `sed -i ''` form.
  4. Version reset (`Justfile:67`):
     `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py`
     — replaces any `X.Y.Z` semver in `__init__.py` with `0.0.1`. (Runs against
     the still-named `modernpackage/__init__.py` path before the directory rename.)
  5. `mv modernpackage {{package_name}}` (`Justfile:68`) — renames the package
     source directory to the new name.
  6. `rm -fr .git/ .venv` (`Justfile:69`) — drops cloned git history and venv.
  7. `git init -b main .` → `git add .` → `git commit -m "Initial modern
     {{package_name}} package setup"` (`Justfile:70-72`) — fresh repo + initial
     commit.
  8. Final echo with `cd … && just check` hint (`Justfile:73`).
- Note ordering subtlety: step 4 edits `modernpackage/__init__.py` *before* the
  `mv` in step 5, while steps 2-3 have already replaced the literal
  `modernpackage` substring inside file *contents* (including `__init__.py`'s
  docstring) but not file *paths*.
- Invocation point: `init_new_package` runs `just init <module_name>` as the
  second `Popen`, with `cwd=new_package_path`, immediately after a successful
  `git clone` (`main.py:162-167`). The `{{package_name}}` argument passed is the
  normalized `module_name` (`main.py:163`).

## Q6: How are `parse_args` and `init_new_package` covered by tests, including mocking of parser/subprocess/argument flow?

### Findings
- Tests live in `tests/test_main.py` (unit) and `tests/test_e2e.py` (e2e,
  marked `@pytest.mark.e2e`, excluded by default per `pyproject.toml:40-43`).
- `parse_args` coverage:
  - `test_parse_args_version_flag` (`test_main.py:91-94`): patches `sys.argv` to
    `['modernpackage', '--version']`, asserts `result.version is True`.
  - `test_parse_args_package_name` (`test_main.py:97-100`): patches `sys.argv`
    to `['modernpackage', 'mypackage']`, asserts `result.package_name == 'mypackage'`.
  - Indirectly, `main` tests patch `modernpackage.main.ArgumentParser` and set
    `argparse_mock().parse_args().version` / `.package_name` to drive branches
    (`test_main.py:18-26, 167-231`).
- `init_new_package` coverage (subprocess mocking pattern — patch
  `modernpackage.main.Popen`):
  - Happy path: `test_init_new_package` (`test_main.py:103-108`) sets
    `popen_mock.return_value.returncode = 0`,
    `.communicate.return_value = (b'', b'')`, asserts `popen_mock.call_count == 3`.
  - Name normalization + call args: `test_init_new_package_normalizes_name`
    (`test_main.py:111-123`) inspects `popen_mock.call_args_list[0]` clone target
    name and `call_args_list[1]` (`['just','init','my_cool_package']`, `cwd`).
  - `just check` call: `test_init_new_package_runs_just_check`
    (`test_main.py:126-133`) asserts third call is `['just','check']` with `cwd`.
  - Failure paths use `popen_mock.side_effect = [mock1, mock2, …]` with
    per-step `MagicMock`s and distinct `returncode`s:
    git-clone failure (`test_main.py:136-141`), `just` not installed via
    `FileNotFoundError` side effect (`test_main.py:144-151`), `just init`
    failure (`test_main.py:154-164`), `just check` failed reporting
    (`test_main.py:283-302`), network-failure humanized message
    (`test_main.py:305-318`).
  - Output assertions patch `modernpackage.main.print`
    (`test_main.py:270-302`).
- Argument-flow / `main` coverage: `test_main_with_package_name`
  (`test_main.py:167-177`) patches `ArgumentParser` and
  `modernpackage.main.init_new_package`, asserting
  `init_mock.assert_called_once_with(package_name='mypackage')`. Return-code and
  stderr-surfacing variants at `test_main.py:180-217`; no-args at
  `test_main.py:220-231`.
- E2E: `test_scaffolded_package_passes_check` (`test_e2e.py:52-83`) clones the
  local repo, runs `just init <module_name>` (with injected
  `_GIT_IDENTITY_ENV`, `test_e2e.py:29-34, 65-69`), and asserts the scaffold
  passes `just check`; verifies `__init__.py` contains `0.0.1`
  (`test_e2e.py:78-80`).

## Cross-Cutting Observations
- Two distinct name forms flow through the system: the user-supplied
  `package_name` (may contain `.`/`-`, validated but not rewritten) and the
  derived `module_name` (normalized, used for paths and the `just init`
  argument) — `main.py:143-144`.
- The literal string `modernpackage` is the substitution token everywhere:
  pyproject `name`, the clone URL (`main.py:147`), and every tracked file the
  `just init` `git grep | sed` pass rewrites (`Justfile:62-65`).
- Author/email/description are static placeholders in `pyproject.toml:3-6`; no
  code path currently reads or rewrites them — only the package `name` and
  version are transformed by `just init`.
- Error-reporting convention is two-tier: `ArgumentTypeError` for invalid CLI
  input (parse-time, exit 2) vs `RuntimeError` surfaced by `main` for runtime
  failures (exit 1), with `humanize_git_clone_error` enriching git failures.
- Test conventions match CLAUDE.md/Code Best Practices: top-level `def test_*`,
  plain `assert`, SDK/subprocess seams patched on the defining module object
  (`modernpackage.main.Popen`, `modernpackage.main.ArgumentParser`).

## Open Areas
- There is no existing `license` or `repository` key in `pyproject.toml`; license
  is only a classifier (`pyproject.toml:11`) and the only URL is `homepage`
  (`pyproject.toml:21`). The questions ask about these fields; the answer is that
  they are absent in their dedicated forms.
- No current CLI flag, `parse_args` argument, or `init_new_package` parameter
  exists for author name, author email, or description — only `--version` and the
  `package_name` positional exist (`main.py:122-138`). The `just init` recipe
  does not substitute any author/email/description placeholders (`Justfile:59-73`).
