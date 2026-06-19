# modernpackage — CLI Invocation

[overview.md](overview.md)

## Entry Points

`modernpackage` defines two console script entry points in `pyproject.toml`:
- `modernpackage` — full name entry point
- `mp` — alias for quick invocation

Both route to `modernpackage.main:main()`, so they are functionally identical.

## Command-Line Interface

### Exit Codes

`modernpackage` returns exit codes as follows:
- **Exit code 0**: successful operation (version printed, package initialized with all quality gates passing, or no arguments provided)
- **Exit code 1**: failure in package initialization (git clone, just init, or just check failed)

The exit code is reflected in the process exit status, allowing shell scripts and CI/CD pipelines to detect failures. Importantly, failures of the validation step (`just check`) now result in exit code 1, allowing automated tools to detect when the scaffolded package does not meet quality standards.

### No arguments (no-op)

```bash
modernpackage
```

Calls `main()` with no arguments. If neither `--version` nor a package name is provided, the function exits silently with no action and exit code 0.

### Version flag

```bash
modernpackage --version
modernpackage -v
```

Prints the installed version of `modernpackage` and exits with exit code 0:
```
modernpackage <version>
```

The version is read from `modernpackage/__version__` at runtime.

### Dry-run flag

```bash
modernpackage <package_name> --dry-run
modernpackage <package_name> --dry-run --author-name "Ada Lovelace" --description "My package"
modernpackage <package_name> --dry-run --backend
```

Previews what scaffolding would do without making any changes. Runs preflight checks (same as a normal run), then exits cleanly with exit code 0 and prints a high-level plan showing:
- The target directory that would be created
- The template URL that would be cloned
- Per-field metadata substitutions (fields with values, fields keeping the template default)
- The well-known `just init` outcomes (rename `modernpackage/ → <module>/`, version reset to `0.0.1`)
- Whether the FastAPI backend would be injected (if `--backend` is set)

No directory is created, no clone occurs, no subprocess is spawned beyond preflight.

**Example: Dry-run with metadata**

```bash
modernpackage my-package --dry-run --author-name "Ada Lovelace" --description "A cool package"
```

**Output (stdout):**
```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [ok]   target directory available
  [ok]   template remote reachable
Dry run — no changes will be made:
  clone https://github.com/albertas/modernpackage into /home/user/my_package
  update pyproject.toml metadata:
    author name: Ada Lovelace
    author email: keeps template default
    description: A cool package
    license: keeps template default
    repository URL: keeps template default
  run just init: rename modernpackage/ -> my_package/
  run just init: reset version to 0.0.1
```

**Example: Dry-run with backend**

```bash
modernpackage my-service --dry-run --backend
```

**Output (stdout):**
```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [ok]   target directory available
  [ok]   template remote reachable
Dry run — no changes will be made:
  clone https://github.com/albertas/modernpackage into /home/user/my_service
  update pyproject.toml metadata:
    author name: keeps template default
    author email: keeps template default
    description: keeps template default
    license: keeps template default
    repository URL: keeps template default
  add FastAPI backend (app, migrations, container, recipes)
  run just init: rename modernpackage/ -> my_service/
  run just init: reset version to 0.0.1
```

**Exit code:** 0

**Important**: The dry-run still performs preflight checks (including a network probe to verify the template repository is reachable). If preflight fails, the dry-run returns exit code 1 and no plan is printed.

### Backend flag

```bash
modernpackage <package_name> --backend
modernpackage <package_name> --fastapi            # alias for --backend
modernpackage <package_name> --backend --author-name "Ada" --description "My service"
```

Scaffolds a FastAPI-based async web service with database, migrations, and containerization. When `--backend` (or its alias `--fastapi`) is provided, the scaffolder injects a complete backend template containing:

- **FastAPI application factory** with lifespan engine/sessionmaker management
- **Async SQLAlchemy 2.0 + asyncpg** for async database operations (PostgreSQL)
- **Dependency injection** for session management with Annotated types
- **Health probes**: `/livez` (liveness, no DB required) and `/readyz` (readiness, checks DB connectivity)
- **Alembic async migrations** with auto-migration support (`just migrate`, `just makemigration`, `just migration-check`)
- **Containerization**: multi-stage `Containerfile` and `compose.yml` with PostgreSQL service, automatic migration gating, and health checks
- **Complete test suite** covering the backend modules with ≥95% coverage (satisfies generated `just check`)

The generated package includes all backend dependencies (`fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `uvicorn`) in `[project.dependencies]` and `httpx` in the dev group (required by FastAPI's `TestClient`).

**Without the flag**, output is **byte-for-byte identical** to today's scaffold (no backend is injected, no extra dependencies added).

**Example: Scaffold with backend**

```bash
modernpackage my-service --backend
```

The generated package directory structure includes:

```
my_service/
├── my_service/
│   ├── __init__.py
│   ├── app.py              # FastAPI app factory with lifespan
│   ├── db.py               # Async engine and session management
│   └── health.py           # Health probe routes
├── tests/
│   └── test_app.py         # Backend tests (≥95% coverage)
├── migrations/
│   ├── env.py              # Alembic async environment
│   ├── script.py.mako      # Migration template
│   └── versions/            # Auto-generated migrations
├── alembic.ini             # Alembic configuration
├── Containerfile           # Multi-stage Docker build
├── compose.yml             # Docker Compose stack (app + Postgres + migrations)
├── .dockerignore            # Container build exclusions
├── Justfile                # Includes migrate, makemigration, migration-check
├── pyproject.toml          # Backend deps: fastapi, sqlalchemy, asyncpg, alembic, uvicorn
└── README.md
```

**Development workflow with backend:**

```bash
cd my_service
just check              # Full validation including backend tests
just migrate            # Run pending Alembic migrations
just makemigration "add users table"  # Generate migration
docker compose up       # Start app + Postgres + migration job
```

### Package initialization

```bash
modernpackage <package_name>
mp <name>
```

Initializes a new Python package with the given name in the current directory. The `package_name` argument is validated to be a valid PEP 508 / PyPI distribution name:
- Must start and end with an alphanumeric character (a-z, A-Z, 0-9)
- May contain hyphens (`-`), underscores (`_`), and dots (`.`) in between
- Validation is case-insensitive
- The normalized module name (after converting hyphens and dots to underscores) must not collide with a Python standard-library module name

If the name does not match the PEP 508 pattern, an error is raised with a specific reason:

**Empty name:**
```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Invalid package name: '' — name must not be empty
```

**Leading or trailing separator:**
```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Invalid package name: '-bad' — name must start and end with a letter or digit
```

**Disallowed character:**
```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Invalid package name: 'has space' — name contains a disallowed character: ' ' (only letters, digits, '.', '_', '-' are allowed)
```

If the name's normalized form collides with a Python standard-library module, an error is raised:

```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Package name 'json' collides with the Python standard-library module 'json'
```

Examples of valid names: `mypackage`, `my-package`, `my_package`, `my.package`, `a`, `my-json`, `jsonschema`, `email_utils`
Examples of invalid names: `-bad`, `bad-`, `has space`, empty string, `json`, `os`, `email`

**Important**: The provided `package_name` may contain hyphens and dots (e.g., `my-cool.package`), but the created directory will use underscores instead (e.g., `my_cool_package`). This normalization ensures that the directory name and all import paths are valid Python identifiers. For example:

```bash
modernpackage my-cool.package    # valid PEP 508 distribution name
# Creates a directory named: my_cool_package
# All Python imports use: from my_cool_package import ...
```

#### Success path

Upon success, a new directory is created in the current working directory containing a complete, ready-to-use Python package. The directory name is derived from the provided package name by replacing hyphens and dots with underscores (ensuring a valid Python module identifier).

**Example**: When you run `modernpackage my-cool.package`, a directory named `my_cool_package` is created (not `my-cool.package`).

The created directory contains:
- All source files cloned from `https://github.com/albertas/modernpackage`
- All occurrences of "modernpackage" renamed to the derived module name (e.g., "my_cool_package")
- Version reset to `0.0.1`
- Git repository reinitialized
- Quality validation run via `just check` to verify the scaffolded package passes all quality gates (formatting, linting, complexity, type checking, tests, security audit, dead code detection)

After all steps complete, the outcome of `just check` is reported and the exit code reflects the result:
- **If `just check` passes** (all quality gates succeed), a success message followed by a summary block and next steps hint are printed to stdout and exit code 0 is returned:
  ```
  just check passed — <module_name> scaffold is valid.
  Created package:
    package name: <package_name>
    path: <created_path>
    version: 0.0.1
  Next steps:
    cd <module_name> && just check
  ```
  Exit code: 0
  (where `<module_name>` is the normalized directory name with underscores, `<package_name>` is the validated distribution name, and `<created_path>` is the absolute path to the created directory)
  
- **If `just check` fails** (any quality gate fails), a message is printed to stderr and exit code 1 is returned:
  ```
  just check failed with exit code <code> — review the output in <module_name>.
  ```
  Exit code: 1
  (where `<module_name>` is the normalized directory name with underscores)

The package directory is created in both cases; validation failure is reported but does not prevent the package from being created (allowing the user to review and fix issues in the newly created directory). However, the exit code now reflects the validation outcome, allowing CI/CD pipelines and automated tools to detect when the scaffolded package does not meet quality standards.

#### Preflight checks and checklist

Before any subprocess is spawned or any directory is created, `init_new_package()` performs a series of preflight checks and prints a concise checklist to stdout showing each check's outcome.

The checklist is printed to **stdout** (informational output) with one line per check and status markers (`[ok]` or `[FAIL]`). If any check fails, the checklist is printed up to and including the failing check, and the error details are printed to **stderr**. This separation of streams keeps the checklist visible while error details stay distinct.

##### Preflight Checklist Output (Happy Path)

When all checks pass, the full checklist is printed to stdout:

```bash
modernpackage my-package
```

**Output:**
```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [ok]   target directory available
  [ok]   template remote reachable
```

Scaffolding then proceeds to clone, initialize, and validate the package.

##### Check Details

The checklist includes four checks run in order:

1. **Package name valid** — display-only check confirming the package name passed PEP 508 validation (already validated at argparse time, so never fails at this point)
2. **Required tools on PATH** — verifies that all required tools (`git`, `just`, `uv`) are available on `PATH` via `shutil.which()`
3. **Target directory available** — verifies that the target package directory does not already exist (file or directory)
4. **Template remote reachable** — verifies that the template repository is reachable via a `git ls-remote` probe with a 10-second timeout

##### Preflight Checklist Output (Failure Path)

When a check fails, the checklist is printed up to and including the failing check (marked `[FAIL]`), and scaffolding aborts before any clone or filesystem operation.

**Example: Missing git tool**

```bash
modernpackage my-package
```

**Output (stdout):**
```
Preflight checks:
  [ok]   package name valid
  [FAIL] required tools on PATH (git, just, uv)
```

**Output (stderr):**
```
required tool(s) not found on PATH: git — install the missing tool(s) before scaffolding:
  - git: https://git-scm.com/downloads
```

**Exit code:** 1

**Example: Target directory exists**

```bash
mkdir my-package
modernpackage my-package
```

**Output (stdout):**
```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [FAIL] target directory available
```

**Output (stderr):**
```
target directory already exists: /home/user/my_package — choose a different package name or remove the existing directory
```

**Exit code:** 1

**Important**: The target directory name is derived by normalizing the package name (replacing hyphens and dots with underscores). For example, `my-cool.package` becomes `my_cool_package`. This check verifies that a directory with this normalized name does not exist before attempting to clone.

**Example: Template remote unreachable**

```bash
modernpackage my-package
```

**Output (stdout):**
```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [ok]   target directory available
  [FAIL] template remote reachable
```

**Output (stderr):**
```
repository unreachable — check your network connection

template remote unreachable (git ls-remote exit code 2): fatal: Could not resolve host: github.com
```

**Exit code:** 1

These preflight checks ensure that scaffolding fails fast and clearly when requirements are not met, with a visible checklist showing exactly which checks passed and which failed, preventing confusing late failures or incomplete clones.

#### Failure path

If the `git clone` step fails (e.g., due to network errors, invalid URL, or repository not found), the error is caught in `main()` and printed to stderr with exit code 1. This occurs only after the preflight check has passed, so the required tools are guaranteed to be present.

For common failure modes, a friendly, actionable message is displayed first, followed by the raw stderr for diagnostics:

```
<friendly message>

git clone failed with exit code <code>: <stderr output>
```

**Common failure messages:**

- **Network unreachable**: 
  ```
  repository unreachable — check your network connection

  git clone failed with exit code 1: fatal: unable to access 'https://github.com/albertas/modernpackage/': Could not resolve host: github.com
  ```

- **Repository not found**:
  ```
  template repository not found — it may have moved or been removed

  git clone failed with exit code 1: fatal: repository 'https://github.com/albertas/modernpackage' not found
  ```

- **Authentication failed**:
  ```
  authentication failed — check your git credentials or access rights

  git clone failed with exit code 1: fatal: could not read Username for 'https://github.com': terminal prompts disabled
  ```

- **Destination directory exists**:
  ```
  destination directory already exists — choose a different package name

  git clone failed with exit code 128: fatal: destination path already exists and is not an empty directory.
  ```

- **Filesystem permission denied**:
  ```
  cannot write to the destination directory — check filesystem permissions

  git clone failed with exit code 1: fatal: could not create work tree dir 'mypackage': Permission denied
  ```

For unknown errors (patterns that don't match any friendly message), the raw error output is displayed:

```
git clone failed with exit code <code>: <stderr output>
```

The command exits without creating the target directory when `git clone` fails.

If the `just init` step fails after cloning completes (e.g., due to missing `just` command, rewrite errors, or other failures), the error is caught in `main()` and printed to stderr with exit code 1:

```
just init failed with exit code <code>: <stderr output>
```

The error message includes the captured stderr output from the failed `just init` command. The command exits with exit code 1 and the `<package_name>` directory is left in an incomplete state (the cloned files are present, but the transformation to the new package name was not completed).

If the `just` command is not installed (detected at subprocess spawn time before `just init` execution), the error is caught in `init_new_package()` and raised as a `RuntimeError`, which is caught in `main()` and printed to stderr with exit code 1:

```
'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation
```

The command exits with exit code 1 and the `<package_name>` directory is left in the incomplete state from the successful `git clone`.

All errors are printed to `sys.stderr` as clean messages, without a Python traceback, making error diagnosis straightforward for end users.

## End-to-End Testing

### Running the End-to-End Test

The package includes an end-to-end test that validates the scaffolding workflow by cloning the local template, running `just init`, and verifying the scaffolded package passes `just check`. This test is excluded from the default `just check` run because it requires network access and several minutes to complete.

To run the e2e test explicitly:

```bash
just test-e2e
```

This command runs only the test marked `@pytest.mark.e2e` in `tests/test_e2e.py`.

### Test Requirements & Graceful Skipping

The e2e test gracefully skips if the required tools are not available on `PATH`:
- `git` — version control system
- `just` — command runner / task automation
- `uv` — Python package manager and virtual environment tool

If any tool is missing, the test skips with a diagnostic message instead of failing. This allows developers to run the test on machines that have the tools (e.g., for final validation) and skip gracefully on machines that don't.

**Note on git config in e2e**: The e2e test sets git author/committer identity via environment variables (`GIT_AUTHOR_NAME`, `GIT_COMMITTER_NAME`, etc.), not via `git config`. These environment variables do not populate `git config user.*` keys, so the git config fallback is not exercised by the e2e test. This is intentional — the e2e test exercises the git clone and init workflow, while unit tests verify the git config fallback behavior in isolation via mocked git calls.

### Test Duration & Network Requirements

The e2e test takes several minutes to complete because the inner `just check` runs:
- `uv sync` — downloads and installs dependencies from PyPI and the internal GitLab index
- `pip-audit` — queries the vulnerability database over the network
- Full unit test suite with coverage measurement

The test requires network connectivity; offline environments fail at the `uv sync` step.

### What the Test Verifies

The test scaffolds a package from the local template and validates:
1. `git clone` succeeds and produces a copy of the template
2. `just init <package_name>` succeeds and renames all "modernpackage" occurrences to the new name
3. The renamed `__init__.py` exists and contains the version `0.0.1`
4. `just check` passes, meaning the scaffolded package satisfies all quality gates (formatting, linting, complexity, type checking, unit tests, security audit, dead code detection)

### Test Outcome

- **Pass**: The scaffolded package is valid and passes all quality gates. Exit code 0.
- **Skip**: Required tools are missing from `PATH` (e.g., `just` not installed). Exit code 0, but the test report shows `1 skipped`. This is an honest outcome on machines without the required tools.
- **Fail**: The scaffolding process failed or the scaffolded package does not pass `just check`. Exit code 1. This indicates a regression in the local template.

## Metadata Defaults Resolution

When any of the five metadata flags are omitted, `parse_args()` consults defaults in a specific precedence order. For `author_name` and `author_email`, the fallback chain is **flag > env > git config > config file > None**. For other fields, it is **flag > env > config file > None** (no git config fallback).

| Flag | Environment Variable | Git Config Key | Config File Key | Fallback Chain |
|------|----------------------|---|---|---|
| `--author-name` | `MODERNPACKAGE_AUTHOR_NAME` | `user.name` | `author_name` | env → git config → config file → None |
| `--author-email` | `MODERNPACKAGE_AUTHOR_EMAIL` | `user.email` | `author_email` | env → git config → config file → None |
| `--description` | `MODERNPACKAGE_DESCRIPTION` | (none) | `description` | env → config file → None |
| `--license` | `MODERNPACKAGE_LICENSE` | (none) | `license` | env → config file → None |
| `--repository-url` | `MODERNPACKAGE_REPOSITORY_URL` | (none) | `repository_url` | env → config file → None |

**Precedence**: Command-line flags take precedence over all other sources. If a flag is provided, all fallback sources are ignored.

**Environment variable fallback**: When a flag is omitted, the corresponding environment variable is consulted. If the environment variable is unset or empty, the next fallback source is consulted.

**Git config fallback** (for `author_name` and `author_email` only): When both a flag and its environment variable are absent (or empty), the user's git config is consulted via `git config user.name` (or `user.email`). The git config is read as the user's effective configuration (merged local-over-global, the same way `git commit` would resolve it). If git is not installed, the key is unset, or the command fails, the fallback continues to the config file (or returns `None` for author-only fields).

**Config file fallback**: When flag, environment variable, and (for author fields) git config are all absent or empty, the per-user TOML config file is consulted. The file is located at `$XDG_CONFIG_HOME/modernpackage/config.toml` (or `~/.config/modernpackage/config.toml` if `$XDG_CONFIG_HOME` is unset or empty). The file uses flat TOML keys (`author_name`, `author_email`, `description`, `license`, `repository_url`). A value is treated as set only if it is a non-empty string; empty strings and non-string TOML values (int, bool, array, table) are treated as unset. A missing config file is expected and emits no notice. A malformed or unreadable config file prints a notice to stderr (naming the file path and error) and the fallback continues to `None`.

**Empty environment variables**: An environment variable that is set to an empty string (`export MODERNPACKAGE_LICENSE=`) is treated as unset and allows the next fallback source (git config for author fields, config file for all fields, or `None` if no other source is set) to be consulted.

**Validation**: Email and URL values are validated regardless of their source (flag, env var, git config, or config file). Invalid values cause the command to exit with code 2 and a clean error message (no traceback).

### Metadata Defaults Examples

```bash
# Use env vars for all metadata
export MODERNPACKAGE_AUTHOR_NAME="Ada Lovelace"
export MODERNPACKAGE_AUTHOR_EMAIL="ada@example.com"
export MODERNPACKAGE_DESCRIPTION="A cool package"
export MODERNPACKAGE_LICENSE="MIT"
export MODERNPACKAGE_REPOSITORY_URL="https://github.com/example/my-package"
modernpackage my-package      # uses all five env defaults

# Override one env var with a flag
export MODERNPACKAGE_AUTHOR_NAME="Ada Lovelace"
modernpackage my-package --author-name "Babbage"    # flag wins; uses "Babbage"

# Valid env email flows through
export MODERNPACKAGE_AUTHOR_EMAIL="a@b.co"
modernpackage my-package      # uses "a@b.co"

# Invalid env email exits cleanly with code 2 (no traceback)
export MODERNPACKAGE_AUTHOR_EMAIL="nope"
modernpackage my-package      # Error: Invalid author email: 'nope' — expected name@domain.tld
echo $?                        # Exit code: 2

# Empty env var is treated as unset
export MODERNPACKAGE_DESCRIPTION=""
modernpackage my-package --description "From flag"   # uses "From flag" (empty env ignored)
modernpackage my-package                             # no description (None)

# Git config fallback (flag and env both absent/empty)
unset MODERNPACKAGE_AUTHOR_NAME
unset MODERNPACKAGE_AUTHOR_EMAIL
git config user.name "Ada Lovelace"
git config user.email "ada@example.com"
modernpackage my-package      # author_name and author_email come from git config

# Precedence: flag > env > git config > None
export MODERNPACKAGE_AUTHOR_NAME="Env Name"
git config user.name "Git Name"
modernpackage my-package --author-name "Flag Name"  # uses "Flag Name" (flag wins)
modernpackage my-package                            # uses "Env Name" (env beats git config)

# Config file fallback (flag, env, and git config all absent/empty)
mkdir -p ~/.config/modernpackage
cat > ~/.config/modernpackage/config.toml << EOF
author_name = "Ada Lovelace"
author_email = "ada@example.com"
description = "From config file"
license = "MIT"
repository_url = "https://github.com/example/my-package"
EOF
unset MODERNPACKAGE_AUTHOR_NAME
unset MODERNPACKAGE_AUTHOR_EMAIL
unset MODERNPACKAGE_DESCRIPTION
git config --global --unset user.name 2>/dev/null || true
git config --local --unset user.name 2>/dev/null || true
modernpackage my-package      # uses all values from config file

# Precedence: flag > env > git config > config file > None
git config user.name "Git Name"
export MODERNPACKAGE_AUTHOR_EMAIL="env@example.com"
modernpackage my-package --author-name "Flag Name" \
  # author_name="Flag Name" (flag wins)
  # author_email="env@example.com" (env beats git config and config file)
  # description="From config file" (config file used when env/git absent)

# All sources absent
rm ~/.config/modernpackage/config.toml
unset MODERNPACKAGE_AUTHOR_NAME
unset MODERNPACKAGE_AUTHOR_EMAIL
git config --global --unset user.name 2>/dev/null || true
git config --local --unset user.name 2>/dev/null || true
modernpackage my-package      # author_name and author_email are None

# Config file email is validated (must be valid format)
cat > ~/.config/modernpackage/config.toml << EOF
author_email = "not-an-email"
EOF
unset MODERNPACKAGE_AUTHOR_EMAIL
git config --global --unset user.email 2>/dev/null || true
git config --local --unset user.email 2>/dev/null || true
modernpackage my-package      # Error: Invalid author email: 'not-an-email' — expected name@domain.tld
echo $?                        # Exit code: 2

# Malformed config file (prints notice to stderr, continues with next source)
cat > ~/.config/modernpackage/config.toml << EOF
this is = not valid toml =
EOF
unset MODERNPACKAGE_DESCRIPTION
export MODERNPACKAGE_DESCRIPTION="From env"
modernpackage my-package      # stderr: "Ignoring unreadable config file …"
                              # description="From env" (env used after config file error)
```

## Argument Parser

The CLI uses `argparse.ArgumentParser` with the following configuration:

- **`-v` / `--version`**: optional flag, `action='store_true'`, default `False` — prints package version
- **`package_name`**: optional positional argument, `nargs='?'`, validated via `type=validate_package_name()` — name of package to initialize (must be a valid PEP 508 / PyPI distribution name)
- **`--author-name`**: optional flag, default `None` — author name to record in the new package (free string, no validation). If omitted, falls back to `$MODERNPACKAGE_AUTHOR_NAME`.
- **`--author-email`**: optional flag, default `None`, validated via `type=validate_author_email()` — author email to record in the new package (must be a basic email shape: `name@domain.tld`). If omitted, falls back to `$MODERNPACKAGE_AUTHOR_EMAIL`.
- **`--description`**: optional flag, default `None` — short description of the new package (free string, no validation). If omitted, falls back to `$MODERNPACKAGE_DESCRIPTION`.
- **`--license`**: optional flag, default `None` — license identifier for the new package (free string, no validation). If omitted, falls back to `$MODERNPACKAGE_LICENSE`.
- **`--repository-url`**: optional flag, default `None`, validated via `type=validate_repository_url()` — repository URL to record in the new package (must be an `http(s)://` URL). If omitted, falls back to `$MODERNPACKAGE_REPOSITORY_URL`.

The parser is created and invoked in `parse_args()`, which returns an `argparse.Namespace` object with type-annotated fields:
- `version: bool` — whether the `--version` flag was provided
- `package_name: str | None` — the package name (if provided), or `None` if omitted
- `author_name: str | None` — author name (from flag, environment variable `$MODERNPACKAGE_AUTHOR_NAME`, or `None`)
- `author_email: str | None` — author email (from flag, environment variable `$MODERNPACKAGE_AUTHOR_EMAIL`, or `None`)
- `description: str | None` — package description (from flag, environment variable `$MODERNPACKAGE_DESCRIPTION`, or `None`)
- `license: str | None` — license identifier (from flag, environment variable `$MODERNPACKAGE_LICENSE`, or `None`)
- `repository_url: str | None` — repository URL (from flag, environment variable `$MODERNPACKAGE_REPOSITORY_URL`, or `None`)

### Type Safety

The `parse_args()` function is fully type-annotated (`def parse_args() -> Namespace`) and verified by mypy in strict mode. All argument validation and type checking is enforced at parse time.

### Metadata Flags Examples

```bash
# Create a package with author information
modernpackage my-package --author-name "Ada Lovelace" --author-email "ada@example.com"

# Create a package with full metadata
modernpackage my-package \
  --author-name "Ada Lovelace" \
  --author-email "ada@example.com" \
  --description "A cool package" \
  --license "MIT" \
  --repository-url "https://github.com/example/my-package"

# Invalid email (missing domain)
modernpackage my-package --author-email "not-an-email"
# Error: Invalid author email: 'not-an-email' — expected name@domain.tld
# Exit code: 2 (argument validation error, no scaffolding occurs)

# Invalid URL (missing http(s) scheme)
modernpackage my-package --repository-url "github.com/example/repo"
# Error: Invalid repository URL: 'github.com/example/repo' — expected http(s)://…
# Exit code: 2 (argument validation error, no scaffolding occurs)

# Valid URLs (with schemes)
modernpackage my-package --repository-url "https://github.com/example/repo"
modernpackage my-package --repository-url "http://example.com/repo"
```

**Note**: The metadata flags are optional and default to `None`. Each resolved (non-`None`) value is written into the new package's `pyproject.toml` by `_write_package_metadata` after the template is cloned and before `just init`, so the metadata lands in the first commit. A field left `None` leaves its template placeholder untouched.

## Validation

**`validate_package_name(value)`** validates that a string is a valid PEP 508 / PyPI distribution name:

- Input: a string (typically the package name)
- Output: the input string unchanged if valid
- Error: raises `argparse.ArgumentTypeError` with a specific reason if the string does not match the PEP 508 pattern

The validation pattern matches:
- A single alphanumeric character (e.g., `'a'`)
- Or an alphanumeric character followed by any number of alphanumeric characters, hyphens, underscores, or dots, followed by an alphanumeric character (e.g., `'my-package'`, `'my_package'`, `'my.package'`)

When validation fails, the error message identifies the specific reason (checked in precedence order: empty → disallowed character → leading/trailing separator):

Examples:
- `validate_package_name('mypackage')` → `'mypackage'` ✓
- `validate_package_name('MyPackage123')` → `'MyPackage123'` ✓
- `validate_package_name('my-package')` → `'my-package'` ✓
- `validate_package_name('my_package')` → `'my_package'` ✓
- `validate_package_name('my.package')` → `'my.package'` ✓
- `validate_package_name('a')` → `'a'` ✓
- `validate_package_name('')` → raises `ArgumentTypeError('Invalid package name: '' — name must not be empty')`
- `validate_package_name('-bad')` → raises `ArgumentTypeError("Invalid package name: '-bad' — name must start and end with a letter or digit")`
- `validate_package_name('bad-')` → raises `ArgumentTypeError("Invalid package name: 'bad-' — name must start and end with a letter or digit")`
- `validate_package_name('has space')` → raises `ArgumentTypeError("Invalid package name: 'has space' — name contains a disallowed character: ' ' (only letters, digits, '.', '_', '-' are allowed)")`
