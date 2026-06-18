# modernpackage — Codebase Specification

This document is an accurate, navigable reference to the `modernpackage` codebase for contributors and automated phases: goal, architecture, CLI entry point, scaffolding flow, build/tooling config, test setup, overall repository structure, and known gaps. Every architectural claim carries a `file:line` citation.

## Goal

- **Self-replicating CLI scaffolder** for new Python packages using a strict, modern toolset (`README.md:1-34`).
- Invoked as `modernpackage <name>` or `mp <name>` — orchestrates either a version branch or package initialization (`main.py:54-62`).

## Architecture overview

A small, two-module package with a single self-replication entrypoint:

- **`modernpackage/__init__.py`**: defines version constant (`__version__ = '0.0.9'`).
- **`modernpackage/main.py`**: CLI logic — `main()` orchestrates, `parse_args()` parses arguments, `validate_package_name()` validates, `init_new_package()` clones and initializes.
- **`pyproject.toml`**: single configuration hub (dependencies, build backend, tool settings) (`pyproject.toml:1-94`).
- **`Justfile`**: canonical command hub — all development and publishing commands route through it.

The self-replication path (one fenced ASCII diagram):

```
modernpackage <name>
        │  main()  (main.py:54-62)
        ▼
init_new_package(name)            (main.py:37-51)
        │
        ├─▶ git clone albertas/modernpackage  ./<name>
        │
        └─▶ just init <name>   (cwd=./<name>)
                  │
                  ├─ git grep + sed: rename every "modernpackage" → <name>
                  ├─ sed: reset __init__ version → 0.0.1
                  ├─ mv modernpackage/ → <name>/
                  └─ rm .git → git init → git add → git commit
```

## CLI entry point

- **Console scripts**: two entry points, `modernpackage` and `mp`, both route to `modernpackage.main:main` (`pyproject.toml:23-25`).
- **`main()` control flow** (`main.py:54-62`): calls `parse_args()`, then branches:
  - If `--version` / `-v` flag set, prints `modernpackage <__version__>` and exits.
  - Elif package name provided, calls `init_new_package(package_name)`.
  - Else no-op (silent exit).
- **`parse_args()` signature** (`main.py:18-34`): uses `argparse.ArgumentParser`:
  - `-v` / `--version`: `action='store_true'`, default `False`.
  - `package_name`: optional positional argument (`nargs='?'`), validated via `type=validate_package_name`.
- **`validate_package_name(value)` validator** (`main.py`): validates that `value` is a valid PEP 508 / PyPI distribution name (alphanumeric start/end, with hyphens/underscores/dots in between, case-insensitive via compiled regex `_PACKAGE_NAME_RE`); returns `value` if valid, else raises `ArgumentTypeError(f'Invalid package name: {value!r}')`.
- **`_PACKAGE_NAME_RE` pattern** (`main.py`): compiled regex constant matching PEP 508 / PyPI distribution names: `r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$'` with `re.IGNORECASE`.
- **`__version__` source** (`modernpackage/__init__.py:3`): constant `'0.0.9'`.

## Package-init flow

- **`init_new_package(package_name)` orchestration** (`main.py:37-51`):
  1. Resolves target path: `Path.cwd() / package_name`.
  2. Spawns first `subprocess.Popen`: `git clone https://github.com/albertas/modernpackage <cwd>/<name>` to target path.
  3. Captures output via `.communicate()[0]` (discarded).
  4. Spawns second `subprocess.Popen`: `just init <name>` with `cwd=<new_package_path>`.
  5. Captures output, decodes, and **discards the result** — no return value, no error handling.
  6. Both Popen calls flagged `# noqa: S603/S607` to suppress subprocess security lints.
  - **Known gap**: no error handling, no output logging, discarded results (current state).
- **`just init` recipe** transforms the cloned repository:
  - **Rename**: `git grep -l 'modernpackage' | xargs sed -i` (Linux) or `sed -i ''` (Darwin) to replace all occurrences of token "modernpackage" with the new package name.
  - **Version reset**: `sed` to replace the version string (e.g., `0.0.9`) with `0.0.1`.
  - **Directory rename**: `mv modernpackage <name>` to rename the package directory.
  - **Git reinitialization**: `rm -fr .git/ .venv`, then `git init -b main`, `git add .`, `git commit` with message "Initial modern <name> package setup".
- **Named parameter handling**: the `just init` recipe accepts a named parameter `package_name` with default `"modernpackage"`, interpolated as `{{package_name}}` in the recipe body.

## Build, versioning & dependencies

- **Build backend**: `hatchling` (`pyproject.toml:42-44`, `[build-system]`).
- **Build configuration** (`pyproject.toml:46-48`): includes `**/*.py`, excludes `tests/**`.
- **Version management** (`pyproject.toml:50-51`, `[tool.hatch.version]`): dynamic version read from `modernpackage/__init__.py`, currently `'0.0.9'` (`__init__.py:3`).
- **Python requirement**: `>= 3.14` (`pyproject.toml:8`).
- **Runtime dependencies**: empty list (`pyproject.toml:18`, `dependencies = []`).
- **Optional test group** (`pyproject.toml:27-37`): ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, vupi>=0.0.6.
- **Publishing**: `just publish` clears `dist/*`, runs `uv build`, then `uv publish`.
- **Dependency pinning**: `just compile` uses `uv pip compile` to generate `requirements.txt` (runtime, empty) and `requirements-dev.txt` (full dev pins).
- **Private index** (`pyproject.toml:92-94`): `[[tool.uv.index]]` defines a private GitLab uv index at `https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple`.

## Developer tooling

**Narrative**: `pyproject.toml` is the single configuration hub; `Justfile` is the canonical command hub (`pyproject.toml:1-94`). All development commands are invoked through the Justfile, which delegates to tools via `uv run` with a `sync` prerequisite.

- **Tool configuration** (`pyproject.toml:53-90`):
  - **ruff** (`pyproject.toml:53-74`): line-length 88, single quotes (`quote-style = "single"`), select ALL with targeted ignores (D203, D213, COM812, ISC001, ANN101; tests allow S101 and no docs).
  - **mypy** (`pyproject.toml:76-84`): `strict = true`, `python_version = "3.14"`, color output enabled.
  - **deadcode** (`pyproject.toml:86-90`): ignores `main` function, excludes tests.
  - **pytest** (`pyproject.toml:39-40`): `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"` — measures coverage on package only, fails below 95%, and excludes e2e tests by default.
  - **pip-audit**: no project configuration in `pyproject.toml`; simply invoked via `just audit`.
- **Justfile command hub**:
  - `sync`: syncs dependencies from requirements files (prerequisite for recipes that need the editable install).
  - `check`: runs `check-format check-lint check-complexity check-typecheck test audit deadcode` in sequence — the primary quality gate.
  - `fix`: runs `format fix-lint` — auto-fix tools.
  - Individual targets: `format`, `lint`, `typecheck`, `audit`, `deadcode`, `test`, `test-e2e` — all depend on `sync` except `publish`, `compile`, and `init`.
  - Specialized targets: `check-format`, `check-lint`, `check-complexity`, `check-typecheck` (check-only variants).
  - Other targets: `publish`, `compile`, `init package_name="modernpackage"`.

## Tests

- **Test coverage**: single test function `test_show_version()` in `tests/test_main.py:7-14`.
  - Patches `ArgumentParser` and `print` via `unittest.mock.patch`.
  - Forces `version = True` on parsed args.
  - Calls `main()`.
  - Asserts `print` called once with `f'modernpackage {__version__}'`.
- **Coverage of codebase**:
  - ✓ Covered: `--version` branch only.
  - ✗ Untested: `validate_package_name()` validation, `init_new_package()` cloning, package-name branch, real argument parsing.
- **Coverage gate** (`pyproject.toml:39-40`): `--cov-fail-under=50.0` — currently met by the single test, but uncovered paths are extensive.
- **Test infrastructure**: no `conftest.py`, no shared fixtures; per-test `unittest.mock.patch` only.

## Repository structure

- **Package**:
  - `modernpackage/__init__.py` — version constant.
  - `modernpackage/main.py` — CLI entry point, argument parsing, package initialization logic (imports `__version__` from `__init__`).
- **Tests**:
  - `tests/__init__.py` — test package marker.
  - `tests/test_main.py` — single test of `--version` branch.
- **Configuration & build**:
  - `pyproject.toml` — single config hub (build backend, dependencies, tool settings).
  - `Justfile` — command hub (development, testing, publishing recipes).
- **Dependencies**:
  - `requirements.txt` — runtime dependencies (currently empty).
  - `requirements-dev.txt` — pinned dev and test dependencies.
  - `uv.lock` — lock file for `uv`.
- **CI/CD**:
  - `.github/workflows/check-modernpackage-on-python314.yml` — GitHub Actions workflow.
  - `.gitlab-ci.yml` — GitLab CI configuration.
  - Both install `just` and run `just sync` + `just check` as the primary gate.
- **Documentation & metadata**:
  - `README.md` — user-facing usage guide and feature-request backlog.
  - `BACKLOG.md` — task tracking.
  - `issues/` — issue directory.
  - `workspace/` — task/research artifacts.
- **Build output**:
  - `dist/` — contains `0.0.8` wheel and sdist (version older than `__init__.py:3` `0.0.9`; see Known gaps).

The architecture is self-referential: the CLI clones this very repository, then `just init` rewrites the clone to a new package name (`main.py:37-51`).

## Known gaps & divergences

- **No error handling in `init_new_package()`** (`main.py:37-51`): both `Popen` calls discard output via `.communicate()[0]` with no success/failure checks. If `git clone` or `just init` fail, the user sees no error and the process silently continues.
- **Version drift** (`__init__.py:3`): source declares `__version__ = '0.0.9'`, but `dist/` contains `0.0.8` wheel and sdist. No in-repo evidence of which version is published; the discrepancy is unresolved.
- **README Feature requests are aspirational** (`README.md:36-78`): the "Feature requests" section lists desired enhancements (virtualenv init, git/network checks, async tests, etc.), none of which are implemented. Notably, the documented no-network crash traceback (`README.md:57-76`) is a known failure mode, not a solved feature.
