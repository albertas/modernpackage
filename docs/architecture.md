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
└── Justfile             # canonical command hub
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

The main CLI orchestrator with four fully type-annotated functions:

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

#### `init_new_package(package_name: str) -> int`

Orchestrates the package initialization flow by cloning, rewriting, and validating:

1. **Parameter**: `package_name: str` — name of the new package to create
2. **Returns**: `int` — exit code (0 on success, 1 if `just check` fails)
3. **Process**:
   - Resolves target path: `Path.cwd() / package_name`
   - **Step 1: Clone** — Spawns `git clone https://github.com/albertas/modernpackage <path>` via `Popen` with `stderr=PIPE`
     - Waits for completion via `communicate()` and captures both stdout and stderr
     - **If `returncode != 0`**: calls `humanize_git_clone_error(decoded stderr)` to map common failure patterns to friendly messages; raises `RuntimeError` with either:
       - `'{friendly message}\n\ngit clone failed with exit code {returncode}: {decoded stderr}'` if a known pattern is found, or
       - `'git clone failed with exit code {returncode}: {decoded stderr}'` as fallback for unknown errors
   - **Step 2: Initialize** — **If `returncode == 0`**: continues to spawn `just init <package_name>` (cwd: the cloned directory) with `stderr=PIPE`
     - Wraps the `just init` `Popen` call in a `try`/`except FileNotFoundError` block:
       - **If `FileNotFoundError` is raised**: catches the exception and raises `RuntimeError` with an actionable message: `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`
       - **If `Popen` succeeds**: waits for completion via `communicate()` and captures both stdout and stderr
         - **If `returncode != 0`**: raises `RuntimeError` with message `'just init failed with exit code {returncode}: {decoded stderr}'`
         - **If `returncode == 0`**: continues to Step 3
   - **Step 3: Validate** — **If Step 2 succeeds**: runs `just check <package_name>` (cwd: the cloned directory) via `Popen` and reports the outcome
     - Spawns the subprocess and captures both stdout and stderr via `communicate()`
     - **If `returncode == 0`**: prints a success message to stdout: `'just check passed — {package_name} scaffold is valid.'` and returns `0`
     - **If `returncode != 0`**: prints a failure message to stderr: `'just check failed with exit code {returncode} — review the output in {package_name}.'` and returns `1`
     - Does not raise an error on non-zero exit code; `just check` failure is reported but does not block the function; the failure is propagated via the return code instead

Error messages include the decoded stderr output, providing visibility into the root cause of subprocess failures (e.g., network errors, missing commands, permission issues). The `git clone` error path is enhanced with pattern-matched, human-readable explanations of common failure modes. The `just init` missing-command error path is caught at the point of spawning the subprocess, before any execution attempts, and provides a clear, actionable installation instruction.

The `just init` recipe (in the cloned repo) performs the actual transformation:
- Renames all "modernpackage" occurrences to the new package name
- Resets the version to `0.0.1`
- Renames the package directory (`modernpackage/` → `<name>/`)
- Reinitializes git (clears `.git`, runs `git init`, commits initial state)

The `just check` recipe (in the cloned repo) validates the newly scaffolded package by running all quality gates: format check, ruff lint, complexity audit, mypy type check, unit tests, pip-audit security scan, and deadcode detection.

#### `humanize_git_clone_error(stderr_text: str) -> str | None`

A pure helper function that maps common `git clone` failure patterns to human-readable, actionable messages.

- **Parameter**: `stderr_text: str` — the captured stderr output from a failed `git clone` command
- **Returns**: `str | None` — a friendly error message if a known pattern is found; `None` if no pattern matches
- **Algorithm**: iterates over an ordered list of compiled regex patterns (matched case-insensitively against the lowercased stderr) and returns the first matching message, or `None` if nothing matches

**Error patterns and friendly messages:**

| Pattern | Friendly Message |
|---------|------------------|
| `could not resolve host`, `could not read from remote`, `failed to connect`, `connection timed out`, `network is unreachable` | `repository unreachable — check your network connection` |
| `repository not found`, `remote: not found`, `does not exist` | `template repository not found — it may have moved or been removed` |
| `permission denied (publickey)`, `authentication failed`, `could not read username` | `authentication failed — check your git credentials or access rights` |
| `already exists and is not an empty directory` | `destination directory already exists — choose a different package name` |
| `permission denied`, `could not create`, `unable to create` | `cannot write to the destination directory — check filesystem permissions` |

Patterns are ordered most-specific first to avoid premature matches. The implementation maintains low cyclomatic complexity (a simple loop over the mapping).

#### `main() -> int`

The CLI entry point (orchestrator):

- **Returns**: `int` — a process exit code (0 for success, 1 for failure)
- **Flow**:
  1. Calls `parse_args()` to get user input
  2. **If** `version` flag is set: prints `modernpackage <__version__>` and returns `0`
  3. **Elif** `package_name` is provided:
     - Calls `init_new_package(package_name)` inside a `try`/`except RuntimeError` block
     - **If** `RuntimeError` is raised: catches it, prints the error message to `sys.stderr` (which includes captured stderr from the failed subprocess), and returns `1`
     - **If** no error: returns the value from `init_new_package()` (which is `0` if `just check` passed, or `1` if it failed)
  4. **Else**: silent no-op (no error, no message) and returns `0`

The error handling ensures that subprocess failures (from `git clone` or `just init`) are surfaced to the user as clean, readable messages on stderr instead of Python tracebacks. The returned exit code is translated to the process exit status by the console script wrapper (which calls `sys.exit(main())`), allowing shell scripts and CI/CD pipelines to detect failures properly. Validation failures (from `just check`) are now also reflected in the process exit code.

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

`just publish` clears `dist/`, builds via `uv build`, and publishes via `uv publish`.

### Dependency Compilation & Locking

The project uses two mechanisms to pin and regenerate dependencies:

1. **`requirements.txt` and `requirements-dev.txt`**: generated via `uv pip compile -U` to freeze all transitive dependencies
2. **`uv.lock`**: generated via `uv lock --upgrade` to create a uv-native lock file

The `Justfile` defines a `compile` recipe that regenerates all three artifacts in lockstep:
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

### Command Hub

The `Justfile` is the canonical command hub providing development workflows via `just` recipes:

- **`sync`**: syncs dependencies from requirements files (required by most recipes as a prerequisite)
- **`compile`**: upgrades and regenerates all dependency artifacts (`uv pip compile -U` for both requirements files, then `uv lock --upgrade` for the lock file)
- **`test`**: runs pytest in parallel across `nproc --ignore=1` workers with coverage (mocked unit tests only, excludes e2e)
- **`test-e2e`**: runs pytest with only `e2e` marked tests (overrides the default `-m 'not e2e'` behavior)
- **`check`**: combined quality gate (format, lint, complexity, typecheck, test, audit, deadcode) — enforces all quality gates including complexity threshold of 8
- **`fix`**: auto-fix tools (format, then fix-lint)
- **`fix-lint`**: auto-fix linting and deadcode issues
- **`format`**, **`lint`**, **`typecheck`**, **`audit`**, **`deadcode`**: individual tools
- **`check-format`**, **`check-lint`**, **`check-complexity`**, **`check-typecheck`**: check-only variants (no auto-fix) — `check-complexity` fails if any function exceeds McCabe complexity of 8
- **`publish`**: builds and publishes to PyPI (no `sync` prerequisite; build does not require the editable install)
- **`init`**: self-replication recipe with named parameter `package_name` (default: `"modernpackage"`)

### Tool Coordination

All tools read their configuration from `pyproject.toml`. The Justfile delegates to them via `uv run`, which manages the virtual environment and dependency versions (pinned in `requirements-dev.txt` and `uv.lock`).

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
just check             # run all quality gates (including parallel tests)
```

On a 1-core machine, `nproc --ignore=1` yields 0; `pytest-xdist` treats `-n 0` as single-process (acceptable fallback).

## Self-Replication Flow

When a user runs `modernpackage mypackage`:

1. `main()` parses arguments and calls `init_new_package('mypackage')`
2. `init_new_package()` clones the official repo to `./mypackage`, capturing stderr for detailed error reporting
3. On successful clone, the `just init` recipe (in the clone) transforms it:
   - Renames all "modernpackage" → "mypackage"
   - Resets version to `0.0.1`
   - Reinitializes git
4. On successful initialization, `just check` is run to validate the newly scaffolded package against all quality gates (formatting, linting, complexity, type checking, tests, security audit, dead code detection)
5. Result: a new, independent Python package ready for development

This self-replication pattern allows the package to be both a tool and a template, bootstrapping new projects with the same modern tooling setup. The clone, initialization, and validation steps report detailed error output if they fail, making it easy to diagnose issues (network errors, missing dependencies, permission problems, etc.).

## Known Gaps & Deviations

### Error handling in `init_new_package()`

Both the `git clone` and `just init` subprocess calls capture stderr and include it in error messages:

**Git clone step**: Both stdout and stderr are captured via `Popen(..., stderr=PIPE)` and `communicate()`, which returns a `(stdout, stderr)` tuple. If the return code is non-zero (indicating failure), a `RuntimeError` is raised with the message `'git clone failed with exit code {returncode}: {stderr}'`. The decoded stderr output provides visibility into the root cause (e.g., network errors, invalid URLs, authentication failures). This prevents the function from continuing to the `just init` step when cloning fails.

**Just init step**: The `Popen` call for `just init` is wrapped in a `try`/`except FileNotFoundError` block to detect when the `just` command is not installed. If `FileNotFoundError` is raised (indicating the executable cannot be found), a `RuntimeError` is raised with an actionable message: `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`. This check occurs before subprocess execution, providing immediate feedback to the user.

If the `Popen` call succeeds but the subprocess exits with a non-zero return code, a `RuntimeError` is raised with the message `'just init failed with exit code {returncode}: {stderr}'`. The decoded stderr output provides visibility into the root cause (e.g., rewrite errors, git failures within the init script). A failed `just init` leaves the cloned directory in an incomplete state, so the error is caught and reported immediately rather than silently continuing.

### Version drift

The source declares `__version__ = '0.0.9'`, but published wheels may differ. See `specification.md` for details.

### Justfile command surface

The `Justfile` provides a comprehensive command surface for all development, testing, and publishing workflows:
- **`just test`** and **`just test-e2e`** run in parallel across `nproc --ignore=1` workers with full test discovery and coverage measurement
- **`just check`** enforces the full gate (format, lint, complexity, typecheck, test, audit, deadcode) as the primary quality gate
- **`just fix`** auto-fixes all correctable violations (format + lint + deadcode)
- **`just publish`** builds and publishes to PyPI; **`just compile`** upgrades all locked dependencies
- **`just init <name>`** replicates the package with a new name (named parameter, default `"modernpackage"`)
