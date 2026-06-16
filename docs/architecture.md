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

The main CLI orchestrator (66 lines) with four fully type-annotated functions:

#### `check_alpha_numeric(value: str) -> str`

Validates that a string contains only alphanumeric characters. Used as the `type=` validator in argument parsing.

- **Parameter**: `value: str` — the input string to validate
- **Returns**: `str` — the input string unchanged if valid
- **Raises**: `ArgumentTypeError('Non-AlphaNumeric package name')` if the string contains non-alphanumeric characters

#### `parse_args() -> Namespace`

Parses command-line arguments using `argparse.ArgumentParser`.

- **Arguments**:
  - `-v` / `--version`: optional flag (default `False`)
  - `package_name`: optional positional argument (validated via `check_alpha_numeric`)
- **Returns**: `Namespace` — an `argparse.Namespace` object with fields `version` (bool) and `package_name` (str | None)

#### `init_new_package(package_name: str) -> None`

Orchestrates the package initialization flow by cloning and rewriting:

1. **Parameter**: `package_name: str` — name of the new package to create
2. **Returns**: `None` — no return value; operates via side effects
3. **Process**:
   - Resolves target path: `Path.cwd() / package_name`
   - Spawns `git clone https://github.com/albertas/modernpackage <path>`
   - Spawns `make init <package_name>` (cwd: the cloned directory)
   - Both subprocess calls use `Popen` with `communicate()` to capture output (discarded)
   - No error handling or explicit return — silent on failure (current state)

The `Makefile init` target (in the cloned repo) performs the actual transformation:
- Renames all "modernpackage" occurrences to the new package name
- Resets the version to `0.0.1`
- Renames the package directory (`modernpackage/` → `<name>/`)
- Reinitializes git (clears `.git`, runs `git init`, commits initial state)

#### `main() -> None`

The CLI entry point (orchestrator):

- **Returns**: `None` — no return value
- **Flow**:
  1. Calls `parse_args()` to get user input
  2. **If** `version` flag is set: prints `modernpackage <__version__>` and exits
  3. **Elif** `package_name` is provided: calls `init_new_package(package_name)`
  4. **Else**: silent no-op (no error, no message)

## Type Annotations & Mypy Verification

### Full Type Coverage

All public functions in `modernpackage/main.py` carry complete type annotations:

- **`check_alpha_numeric(value: str) -> str`** — parameter and return types specified
- **`parse_args() -> Namespace`** — return type specified (no parameters)
- **`init_new_package(package_name: str) -> None`** — parameter type and return type specified
- **`main() -> None`** — return type specified (no parameters)

### Mypy Configuration

Mypy is configured in `pyproject.toml` with strict mode enabled:

```ini
[tool.mypy]
exclude = ["build", "dist", ".venv"]
python_version = "3.14"
strict = true
pretty = true
color_output = true
show_error_codes = true
warn_return_any = true
warn_unused_configs = true
```

Key settings:
- **`strict = true`** — enforces full type annotations on all functions and enforces strict type compatibility checks
- **`python_version = "3.14"`** — type checks assume Python 3.14 or later features
- **`warn_return_any = true`** — warns if any function returns an unannotated `Any` type
- **`warn_unused_configs = true`** — warns if configuration options are unused

### Verification

The strict type-checking audit is run via `just check-typecheck` (or `just typecheck` for automatic fixing):

```bash
just check-typecheck  # runs: uv run mypy modernpackage tests
```

**Current status**: ✅ **All 4 source files pass strict mypy**
- `modernpackage/__init__.py` — version constant
- `modernpackage/main.py` — CLI orchestrator with 4 functions
- `tests/__init__.py` — test package marker
- `tests/test_main.py` — comprehensive test suite

Result: `Success: no issues found in 4 source files`

This ensures all code paths are covered by type hints and comply with strict type-checking rules.

## Build & Versioning

### Build Configuration

- **Build backend**: `hatchling` (modern, minimal Python build system)
- **Package files**: includes `**/*.py`, excludes `tests/**`
- **Version source**: dynamic, read from `modernpackage/__init__.py` at build time (no hard-coded version in `pyproject.toml`)
- **Python requirement**: `>= 3.14`
- **Runtime dependencies**: none (empty list)
- **Test dependencies**: ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi (with a minimum version floor for the constrained package)

### Publishing

`make publish` clears `dist/`, builds via `uv build`, and publishes via `uv publish`.

### Dependency Compilation & Locking

The project uses two mechanisms to pin and regenerate dependencies:

1. **`requirements.txt` and `requirements-dev.txt`**: generated via `uv pip compile -U` to freeze all transitive dependencies
2. **`uv.lock`**: generated via `uv lock --upgrade` to create a uv-native lock file

Both `Makefile` and `Justfile` define a `compile` recipe that regenerates all three artifacts in lockstep:
- `uv pip compile -U -q pyproject.toml -o requirements.txt` (regenerates runtime pins; currently empty since `dependencies = []`)
- `uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt` (regenerates dev/test pins including the `test` extra)
- `uv lock --upgrade` (regenerates the native uv lock file to match the same versions)

This ensures that `requirements.txt`, `requirements-dev.txt`, and `uv.lock` always agree on shared package versions and are bumped together whenever dependencies are upgraded. The compile recipes delegate to the private GitLab uv index configured in `pyproject.toml`, which may lag behind PyPI; the resolved versions are capped by what that index serves.

## Configuration Hub

### `pyproject.toml`

Single unified configuration file for all tools:

- **`[project]`**: package metadata, entry points (`modernpackage` and `mp`), optional test dependencies
- **`[tool.pytest.ini_options]`**: test runner config
  - `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`
  - Measures coverage against the `modernpackage` package only (excludes `tests/`)
  - Fails if coverage is below 95%
  - Default run excludes `e2e` marked tests (mocked unit tests only)
  - `markers` lists registered markers: `e2e` (tests that perform real external calls)
- **`[tool.ruff]`**: linter & formatter config
  - Line length: 88 characters
  - Quote style: single quotes
  - Linting: select ALL with targeted per-file ignores (ruff, docstrings, comments, type hints)
  - Tests allow `assert` and skip docstring requirements
- **`[tool.ruff.lint.mccabe]`**: cyclomatic complexity enforcement
  - `max-complexity = 8` — enforces that no function exceeds a cyclomatic complexity of 8
  - Ruff's `C901` rule (checked via `just check-complexity`) fails on any function that exceeds this threshold
  - Ensures code remains understandable and maintainable; functions with complexity > 8 are difficult to reason about
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
- **`compile`**: upgrades and regenerates all dependency artifacts (`uv pip compile -U` for both requirements files, then `uv lock --upgrade` for the lock file)
- **`test`**: runs pytest in parallel across `nproc --ignore=1` workers with coverage (mocked unit tests only, excludes e2e)
- **`test-e2e`**: runs pytest with only `e2e` marked tests
- **`lint`**, **`format`**, **`mypy`**, **`audit`**, **`deadcode`**: individual quality checks
- **`publish`**: builds and publishes to PyPI

All targets depend on `.venv` and use the virtualenv to invoke tools (except `compile`, which runs without a venv dependency to allow regenerating pinned dependencies).

#### Justfile

Provides equivalent `just` targets:

- **`sync`**: syncs dependencies from requirements files
- **`compile`**: upgrades and regenerates all dependency artifacts (same as Makefile: `uv pip compile -U` for both requirements files, then `uv lock --upgrade` for the lock file)
- **`test`**: runs pytest in parallel across `nproc --ignore=1` workers (mocked unit tests only, excludes e2e)
- **`test-e2e`**: runs pytest with only `e2e` marked tests (overrides the default `-m 'not e2e'` behavior)
- **`check`**: combined quality check (format, lint, complexity, typecheck, test) — enforces all quality gates including complexity threshold of 8
- **`format`**, **`lint`**, **`typecheck`**: individual checks
- **`check-format`**, **`check-lint`**, **`check-complexity`**, **`check-typecheck`**: check-only (no auto-fix) — `check-complexity` fails if any function exceeds McCabe complexity of 8
- **`lifecycle`**: runs `uv run lifecycle` for CI/CD integration

### Tool Coordination

All tools read their configuration from `pyproject.toml`. The Makefile and Justfile delegate to them via `uv run`, which manages the virtual environment and dependency versions (pinned in `requirements-dev.txt` and `uv.lock`).

## Test Strategy

### Test Coverage Goal

**95% coverage of `modernpackage/` source** — all code paths must be exercised with deterministic, mocked, parallel tests.

### Parallelism & Determinism

Tests run in parallel across `nproc --ignore=1` CPU cores using `pytest-xdist`. All tests are:
- **Independent**: no shared state or ordering dependencies between tests
- **Mocked**: all external effects (subprocess, network, filesystem) are mocked at the seam
- **Deterministic**: coverage aggregates transparently across workers; final coverage measurement is deterministic despite parallel execution

### Test Organization

Tests live in `tests/test_main.py` using:

- Plain `def test_*` functions (no test classes)
- `unittest.mock.patch` for dependency injection (mocking `ArgumentParser`, `print`, `Popen`, etc.)
- `pytest.raises` for exception testing
- No real subprocess/network calls; all external dependencies mocked
- Unit tests are unmarked (default, included in `just test`)
- End-to-end tests use `@pytest.mark.e2e` (excluded from default run, included only in `just test-e2e`)

### Test Markers

The `e2e` marker is registered in `pyproject.toml` to categorize tests:

- **`e2e`**: marks tests that perform real external calls (network, subprocess, filesystem). These are excluded from the default `just test` run (which runs only mocked unit tests) and are reserved for an explicit `just test-e2e` invocation. Pre-registering the marker prevents future `filterwarnings = error` strictness from breaking on unregistered marker usage.

### Coverage Measurement

`pytest-cov` is configured in `pyproject.toml`:

```ini
[tool.pytest.ini_options]
addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"
markers = [
    "e2e: tests that perform real external calls (network/subprocess/fs)",
]
```

- `--cov=modernpackage`: measures coverage only for the package (excludes `tests/`)
- `--cov-fail-under=95.0`: test suite fails if coverage drops below 95%
- `--no-cov-on-fail`: skips coverage reporting if tests fail (speeds up failure diagnosis)
- `-m 'not e2e'`: default run excludes `e2e` marked tests (mocked unit tests only)

### Test Execution

Tests run in parallel across all-but-one CPU cores (via `nproc --ignore=1`) using `pytest-xdist`. The default run excludes `e2e` marked tests, running only mocked unit tests. Coverage is aggregated transparently across parallel workers.

```bash
just test              # run parallel unit tests (mocked, excludes e2e) with coverage
just test-e2e         # run only e2e marked tests (real external calls)
make test              # equivalent Makefile target (parallel)
make test-e2e         # equivalent Makefile target for e2e tests
make check             # run all quality gates (including parallel tests)
just check             # equivalent just target
```

On a 1-core machine, `nproc --ignore=1` yields 0; `pytest-xdist` treats `-n 0` as single-process (acceptable fallback).

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

### Justfile and Makefile alignment

Both the `Justfile` and `Makefile` now define equivalent targets with parallel test execution:
- `just test` and `make test` both run in parallel across `nproc --ignore=1` workers
- `just test-e2e` and `make test-e2e` both select only `e2e` marked tests
- Future work: `BACKLOG.md` plans to merge the Makefile into the Justfile, making `just` the canonical runner
