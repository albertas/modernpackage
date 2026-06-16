# modernpackage — Codebase Specification

This document is an accurate, navigable reference to the `modernpackage` codebase for contributors and automated phases: goal, architecture, CLI entry point, scaffolding flow, build/tooling config, test setup, overall repository structure, and known gaps. Every architectural claim carries a `file:line` citation.

## Goal

- **Self-replicating CLI scaffolder** for new Python packages using a strict, modern toolset (`README.md:1-34`).
- Invoked as `modernpackage <name>` or `mp <name>` — orchestrates either a version branch or package initialization (`main.py:54-62`).

## Architecture overview

A small, two-module package with a single self-replication entrypoint:

- **`modernpackage/__init__.py`**: defines version constant (`__version__ = '0.0.9'`).
- **`modernpackage/main.py`**: CLI logic — `main()` orchestrates, `parse_args()` parses arguments, `check_alpha_numeric()` validates, `init_new_package()` clones and initializes.
- **`pyproject.toml`**: single configuration hub (dependencies, build backend, tool settings) (`pyproject.toml:1-94`).
- **`Makefile`**: canonical command hub — all development and publishing commands route through it (`Makefile:1-78`).

The self-replication path (one fenced ASCII diagram):

```
modernpackage <name>
        │  main()  (main.py:54-62)
        ▼
init_new_package(name)            (main.py:37-51)
        │
        ├─▶ git clone albertas/modernpackage  ./<name>
        │
        └─▶ make init <name>   (cwd=./<name>)  (Makefile:60-75)
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
  - `package_name`: optional positional argument (`nargs='?'`), validated via `type=check_alpha_numeric`.
- **`check_alpha_numeric(value)` validator** (`main.py:10-15`): returns `value` if `value.isalnum()`, else raises `ArgumentTypeError('Non-AlphaNumeric package name')`.
- **`__version__` source** (`modernpackage/__init__.py:3`): constant `'0.0.9'`.

## Package-init flow

- **`init_new_package(package_name)` orchestration** (`main.py:37-51`):
  1. Resolves target path: `Path.cwd() / package_name`.
  2. Spawns first `subprocess.Popen`: `git clone https://github.com/albertas/modernpackage <cwd>/<name>` to target path.
  3. Captures output via `.communicate()[0]` (discarded).
  4. Spawns second `subprocess.Popen`: `make init <name>` with `cwd=<new_package_path>`.
  5. Captures output, decodes, splits on `'make:'`, and **discards the result** — no return value, no error handling.
  6. Both Popen calls flagged `# noqa: S603/S607` to suppress subprocess security lints.
  - **Known gap**: no error handling, no output logging, discarded results (current state).
- **`Makefile init` target** (`Makefile:60-75`) transforms the cloned repository:
  - **Rename**: `git grep -l 'modernpackage' | xargs sed -i` (Linux) or `sed -i ''` (Darwin) to replace all occurrences of token "modernpackage" with the new package name.
  - **Version reset**: `sed` to replace the version string (e.g., `0.0.9`) with `0.0.1`.
  - **Directory rename**: `mv modernpackage <name>` to rename the package directory.
  - **Git reinitialization**: `rm -fr .git/ .venv`, then `git init -b main`, `git add .`, `git commit` with message "Initial modern <name> package setup".
- **Make argument handling** (`Makefile:2`, `Makefile:77-78`):
  - Default value for `args` variable: `"modernpackage"` — used as fallback if no CLI argument provided.
  - Catch-all rule `%:` and `@:` allows any unrecognized make goal to silently pass (no error if `make init mypackage` is called).

## Build, versioning & dependencies

- **Build backend**: `hatchling` (`pyproject.toml:42-44`, `[build-system]`).
- **Build configuration** (`pyproject.toml:46-48`): includes `**/*.py`, excludes `tests/**`.
- **Version management** (`pyproject.toml:50-51`, `[tool.hatch.version]`): dynamic version read from `modernpackage/__init__.py`, currently `'0.0.9'` (`__init__.py:3`).
- **Python requirement**: `>= 3.14` (`pyproject.toml:8`).
- **Runtime dependencies**: empty list (`pyproject.toml:18`, `dependencies = []`).
- **Optional test group** (`pyproject.toml:27-37`): hatch, ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, vupi>=0.0.6.
- **Publishing** (`Makefile:22-25`): `make publish` clears `dist/*`, runs `hatch build`, then `hatch -v publish`.
- **Dependency pinning** (`Makefile:53-55`): `make compile` uses `uv pip compile` to generate `requirements.txt` (runtime, empty) and `requirements-dev.txt` (full dev pins).
- **Private index** (`pyproject.toml:92-94`): `[[tool.uv.index]]` defines a private GitLab uv index at `https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple`.

## Developer tooling

**Narrative**: `pyproject.toml` is the single configuration hub; `Makefile` is the canonical command hub (`pyproject.toml:1-94`, `Makefile:1-78`). All development commands are invoked through the Makefile, which manages virtual environment setup (`.venv` target) and delegates to installed tools.

- **Tool configuration** (`pyproject.toml:53-90`):
  - **ruff** (`pyproject.toml:53-74`): line-length 88, single quotes (`quote-style = "single"`), select ALL with targeted ignores (D203, D213, COM812, ISC001, ANN101; tests allow S101 and no docs).
  - **mypy** (`pyproject.toml:76-84`): `strict = true`, `python_version = "3.14"`, color output enabled.
  - **deadcode** (`pyproject.toml:86-90`): ignores `main` function, excludes tests.
  - **pytest** (`pyproject.toml:39-40`): `addopts = "--cov=. --no-cov-on-fail --cov-fail-under=50.0"`.
  - **pip-audit**: no project configuration in `pyproject.toml`; simply invoked via `make audit`.
- **Makefile command hub** (`Makefile:1-50`):
  - `.venv` target: creates Python 3.14 virtual environment, installs dev requirements and test extras.
  - `check` (`Makefile:10`): runs `test lint mypy audit deadcode` in sequence — the primary quality gate.
  - `fix` (`Makefile:11`): runs `format fixlint`.
  - Individual targets: `format`, `lint`, `fixlint`, `mypy`, `audit`, `deadcode`, `test` — all depend on `.venv`.
  - Other targets: `publish` (`Makefile:22-25`), `compile` (`Makefile:53-55`), `sync` (`Makefile:49-51`).
- **Known gap**: `BACKLOG.md` (`BACKLOG.md:26-30`) references `just` commands such as `just check-format` and `just check`, but the present `Justfile` (`Justfile:1-4`) only defines a `lifecycle` target; those `just` commands do not work. README correctly documents `make check` / `make fix` (`README.md:15-21`), which is the actual quality gate.

## Tests

- **Test coverage**: single test function `test_show_version()` in `tests/test_main.py:7-14`.
  - Patches `ArgumentParser` and `print` via `unittest.mock.patch`.
  - Forces `version = True` on parsed args.
  - Calls `main()`.
  - Asserts `print` called once with `f'modernpackage {__version__}'`.
- **Coverage of codebase**:
  - ✓ Covered: `--version` branch only.
  - ✗ Untested: `check_alpha_numeric()` validation, `init_new_package()` cloning, package-name branch, real argument parsing.
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
  - `Makefile` — command hub (development, testing, publishing targets).
  - `Justfile` — currently defines only `lifecycle` target.
- **Dependencies**:
  - `requirements.txt` — runtime dependencies (currently empty).
  - `requirements-dev.txt` — pinned dev and test dependencies.
  - `uv.lock` — lock file for `uv`.
- **CI/CD**:
  - `.github/workflows/check-modernpackage-on-python314.yml` — GitHub Actions workflow.
  - `.gitlab-ci.yml` — GitLab CI configuration.
  - Both run `make check` as the primary gate.
- **Documentation & metadata**:
  - `README.md` — user-facing usage guide and feature-request backlog.
  - `BACKLOG.md` — task tracking.
  - `issues/` — issue directory.
  - `workspace/` — task/research artifacts.
- **Build output**:
  - `dist/` — contains `0.0.8` wheel and sdist (version older than `__init__.py:3` `0.0.9`; see Known gaps).

The architecture is self-referential: the CLI clones this very repository, then `make init` rewrites the clone to a new package name (`main.py:37-51`, `Makefile:60-75`).

## Known gaps & divergences

- **No error handling in `init_new_package()`** (`main.py:37-51`): both `Popen` calls discard output via `.communicate()[0]` with no success/failure checks. If `git clone` or `make init` fail, the user sees no error and the process silently continues.
- **Version drift** (`__init__.py:3`): source declares `__version__ = '0.0.9'`, but `dist/` contains `0.0.8` wheel and sdist. No in-repo evidence of which version is published; the discrepancy is unresolved.
- **Justfile vs. BACKLOG divergence** (`Justfile:1-4`, `BACKLOG.md:26-30`): `BACKLOG.md` references `just` commands such as `just check-format` and `just check`, but the present `Justfile` only defines a `lifecycle` target — so those `just` commands do not work. README correctly documents `make check` / `make fix` (`README.md:15-21`) as the development commands.
- **README Feature requests are aspirational** (`README.md:36-78`): the "Feature requests" section lists desired enhancements (virtualenv init, git/network checks, async tests, etc.), none of which are implemented. Notably, the documented no-network crash traceback (`README.md:57-76`) is a known failure mode, not a solved feature.
