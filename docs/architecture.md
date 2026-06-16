# modernpackage — Architecture & Design

[overview.md](overview.md)

## Package Structure

```
modernpackage/
├── __init__.py          # version constant
└── main.py              # CLI entry point, argument parsing, initialization logic

tests/
├── __init__.py          # test package marker
└── test_main.py         # test suite with comprehensive coverage

Configuration & Build:
├── pyproject.toml       # unified config hub (build, deps, tool settings)
├── Makefile             # canonical command hub
└── Justfile             # just-based command shortcuts
```

## Modules

### `modernpackage/__init__.py`

Defines the package version as a module-level constant:

```python
__version__ = '0.0.9'
```

This constant is:
- Imported by `main.py` for the `--version` output
- Read by `hatchling` (build backend) to set the wheel/sdist version dynamically

### `modernpackage/main.py`

The main CLI orchestrator (62 lines) with four functions:

#### `check_alpha_numeric(value: str) -> str`

Validates that a string contains only alphanumeric characters. Used as the `type=` validator in argument parsing.

- **Returns** the input string unchanged if valid
- **Raises** `ArgumentTypeError('Non-AlphaNumeric package name')` if the string contains non-alphanumeric characters

#### `parse_args() -> Namespace`

Parses command-line arguments using `argparse.ArgumentParser`.

- **Arguments**:
  - `-v` / `--version`: optional flag (default `False`)
  - `package_name`: optional positional argument (validated via `check_alpha_numeric`)
- **Returns** an `argparse.Namespace` object with fields `version` and `package_name`

#### `init_new_package(package_name: str) -> None`

Orchestrates the package initialization flow by cloning and rewriting:

1. Resolves target path: `Path.cwd() / package_name`
2. Spawns `git clone https://github.com/albertas/modernpackage <path>`
3. Spawns `make init <package_name>` (cwd: the cloned directory)
4. Both subprocess calls use `Popen` with `communicate()` to capture output (discarded)
5. No error handling or return value — silent on failure (current state)

The `Makefile init` target (in the cloned repo) performs the actual transformation:
- Renames all "modernpackage" occurrences to the new package name
- Resets the version to `0.0.1`
- Renames the package directory (`modernpackage/` → `<name>/`)
- Reinitializes git (clears `.git`, runs `git init`, commits initial state)

#### `main() -> None`

The CLI entry point (orchestrator):

1. Calls `parse_args()` to get user input
2. **If** `version` flag is set: prints `modernpackage <__version__>` and exits
3. **Elif** `package_name` is provided: calls `init_new_package(package_name)`
4. **Else**: silent no-op (no error, no message)

## Build & Versioning

### Build Configuration

- **Build backend**: `hatchling` (modern, minimal Python build system)
- **Package files**: includes `**/*.py`, excludes `tests/**`
- **Version source**: dynamic, read from `modernpackage/__init__.py` at build time (no hard-coded version in `pyproject.toml`)
- **Python requirement**: `>= 3.14`
- **Runtime dependencies**: none (empty list)
- **Test dependencies**: hatch, ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, vupi

### Publishing

`make publish` clears `dist/`, builds via `hatch build`, and publishes via `hatch publish`.

## Configuration Hub

### `pyproject.toml`

Single unified configuration file for all tools:

- **`[project]`**: package metadata, entry points (`modernpackage` and `mp`), optional test dependencies
- **`[tool.pytest.ini_options]`**: test runner config
  - `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0"`
  - Measures coverage against the `modernpackage` package only (excludes `tests/`)
  - Fails if coverage is below 95%
- **`[tool.ruff]`**: linter & formatter config
  - Line length: 88 characters
  - Quote style: single quotes
  - Linting: select ALL with targeted per-file ignores (ruff, docstrings, comments, type hints)
  - Tests allow `assert` and skip docstring requirements
- **`[tool.mypy]`**: type checker config
  - `strict = true` — enforces full type annotations
  - `python_version = "3.14"`
  - Color output and detailed error reporting enabled
- **`[tool.deadcode]`**: dead code scanner config
  - Ignores the `main` function (intentional entry point)
  - Excludes `tests/`
- **`[[tool.uv.index]]`**: private GitLab package index for internal dependencies

## Developer Tooling

### Command Hubs

Two command hubs provide development workflows:

#### Makefile (canonical)

The primary command hub. Targets include:

- **`.venv`**: creates Python 3.14 virtualenv, installs dev and test dependencies
- **`check`**: runs all quality gates in sequence (`test lint mypy audit deadcode`)
- **`fix`**: runs auto-fix tools (`format fixlint`)
- **`test`**: runs pytest with coverage
- **`lint`**, **`format`**, **`mypy`**, **`audit`**, **`deadcode`**: individual quality checks
- **`publish`**: builds and publishes to PyPI

All targets depend on `.venv` and use `uv run` to invoke tools in the managed virtualenv.

#### Justfile

Provides equivalent `just` targets:

- **`sync`**: syncs dependencies from requirements files
- **`test`**: runs pytest
- **`check`**: combined quality check (format, lint, complexity, typecheck, test)
- **`format`**, **`lint`**, **`typecheck`**: individual checks
- **`check-format`**, **`check-lint`**, **`check-complexity`**, **`check-typecheck`**: check-only (no auto-fix)
- **`lifecycle`**: runs `uv run lifecycle` for CI/CD integration

### Tool Coordination

All tools read their configuration from `pyproject.toml`. The Makefile and Justfile delegate to them via `uv run`, which manages the virtual environment and dependency versions (pinned in `requirements-dev.txt` and `uv.lock`).

## Test Strategy

### Test Coverage Goal

**95% coverage of `modernpackage/` source** — all code paths must be exercised with deterministic, mocked tests.

### Test Organization

Tests live in `tests/test_main.py` using:

- Plain `def test_*` functions (no test classes)
- `unittest.mock.patch` for dependency injection (mocking `ArgumentParser`, `print`, `Popen`, etc.)
- `pytest.raises` for exception testing
- No real subprocess/network calls; all external dependencies mocked

### Coverage Measurement

`pytest-cov` is configured in `pyproject.toml`:

```ini
[tool.pytest.ini_options]
addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0"
```

- `--cov=modernpackage`: measures coverage only for the package (excludes `tests/`)
- `--cov-fail-under=95.0`: test suite fails if coverage drops below 95%
- `--no-cov-on-fail`: skips coverage reporting if tests fail (speeds up failure diagnosis)

### Test Execution

```bash
just test              # run pytest with coverage
make test              # equivalent Makefile target
make check             # run all quality gates (including tests)
just check             # equivalent just target
```

## Self-Replication Flow

When a user runs `modernpackage mypackage`:

1. `main()` parses arguments and calls `init_new_package('mypackage')`
2. `init_new_package()` clones the official repo to `./mypackage`
3. The Makefile `init` target (in the clone) transforms it:
   - Renames all "modernpackage" → "mypackage"
   - Resets version to `0.0.1`
   - Reinitializes git
4. Result: a new, independent Python package ready for development

This self-replication pattern allows the package to be both a tool and a template, bootstrapping new projects with the same modern tooling setup.

## Known Gaps & Deviations

### No error handling in `init_new_package()`

Both `git clone` and `make init` subprocess calls discard output with no error checks. Failures (e.g., network errors, missing `make` command) are silent. The user sees no error message and the process continues.

**Plan**: future phases may add error handling and user feedback, but it is not in scope for the current coverage goal.

### Version drift

The source declares `__version__ = '0.0.9'`, but published wheels may differ. See `specification.md` for details.

### Justfile incompleteness

`BACKLOG.md` references `just` commands that did not exist in earlier phases. The present `Justfile` now defines all required targets, and the Makefile and Justfile are equivalent.
