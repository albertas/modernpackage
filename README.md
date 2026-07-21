# modernpackage

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset.

## Usage

Install and run:
```bash
pip install modernpackage
modernpackage <your-package-name>     # or `mp <your-package-name>`
                                       # validates the name (rejects stdlib collisions before scaffolding)
                                       # clones the template and removes scaffolder machinery
                                       # creates a clean new package and validates it with just check
                                       # prints "just check passed" with a summary block, or "just check failed"

# With the optional --backend flag, generates a FastAPI async service:
modernpackage <your-service-name> --backend    # includes app, async DB, migrations, containers

# Example: Success summary (on success)
modernpackage my-package

# Output (on a TTY; passed and valid render in green):
# Running just check in my_package (this can take a while)…
# (just check output)
# just check passed — my_package scaffold is valid.
#
# Created package:
#   package name: my-package
#   path: /home/user/my_package
#   version: 0.0.1
#
# Next steps:
#   cd my_package && just check

# Example: Preview what scaffolding would do without making changes
modernpackage my-package --dry-run

# Output:
# Dry run — no changes will be made:
#   clone https://github.com/albertas/modernpackage into /home/user/my_package
#   update pyproject.toml metadata:
#     author name: keeps template default
#     author email: keeps template default
#     description: keeps template default
#     license: keeps template default
#     repository URL: keeps template default
#   run just init: rename modernpackage/ -> my_package/
#   run just init: reset version to 0.0.1
# Exit code 0

# Example: Dry-run with metadata
modernpackage my-package --dry-run --author-name "Ada Lovelace" --description "A cool package"

# Output:
# Dry run — no changes will be made:
#   clone https://github.com/albertas/modernpackage into /home/user/my_package
#   update pyproject.toml metadata:
#     author name: Ada Lovelace
#     author email: keeps template default
#     description: A cool package
#     license: keeps template default
#     repository URL: keeps template default
#   run just init: rename modernpackage/ -> my_package/
#   run just init: reset version to 0.0.1
# Exit code 0

# Example: Create a package with a name containing hyphens and dots
modernpackage my-cool.package           # Valid PEP 508 distribution name
                                        # Creates directory: my_cool_package
                                        # All Python imports: from my_cool_package import ...

# Example: Create a FastAPI backend service
modernpackage my-service --backend      # or `--fastapi` (alias)
                                        # Scaffolds a complete async FastAPI service
                                        # Includes: app factory, async SQLAlchemy 2.0 + asyncpg
                                        # Includes: Kubernetes-style /livez and /readyz health probes
                                        # Includes: Alembic async migrations (just migrate, just makemigration)
                                        # Includes: Docker Compose stack with Postgres + migration gating
                                        # Created directory: my_service
                                        # Development: cd my_service && docker compose up

# Example: Dry-run with backend flag
modernpackage my-service --backend --dry-run  # Preview backend scaffolding
# (Similar to above, but includes "add FastAPI backend" in the plan)

# Example: Create a fullstack application (backend + frontend)
modernpackage my-app --fullstack              # or `--reactjs` (alias)
                                              # Scaffolds a complete full-stack application
                                              # Backend: async FastAPI service with SQLAlchemy 2.0 + asyncpg
                                              # Frontend: Vite + React 19 + TypeScript with Vitest unit tests
                                              # Includes: Kubernetes health probes, migrations, Docker Compose
                                              # Includes: OpenAPI client, health-aware status page, Playwright e2e
                                              # Created directory: my_app
                                              # Development: cd my_app && docker compose up (runs backend + Postgres)
                                              #             cd frontend && npm run dev (runs frontend dev server)
                                              # Testing: npm run test (Vitest unit tests in frontend/)
                                              #          npm run test:e2e (Playwright against running stack)

# Example: Create a fullstack application with metadata
modernpackage my-app --fullstack \
  --author-name "Ada Lovelace" \
  --license "MIT"                              # Scaffolds fullstack with supplied metadata

# Example: Create a package with metadata
modernpackage my-package \
  --author-name "Ada Lovelace" \
  --author-email "ada@example.com" \
  --description "A cool package" \
  --license "MIT" \
  --repository-url "https://github.com/example/my-package"

# Example: Create a package using environment variable defaults
export MODERNPACKAGE_AUTHOR_NAME="Ada Lovelace"
export MODERNPACKAGE_AUTHOR_EMAIL="ada@example.com"
export MODERNPACKAGE_DESCRIPTION="A cool package"
export MODERNPACKAGE_LICENSE="MIT"
export MODERNPACKAGE_REPOSITORY_URL="https://github.com/example/my-package"
modernpackage my-package           # uses all five env defaults

# Example: Mix environment variables with command-line flags
export MODERNPACKAGE_AUTHOR_NAME="Ada Lovelace"
export MODERNPACKAGE_DESCRIPTION="Default description"
modernpackage my-package --author-name "Babbage"   # flag wins; uses "Babbage"
                                                   # uses "Default description" from env

# Example: Use git config when flags and env vars are absent
git config user.name "Ada Lovelace"
git config user.email "ada@example.com"
modernpackage my-package                           # author_name and author_email from git config
                                                   # (when neither flag nor env var is set)

# Example: Invalid package name (leading separator)
modernpackage -bad                      # Error: Invalid package name: '-bad' — name must start and end with a letter or digit
                                        # Exit code 2 (argument validation error)
                                        # No scaffolding occurs

# Example: Invalid package name (disallowed character)
modernpackage 'has space'               # Error: Invalid package name: 'has space' — name contains a disallowed character: ' ' (only letters, digits, '.', '_', '-' are allowed)
                                        # Exit code 2 (argument validation error)
                                        # No scaffolding occurs

# Example: Attempt to create a package with a name that collides with stdlib
modernpackage json                      # Error: Package name 'json' collides with the Python standard-library module 'json'
                                        # Exit code 2 (argument validation error)
                                        # No scaffolding occurs

# Example: Invalid email format
modernpackage my-package --author-email "not-an-email"  # Error: Invalid author email: 'not-an-email' — expected name@domain.tld
                                        # Exit code 2 (argument validation error)
                                        # No scaffolding occurs

# Example: Invalid repository URL (missing http(s) scheme)
modernpackage my-package --repository-url "github.com/user/repo"  # Error: Invalid repository URL: 'github.com/user/repo' — expected http(s)://…
                                        # Exit code 2 (argument validation error)
                                        # No scaffolding occurs

# Example: Clone failure (directory exists)
mkdir my-package
modernpackage my-package

# Output (stderr):
# destination directory already exists — choose a different package name
#
# git clone failed with exit code 128: fatal: destination path already exists and is not an empty directory.
# Exit code 1 (git clone fails)
# No scaffolding occurs

# Example: Template repository unreachable (network down or DNS failure)
modernpackage my-package                # Output (stderr):
                                        # repository unreachable — check your network connection
                                        # 
                                        # git clone failed with exit code 2: fatal: Could not resolve host: github.com
                                        # Exit code 1 (git clone fails)
                                        # No scaffolding occurs
```

View the installed version:
```bash
modernpackage --version               # or `mp -v`
```

### Optional Feature Flags

The CLI accepts optional feature flags for scaffolding:

- **`--backend` / `--fastapi`**: Store-true flag (default `False`) that scaffolds a complete FastAPI async service. When set, injects a working backend with:
  - FastAPI application factory with lifespan engine/sessionmaker management
  - Async SQLAlchemy 2.0 + asyncpg for async database operations (PostgreSQL)
  - Dependency injection for session management
  - Kubernetes-style health probes (`/livez` liveness, `/readyz` readiness with DB check)
  - Alembic async migrations with auto-migration support (`just migrate`, `just makemigration`, `just migration-check`)
  - Multi-stage `Containerfile` for production builds
  - Docker Compose stack with Postgres service and automatic migration gating
  - Complete test suite with ≥95% code coverage (satisfies generated `just check`)
  
  Without this flag, the generated package output is byte-for-byte identical to today (no backend injected, no extra dependencies).

- **`--fullstack` / `--reactjs`**: Store-true flag (default `False`) that scaffolds a complete frontend + backend application. When set, injects both the FastAPI backend (as above) and a React frontend with:
  - Vite 8 build system for development (dev server, HMR) and optimized production builds
  - React 19 with TypeScript strict mode for type-safe component development
  - Vitest 4.1 unit testing framework with jsdom environment
  - React Testing Library 16.3 for component testing best practices
  - Playwright 1.50+ for browser automation e2e testing (specs in `e2e/`, separate from unit tests)
  - Health-aware status page component demonstrating frontend-to-backend integration
  - OpenAPI client generation via `@hey-api/openapi-ts` with client-fetch plugin
  - ESLint 10 + typescript-eslint 8 for code quality
  - Prettier 3.8 for consistent code formatting
  - Pre-generated `src/client/` OpenAPI client synced to the backend schema
  - Isolated in a `frontend/` subdirectory to keep the Python package root clean
  - Node recipes in the generated Justfile: `frontend-install`, `frontend-build`, `frontend-test`, `frontend-test-e2e`, `frontend-lint`, `generate-client`, `frontend-check`
  - Python `pyproject.toml` gains zero new dependencies (frontend is fully isolated)
  
  `--fullstack` is a superset of `--backend`: the backend is always injected when `--fullstack` is set. If both `--backend` and `--fullstack` are passed, `--fullstack` takes precedence.

- **`--dry-run`**: Store-true flag (default `False`) that previews what scaffolding would do without making changes. Prints a high-level plan to stdout and exits with code 0. If the backend flag is set, the dry-run plan indicates that the FastAPI backend would be injected. If the fullstack flag is set, the dry-run plan indicates that both the backend and React frontend would be injected.

### Optional Metadata Flags

The CLI also accepts five optional flags for package metadata:

- **`--author-name`**: Author name to include in the package (free string). Defaults in order: `$MODERNPACKAGE_AUTHOR_NAME` → `git config user.name` → config file → `None`.
- **`--author-email`**: Author email address (must be a basic email format: `name@domain.tld`). Defaults in order: `$MODERNPACKAGE_AUTHOR_EMAIL` → `git config user.email` → config file → `None`.
- **`--description`**: Short description of the package (free string). Defaults in order: `$MODERNPACKAGE_DESCRIPTION` → config file → `None`.
- **`--license`**: License identifier (free string; commonly SPDX identifiers like `MIT`, `Apache-2.0`, etc.). Defaults in order: `$MODERNPACKAGE_LICENSE` → config file → `None`.
- **`--repository-url`**: Repository URL (must start with `http://` or `https://`). Defaults in order: `$MODERNPACKAGE_REPOSITORY_URL` → config file → `None`.

All metadata flags are optional and default to `None`. When provided via command-line flags, they are validated at parse time (email and URL shapes are checked). When values are sourced from environment variables, git config, or the config file, they are validated with the same rules as flag-supplied values. Invalid metadata (from any source) causes the command to exit with code 2 before any scaffolding occurs.

**Precedence**: Command-line flags take highest precedence, followed by environment variables, followed (for `author-name` and `author-email` only) by git config, followed by the per-user config file, and finally `None` if no source is set.

- For `author_name` and `author_email`: **flag > env > git config > config file > None**
- For other fields: **flag > env > config file > None** (no git config fallback)

When git config values are used, they come from the user's effective git configuration (merged local-over-global, the way `git commit` resolves them). If git is not installed or the config key is unset, the fallback returns `None` silently.

When config-file values are used, they are read from a per-user TOML file at `$XDG_CONFIG_HOME/modernpackage/config.toml` (or `~/.config/modernpackage/config.toml` if `$XDG_CONFIG_HOME` is unset or empty). The config file uses flat TOML keys named after each field: `author_name`, `author_email`, `description`, `license`, and `repository_url`. A value is treated as set only if it is a non-empty string; empty strings and non-string TOML values (int, bool, array, table) are treated as unset. A missing config file is expected and emits no notice. A malformed or unreadable config file is treated gracefully: a notice is printed to stderr (naming the file path and error), and metadata resolution continues with the next fallback source (or `None` if no other source is set). For example:

```toml
# ~/.config/modernpackage/config.toml
author_name = "Ada Lovelace"
author_email = "ada@example.com"
description = "A cool package"
license = "MIT"
repository_url = "https://github.com/example/my-package"
```

The `--help` output advertises each environment variable, making the fallback mechanism discoverable. Environment variables set to empty strings are treated as unset, allowing fallback to the next source.

The provided metadata is automatically written to the generated package's `pyproject.toml` file:
- `--author-name` and `--author-email` populate the `[project].authors` field
- `--description` populates the `[project].description` field
- `--license` adds a `[project].license` SPDX field and removes the hardcoded MIT classifier
- `--repository-url` populates the `[project.urls].homepage` field

All values are TOML-escaped to safely handle special characters (quotes and backslashes).

### Exit Codes

`modernpackage` returns exit code 0 on success (package initialized with all quality gates passing, or version displayed) and exit code 1 on failure (git clone, just init, or just check failed). This allows shell scripts and CI/CD pipelines to detect failures, including validation failures where the scaffolded package does not meet quality standards.

When `git clone` fails, the error message is enhanced with a friendly, actionable explanation of common failure modes (e.g., "repository unreachable — check your network connection" for network errors). The raw stderr is included for diagnostics. Unknown errors fall back to the raw error output.

## After Initialization

Once your new package is created and validated, you can begin development. The initialization process automatically removes the scaffolder's own CLI, tests, and documentation from the generated package, leaving you with a clean, minimal codebase. The process then runs `just check` on the newly scaffolded package and reports whether all quality gates passed (you'll see "just check passed" or "just check failed").

### Standard Package

The generated package includes:
- A minimal `__init__.py` with version `0.0.1`
- A stub `tests/test_main.py` with a single test (satisfying coverage requirements)
- A minimal generic `README.md` ready for your documentation
- No scaffolder CLI machinery, no end-to-end tests, and no scaffolder documentation

**Note**: If you provided a package name with hyphens or dots (e.g., `my-cool.package`), the created directory will use underscores instead (e.g., `my_cool_package`). This ensures the directory name and all Python imports are valid identifiers.

### Backend Package (with `--backend`)

When scaffolded with `--backend`, the generated package additionally includes:
- **Application layer**: `app.py` (FastAPI factory with lifespan), `db.py` (async engine + session management), `health.py` (health probes)
- **Database layer**: Async SQLAlchemy 2.0 base class, asyncpg driver configuration, environment-based connection URL
- **Testing**: `tests/test_app.py` with ≥95% coverage of backend modules (TestClient-based HTTP tests + async unit tests)
- **Migrations**: Alembic async environment (`migrations/env.py`), template (`migrations/script.py.mako`), and versions directory
- **Containerization**: `Containerfile` (multi-stage, BuildKit), `compose.yml` (app + Postgres + migration service), `.dockerignore`
- **Dependencies**: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `uvicorn` in `[project.dependencies]`; `httpx` in dev group
- **Justfile recipes**: `just migrate`, `just makemigration "message"`, `just migration-check` (standalone recipes, not part of `just check` chain)

### Fullstack Package (with `--fullstack`)

When scaffolded with `--fullstack`, the generated package includes both the backend (as above) **and** a frontend directory:
- **Frontend subdirectory**: `frontend/` at the package root contains an isolated Node.js project
- **Frontend source**: `frontend/src/` with React component tree starting from `App.tsx` (a health-aware status page) and `main.tsx`, TypeScript strict mode configuration, app entry point in `index.html`
- **Frontend build system**: Vite 8 configuration (`vite.config.ts`) with React plugin, dev server and preview server with proxy to `/api`, `/livez`, and `/readyz` (backend), production build optimization
- **Frontend testing**: Vitest 4.1 unit test runner with jsdom environment, React Testing Library 16.3 for component testing, test configuration in `setupTests.ts`; Playwright 1.50+ for browser e2e specs in `frontend/e2e/`, separate from unit tests
- **Status page**: `App.tsx` fetches backend health endpoints (`/livez` and `/readyz`) on mount and renders application and database health states, demonstrating frontend-to-backend integration and degrading gracefully when the backend is unreachable
- **Frontend quality**: ESLint 10 + typescript-eslint 8 for linting, Prettier 3.8 for formatting, TypeScript strict mode for type safety
- **API client**: Pre-generated `frontend/src/client/` containing OpenAPI client stubs (TypeScript), generated from the backend's OpenAPI schema via `@hey-api/openapi-ts`
- **Frontend dependencies**: React 19, @hey-api/client-fetch for API calls, React Query for data fetching, @playwright/test for e2e (all as devDependency)
- **Justfile recipes**: `just frontend-install`, `just frontend-build`, `just frontend-test`, `just frontend-test-e2e`, `just frontend-lint`, `just generate-client`, `just frontend-check` (Node recipes, not part of Python `just check` chain)
- **No Python dependencies added**: The Python `pyproject.toml` remains unchanged; frontend is fully isolated in its own Node.js project

To continue development:

```bash
cd my_package                   # Use the directory name (with underscores)
just check                      # Run tests and linters (already run during scaffolding)
just fix                        # Auto-fix linting and formatting issues
just publish                    # Publish your package to PyPI.org

# Backend-specific:
cd my_service                   # Backend service package
docker compose up               # Start app + Postgres + migration service
just migrate                    # Run pending migrations manually
just makemigration "add users"  # Generate a new migration
curl http://localhost:8000/readyz  # Check readiness probe
```

To push to a Git repository (create the project on GitLab/GitHub first):
```bash
git remote add origin git@gitlab.com:<your-username>/<directory-name>.git
git push
```

## Development
Commonly used commands for package development:
- `just check` - run unit tests and linters (format, lint, complexity, typecheck, tests, security audit, dead code detection). Primary quality gate; excludes e2e tests.
- `just test` - run unit tests only (mocked, parallel, excludes e2e). Includes: fast regression guards for the no-flag scaffold guarantee, metadata writing tests, and CLI argument parsing tests.
- `just test-e2e` - run end-to-end tests that scaffold packages and validate them with their respective test suites (slow, requires network and git/just/uv on PATH; npm required for fullstack tests; docker/podman compose required for backend and fullstack runtime tests; skips gracefully if tools missing). Includes: no-flag scaffold validation (verifies zero backend/frontend artifacts), backend scaffold validation (verifies FastAPI injection and `just check` passes), backend runtime integration test (verifies a scaffolded backend-only application runs end-to-end in a real Docker Compose stack with live Postgres, health probes, and real schema migrations via the scaffold's own `just makemigration`/`just migrate`), fullstack scaffold validation (verifies FastAPI backend and React frontend both inject correctly and their respective test suites pass), fullstack runtime integration test (verifies the generated application runs end-to-end in a real Docker Compose stack with live Postgres, HTTP health endpoints, API client generation, frontend builds, and Playwright browser automation against the running frontend+backend stack), fullstack feature integration test (verifies feature injection, migrations, API endpoints, HTTP round-trip, and browser-level data rendering through Playwright), and negative test (verifies no-flag packages have zero backend/frontend artifacts).
- `just fix` - format code and fix detected fixable issues.
- `just bump` - increment the patch component of the version in `modernpackage/__init__.py` (e.g., `0.0.9` → `0.0.10`). Useful for manual version control or testing; automatically invoked by `just publish`.
- `just publish` - automatically increment the patch version via `bump`, commit the version file to git, push to the remote repository, then build and publish the package to pypi.org. The bumped version is included in both the GitLab repository and the PyPI release.
- `just lock` - refresh `uv.lock` to the latest resolvable dependency versions.
- `just sync` - create the virtual environment and install the locked dev group + editable project via `uv sync`.

## Toolset
This package uses these cutting edge tools:
- ruff - for linting and code formatting
- mypy - for type checking
- pip-audit - for known vulnerability detection in dependencies
- deadcode - for unused code detection
- pytest - for collecting and running unit tests
- coverage - for code coverage by unit tests
- uv - for building & publishing package to pypi.org, Python virtual environment and dependency management
- pyproject.toml - configuration file for all tools
- Justfile - aliases for commonly used command line commands

## Feature requests:
- Newly installed package could have virtualenv initialised.
- Check if `git` is available before trying to initialise the repository.
- remove init Makefile alias and cli.py command python files.
- make a cli command: this package should be installable. Ideally this flow should work:
  - `pip install modernpackage`
  - `modernpackage mynewpackage`
  - `cd mynewpackage` && `make check` && `make publish`
- Add pre-commit hooks with all the tools enabled.
- codspeed.io could be considered for Continuous integration pipeline

- Provide Python version for modernpackage CLI command.
- Add modernpackage abreviation CLI alias not to type so much
- make compile and make sync does not work when virtual environment is activated
- enable async test execution by default:
    +    "pytest-asyncio",
    [tool.pytest.ini_options]
    addopts = "--cov=. --no-cov-on-fail --cov-fail-under=90.0"
    +asyncio_mode = "auto"
- Clean up the <package>/main.py file after initialization: that logic is overwhelming.
- Clean up README and descriptions in pyproject.toml and <package>/__init__.py.
- Package should display proper messages when internet connection or git is not available. Now it crashes without internet connection with this Traceback:
```
Cloning modernpackage files to /home/niekas/tools/gitruff
Cloning into '/home/niekas/tools/gitruff'...
fatal: unable to access 'https://github.com/albertas/modernpackage/': Could not resolve host: github.com
Traceback (most recent call last):
  File "/home/niekas/venv/bin/modernpackage", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/home/niekas/venv/lib/python3.12/site-packages/modernpackage/main.py", line 40, in main
    init_new_package(package_name=parsed_args.package_name)
  File "/home/niekas/venv/lib/python3.12/site-packages/modernpackage/main.py", line 26, in init_new_package
    pipe = Popen(["make", "init", package_name], stdin=PIPE, stdout=PIPE, cwd=new_package_path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/usr/lib/python3.12/subprocess.py", line 1955, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
FileNotFoundError: [Errno 2] No such file or directory: '/home/niekas/tools/gitruff'
```
- --django --fastapi or other options to add some kind of dependencies and initial project stub to get started with those projects easily.
- Should create package tags during publishing. Each version should a commit tagged in main branch.
