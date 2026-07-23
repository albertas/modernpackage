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
- Incremented by the `just bump` recipe during release (via a POSIX shell + sed rewrite of this file)
- The single source of truth for the package version; all version references flow from this definition

### `modernpackage/main.py`

The main CLI orchestrator with type-annotated functions and module-level constants for validation and tool checking.

#### Module-Level Constants

**`_TEMPLATE_REPOSITORY_URL: str`**

The GitHub URL of the template repository cloned to scaffold a new package:
```python
_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'
```

Used by the git clone command in `init_new_package()`. Centralizing the URL as a constant avoids duplication and ensures consistency across all references to the template repository.

**`_DRY_RUN_HEADER: str`**

The header line printed at the start of the dry-run plan:
```python
_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'
```

Printed to stdout by `_print_dry_run_plan()` when the `--dry-run` flag is set, establishing the section heading for the preview plan.

**`_RESET_VERSION: str`**

The version string the template is reset to by `just init` (mirrors the `Justfile` sed value at line 67; coupled by convention, not programmatically):
```python
_RESET_VERSION: str = '0.0.1'
```

Used by both the dry-run formatter (`_format_dry_run_plan()` at line 555) and the init summary formatter (`_format_init_summary()`) to report the version the newly scaffolded package is reset to. This is the single source of truth for the reset version, avoiding duplication of the `'0.0.1'` literal.

**`_INIT_SUMMARY_HEADER: str`**

The header line printed at the start of the post-scaffold summary block:
```python
_INIT_SUMMARY_HEADER: str = 'Created package:'
```

Printed to stdout by `_print_init_summary()` after `just check` passes on a successful scaffolding, establishing the section heading for the summary of created artifacts.

**`_PACKAGE_NAME_RE: re.Pattern[str]`**

Compiled regex pattern for PEP 508 / PyPI distribution names:
```python
_PACKAGE_NAME_RE: re.Pattern[str] = re.compile(
    r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$',
    re.IGNORECASE,
)
```

Matches a single alphanumeric character or an alphanumeric start followed by any number of allowed characters (alphanumeric, hyphens, underscores, dots) followed by an alphanumeric end. Used by `validate_package_name()`.

**`_DISALLOWED_CHAR_RE: re.Pattern[str]`**

Compiled regex pattern to find the first disallowed character in a package name:
```python
_DISALLOWED_CHAR_RE: re.Pattern[str] = re.compile(r'[^a-z0-9._-]', re.IGNORECASE)
```

Matches any character that is NOT in `[a-z0-9._-]` (case-insensitive). Used by `_explain_invalid_package_name()` to identify the first disallowed character and provide precise error messages.

**`_STDLIB_MODULE_NAMES: frozenset[str]`**

Frozen set of all Python standard-library top-level module names (available since Python 3.10):
```python
_STDLIB_MODULE_NAMES: frozenset[str] = sys.stdlib_module_names
```

Used by `validate_package_name()` to reject package names whose normalized module form would collide with a stdlib module (e.g., `json`, `os`, `email`).

**`_EMAIL_RE: re.Pattern[str]`**

Compiled regex pattern for basic email shape validation (permissive):
```python
_EMAIL_RE: re.Pattern[str] = re.compile(r'^\S+@\S+\.\S+$')
```

Matches: non-whitespace, `@`, non-whitespace, `.`, non-whitespace. Used by `validate_author_email()`. This is deliberately permissive and does not enforce RFC 5322 compliance.

**`_REPOSITORY_URL_RE: re.Pattern[str]`**

Compiled regex pattern for HTTP(S) URL validation:
```python
_REPOSITORY_URL_RE: re.Pattern[str] = re.compile(r'^https?://\S+$')
```

Matches: `http://` or `https://`, followed by one or more non-whitespace characters. Used by `validate_repository_url()`. Does not perform network reachability checks.

**`_AUTHOR_NAME_ENV: str`**

Environment variable name for the author name default:
```python
_AUTHOR_NAME_ENV: str = 'MODERNPACKAGE_AUTHOR_NAME'
```

Consulted by `parse_args()` when `--author-name` is omitted.

**`_AUTHOR_EMAIL_ENV: str`**

Environment variable name for the author email default:
```python
_AUTHOR_EMAIL_ENV: str = 'MODERNPACKAGE_AUTHOR_EMAIL'
```

Consulted by `parse_args()` when `--author-email` is omitted.

**`_DESCRIPTION_ENV: str`**

Environment variable name for the description default:
```python
_DESCRIPTION_ENV: str = 'MODERNPACKAGE_DESCRIPTION'
```

Consulted by `parse_args()` when `--description` is omitted.

**`_LICENSE_ENV: str`**

Environment variable name for the license default:
```python
_LICENSE_ENV: str = 'MODERNPACKAGE_LICENSE'
```

Consulted by `parse_args()` when `--license` is omitted.

**`_REPOSITORY_URL_ENV: str`**

Environment variable name for the repository URL default:
```python
_REPOSITORY_URL_ENV: str = 'MODERNPACKAGE_REPOSITORY_URL'
```

Consulted by `parse_args()` when `--repository-url` is omitted.

**`_GIT_CONFIG_USER_NAME_KEY: str`**

Git config key for the author name default:
```python
_GIT_CONFIG_USER_NAME_KEY: str = 'user.name'
```

Consulted by `_git_config_default()` when reading the user's git config for `author-name`.

**`_GIT_CONFIG_USER_EMAIL_KEY: str`**

Git config key for the author email default:
```python
_GIT_CONFIG_USER_EMAIL_KEY: str = 'user.email'
```

Consulted by `_git_config_default()` when reading the user's git config for `author-email`.

**`_CONFIG_DIR_NAME: str`**

Directory name within XDG config home for the per-user config file:
```python
_CONFIG_DIR_NAME: str = 'modernpackage'
```

Used by `_user_config_path()` to construct the default config file path.

**`_CONFIG_FILE_NAME: str`**

File name for the per-user TOML config file:
```python
_CONFIG_FILE_NAME: str = 'config.toml'
```

Used by `_user_config_path()` to construct the default config file path.

**`_XDG_CONFIG_HOME_ENV: str`**

Environment variable name for the XDG config home base directory:
```python
_XDG_CONFIG_HOME_ENV: str = 'XDG_CONFIG_HOME'
```

Consulted by `_user_config_path()` to resolve the per-user config file location.

**`_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...]`**

Clone-relative paths deleted wholesale from a generated package:
```python
_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...] = (
    'modernpackage/main.py',
    'tests/test_e2e.py',
    'tests_e2e',
    'docs',
    'BACKLOG.md',
    'backend_template',  # Always removed; re-injected if --backend is set
    'frontend_template',  # Always removed; re-injected if --fullstack is set
    'errors',           # Scaffolder operational/process artifacts
    'issues',           # removed from every generated package
    'workspace',
    'lifecycle_state.yml',  # deleted, then re-seeded with a fresh good-quality stub
    'metrics.yml',
)
```

Used by `_strip_scaffolding()` to remove the scaffolder's own machinery and operational/process artifacts from the cloned tree. Entries are looped over without error if a path does not exist (graceful degradation for variant template shapes). Paths are relative to the clone root. The first set of entries (CLI machinery, test suite, documentation, project metadata, and templates) are removed to keep the generated package clean and minimal. The second set (errors, issues, workspace directories and lifecycle state/metrics files) are scaffolder operational/process artifacts that should not be included in generated packages; `lifecycle_state.yml` is deleted here to drop the scaffolder's phases/semaphores and then re-seeded by `_strip_scaffolding()` with a fresh `code_quality_is_good: true` stub so the generated package's own lifecycle starts from a good-quality baseline. The `backend_template` and `frontend_template` entries are always deleted (even in the base clone), ensuring the no-flag output is byte-for-byte identical to today. When `--backend` is set, `_add_backend()` re-injects backend template files into the clone root after stripping. When `--fullstack` is set, both `_add_backend()` and `_add_frontend()` re-inject their respective templates after stripping. The `tests_e2e` entry is removed to prevent the scaffolder's own end-to-end test directory from leaking into scaffolded packages and causing import errors in the generated package's test suite.

**`_BACKEND_TEMPLATE_DIR: Path`**

Top-level directory containing the backend template files, resolved relative to the installed modernpackage package:
```python
_BACKEND_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / 'backend_template'
```

Used by `_add_backend()` to locate the committed backend template (app.py, db.py, health.py, tests/, migrations/, alembic.ini, Containerfile, compose.yml, .dockerignore). The path is resolved from the installed package so it works both in source checkouts and in published wheels.

**`_BACKEND_DEPENDENCIES: tuple[str, ...]`**

Runtime dependencies for the FastAPI backend service, appended to `[project.dependencies]` when `--backend` is set:
```python
_BACKEND_DEPENDENCIES: tuple[str, ...] = (
    'fastapi>=0.115',
    'sqlalchemy[asyncio]>=2.0',
    'asyncpg>=0.30',
    'alembic>=1.14',
    'uvicorn>=0.34',
)
```

Pinned with lower bounds only; versions float to the latest available (per `uv`'s resolver). Used by `_append_backend_dependencies()` to inject service runtime deps into the generated package's pyproject.toml.

**`_BACKEND_DEV_DEPENDENCIES: tuple[str, ...]`**

Test-only dependency for the FastAPI backend, appended to the dev group when `--backend` is set:
```python
_BACKEND_DEV_DEPENDENCIES: tuple[str, ...] = ('httpx',)
```

`httpx` is required by `fastapi.testclient.TestClient` and is added to the dev group so generated `just check` can run backend tests without adding a runtime dependency.

**`_BACKEND_RECIPES: str`**

Migration recipes appended to the generated package's Justfile:
```python
_BACKEND_RECIPES: str = """
migrate: sync
  uv run alembic upgrade head

makemigration message: sync
  uv run alembic revision --autogenerate -m "{{message}}"

migration-check: sync
  uv run alembic check
"""
```

Appended by `_append_backend_recipes()` after the existing Justfile. Recipes are standalone (not part of `just check` chain) and require a live database.

**`_FRONTEND_TEMPLATE_DIR: Path`**

Top-level directory containing the React frontend template files, resolved relative to the installed modernpackage package:
```python
_FRONTEND_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / 'frontend_template'
```

Used by `_add_frontend()` to locate the committed frontend template (Vite config, React components, Vitest config, ESLint config, TypeScript configs, package.json, pre-generated OpenAPI client). The path is resolved from the installed package so it works both in source checkouts and in published wheels. Only injected when `--fullstack` is set.

**`_FRONTEND_RECIPES: str`**

Frontend build and test recipes appended to the generated package's Justfile:
```python
_FRONTEND_RECIPES: str = """
frontend-install:
  cd frontend && npm ci

frontend-build:
  cd frontend && npm run build

frontend-test:
  cd frontend && npm run test

frontend-lint:
  cd frontend && npm run lint

generate-client:
  cd frontend && npm run generate-client

frontend-check: frontend-install
  cd frontend && npm run format:check && npm run lint && npm run typecheck && npm run test
"""
```

Appended by `_append_frontend_recipes()` after the existing Justfile. Recipes are standalone (not part of Python `just check` chain) and require Node.js + npm. The recipes are scoped to the `frontend/` subdirectory via `cd frontend && ...` and have no `sync` dependency (that is a Python/uv concept). The `frontend-check` recipe aggregates the frontend quality gates for local use.

**`_TEST_MAIN_STUB: str`**

Minimal stub for `tests/test_main.py` written to generated packages:
```python
_TEST_MAIN_STUB: str = """\
from modernpackage import __version__


def test_version() -> None:
    assert __version__ == '0.0.1'
"""
```

Replaces the scaffolder's full test suite after cloning. Serves two purposes: (1) pytest requires ≥1 collected test (empty collection exits non-zero); (2) importing the package keeps `--cov-fail-under=95.0` satisfied (after `main.py` is deleted, the only package code is the `__version__` line, executed on import). Written with the literal `modernpackage` token so that `just init`'s rename sed rewrites the import to the new module name.

**`_README_STUB_TEMPLATE: str`**

Minimal generic README template written to generated packages with the user's chosen distribution name:
```python
_README_STUB_TEMPLATE: str = """\
# {package_name}

A Python package.
"""
```

Replaces the scaffolder's detailed README (which documents the scaffolder, not the generated package). Required by `pyproject.toml:7` which specifies `readme = "README.md"`. The template uses a named `{package_name}` placeholder, which is interpolated directly into the README during `_strip_scaffolding` with the user's chosen distribution name (e.g., `my-package`). This ensures the README H1 reflects the actual package name without relying on sed-based token replacement.

**`_ANSI_GREEN: str`**

ANSI escape code for green text color:
```python
_ANSI_GREEN: str = '\033[32m'
```

Used by `_green()` to wrap text in green when color is enabled. Only rendered on an interactive TTY when the `NO_COLOR` environment variable is not set.

**`_ANSI_RESET: str`**

ANSI escape code to reset text styling to default:
```python
_ANSI_RESET: str = '\033[0m'
```

Used by `_green()` to restore normal text color after a green-wrapped section, ensuring subsequent output is not affected by the color state.

#### Functions

The main CLI orchestrator with type-annotated functions:

#### `_color_enabled() -> bool`

A private helper that determines whether ANSI color output should be used based on TTY and environment variables.

- **Purpose**: Probes the process boundary (TTY + environment) to decide whether to emit ANSI escape codes. Color is enabled only when **both** conditions hold: stdout is an interactive TTY **and** the `NO_COLOR` environment variable is not set (including the empty string). Called by `_green()` on every invocation.
- **Parameters**: none
- **Returns**: `bool` — `True` if color should be enabled, `False` otherwise
- **Algorithm**: 
  1. Checks `sys.stdout.isatty()` to determine if stdout is attached to an interactive terminal
  2. Checks `os.environ.get('NO_COLOR') is None` to ensure the `NO_COLOR` variable is unset (the check is `is None`, not truthiness, so empty string disables color per the `NO_COLOR` standard)
  3. Returns `True` only if both checks pass; otherwise returns `False`
- **Examples**:
  - In an interactive shell with no `NO_COLOR` set: returns `True`
  - When output is piped (`| cat`): returns `False` (stdout is not a TTY)
  - When `NO_COLOR=1` is set: returns `False`
  - When `NO_COLOR=''` is set: returns `False` (empty string disables color)
  - Under pytest `capsys`: returns `False` (capture is via a pipe, not a TTY)

**Design rationale**:
- Checks `isatty()` on the real `sys.stdout` object, not a cached value, so color is responsive to runtime redirection
- Never raises an exception; degrades gracefully to plain text if stdout lacks the `isatty` method or any other probe fails (graceful boundary style per `main.py`)
- The `is None` check (not truthiness) honors the `NO_COLOR` standard: any value, including the empty string, disables color

#### `_green(text: str) -> str`

A private helper that wraps text in ANSI green color when color is enabled, otherwise returns the text unchanged.

- **Purpose**: Wraps affirmative status tokens (e.g., `'[ok]'`, `'passed'`, `'valid'`) in ANSI green/reset codes when stdout is an interactive TTY and `NO_COLOR` is unset. When color is disabled, returns the input unchanged, ensuring piped/redirected output is byte-for-byte identical to plain text.
- **Parameters**:
  - `text: str` — the text to optionally wrap in green
- **Returns**: `str` — the input text wrapped in `_ANSI_GREEN` + `_ANSI_RESET` if color is enabled; the input text unchanged otherwise
- **Algorithm**:
  1. Calls `_color_enabled()` to check if color should be applied
  2. If `True`: returns `f'{_ANSI_GREEN}{text}{_ANSI_RESET}'` (text wrapped in escape codes)
  3. If `False`: returns `text` unchanged
- **Examples**:
  - With color enabled: `_green('[ok]')` → `'\033[32m[ok]\033[0m'` (visible as green in terminal)
  - With color disabled: `_green('[ok]')` → `'[ok]'` (unchanged)
  - Used in `init_new_package`: wraps `'passed'` and `'valid'` in the success message

**Design rationale**:
- Reuses the same helper for all affirmative tokens, ensuring consistent color application across the output
- Returns the input unchanged when color is disabled, making the output identical to non-color output for piped/pytest scenarios, so existing exact-string tests pass unchanged

#### `_format_dry_run_plan(module_name: str, target_path: Path, *, author_name: str | None, author_email: str | None, description: str | None, package_license: str | None, repository_url: str | None) -> str`

A private helper that formats the dry-run preview plan into a multi-line string.

- **Purpose**: Called by `_print_dry_run_plan()` to format the dry-run preview into a human-readable plan. Reports only what the code knows (not what the template will do beyond the documented `just init` outcomes).
- **Parameters**:
  - `module_name: str` — the normalized module name (e.g., `'my_cool_package'`)
  - `target_path: Path` — the computed target directory path
  - `author_name: str | None` — author name (keyword-only)
  - `author_email: str | None` — author email (keyword-only)
  - `description: str | None` — package description (keyword-only)
  - `package_license: str | None` — license identifier (keyword-only)
  - `repository_url: str | None` — repository URL (keyword-only)
- **Returns**: `str` — a multi-line formatted plan with a header, clone action, metadata substitutions, and `just init` outcomes
- **Format**: Uses the `_DRY_RUN_HEADER` constant for the header line, followed by action lines with two-space indentation. For each metadata field, reports either the value (if non-`None`) or a note that it "keeps template default" (if `None`).
- **Example output**:
  ```
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

**Design rationale**:
- Reports the target directory, template URL, and per-field metadata (with `None` → "keeps template default") so the user knows what values will be written
- Includes the well-known `just init` outcomes (rename, version reset) drawn from the template recipe's documented behavior
- Does not attempt to enumerate the exact file list or parse the template `Justfile` (that would require a clone, which the dry-run forbids)
- Extracted into a separate function so the plan is independently testable and `_print_dry_run_plan()` remains a thin output wrapper

#### `_print_dry_run_plan(module_name: str, target_path: Path, *, author_name: str | None, author_email: str | None, description: str | None, package_license: str | None, repository_url: str | None) -> None`

A private helper that prints the dry-run preview plan to stdout.

- **Purpose**: Called by `init_new_package()` when `dry_run=True`. Prints the formatted plan to stdout and lets the caller return.
- **Parameters**: Same as `_format_dry_run_plan()` (forwarded directly)
- **Returns**: `None`
- **Behavior**: 
  1. Calls `_format_dry_run_plan()` with all parameters
  2. Prints the result to stdout via `print(... )  # noqa: T201`
- **Output convention**: Matches the existing output convention (progress/informational text to stdout; design Decision 10, `main.py:592`).

#### `_format_init_summary(package_name: str, created_path: Path) -> str`

A private helper that formats the post-scaffold summary block into a multi-line string.

- **Purpose**: Called by `_print_init_summary()` to format the post-scaffold summary after `just check` passes. Returns text that is independently testable without capturing stdout. Reports the created package name (distribution name), directory path, and the version the template was reset to (`_RESET_VERSION`).
- **Parameters**:
  - `package_name: str` — the validated PEP 508 distribution name (e.g., `'my-cool.package'`)
  - `created_path: Path` — the created directory path (absolute path, e.g., `Path.cwd() / module_name`)
- **Returns**: `str` — a multi-line formatted summary with a header line (`_INIT_SUMMARY_HEADER`), followed by 2-space-indented fields
- **Format**: Uses the `_INIT_SUMMARY_HEADER` constant for the header line, followed by three indented lines:
  - `f'  package name: {package_name}'`
  - `f'  path: {created_path}'`
  - `f'  version: {_RESET_VERSION}'`
- **Example output**:
  ```
  Created package:
    package name: my-cool.package
    path: /home/user/my_cool_package
    version: 0.0.1
  ```

**Design rationale**:
- Extracted into a separate function so the summary is independently testable (returns a string, not printing directly)
- Matches the formatter/printer split pattern used by `_format_dry_run_plan()` / `_print_dry_run_plan()`
- Uses 2-space indentation to match the dry-run plan body indentation aesthetic
- Reports all three values (distribution name, directory path, reset version) that are known at the time of the success branch

#### `_print_init_summary(package_name: str, created_path: Path) -> None`

A private helper that prints the formatted post-scaffold summary to stdout.

- **Purpose**: Called by `init_new_package()` in the success branch immediately after `just check` passes, to print a human-readable summary of what was created.
- **Parameters**:
  - `package_name: str` — the validated PEP 508 distribution name (passed through from the caller)
  - `created_path: Path` — the created directory path (passed through from the caller)
- **Returns**: `None`
- **Behavior**: 
  1. Calls `_format_init_summary(package_name, created_path)` to get the formatted block
  2. Prints the result to stdout via `print(...) # noqa: T201`
- **Output convention**: Matches the existing output convention (progress/informational text to stdout)

#### `_explain_invalid_package_name(value: str) -> str`

A private helper that returns a precise reason why a package name failed validation.

- **Purpose**: Called only when `_PACKAGE_NAME_RE.match(value)` is falsy, to provide actionable diagnostic messages.
- **Parameter**: `value: str` — the input string that failed the regex check
- **Returns**: `str` — a concise explanation of the failure reason
- **Algorithm**: Checks reasons in precedence order (most-specific-first):
  1. **Empty value**: returns `'name must not be empty'`
  2. **Disallowed character**: finds the first character outside `[a-z0-9._-]` (case-insensitive) and returns `'name contains a disallowed character: <char> (only letters, digits, '.', '_', '-' are allowed)'`
  3. **Leading/trailing separator**: residual case (regex failed, value is non-empty and contains only allowed characters), returns `'name must start and end with a letter or digit'`

Examples:
- `_explain_invalid_package_name('')` → `'name must not be empty'`
- `_explain_invalid_package_name('has space')` → `"name contains a disallowed character: ' ' (only letters, digits, '.', '_', '-' are allowed)"`
- `_explain_invalid_package_name('-bad')` → `'name must start and end with a letter or digit'`
- `_explain_invalid_package_name('bad.')` → `'name must start and end with a letter or digit'`

#### `validate_package_name(value: str) -> str`

Validates that a string is a valid PEP 508 / PyPI distribution name and that its normalized module form does not collide with a Python standard-library module. Used as the `type=` validator in argument parsing.

A valid distribution name must:
- Start and end with an alphanumeric character (a-z, A-Z, 0-9)
- May contain hyphens (`-`), underscores (`_`), and dots (`.`) in between
- Matching is case-insensitive
- When normalized to a module name (replacing hyphens and dots with underscores), it must not equal a Python standard-library top-level module name

The validation is performed in two stages:

1. **Composition check** using a compiled regex constant `_PACKAGE_NAME_RE`:
   ```python
   _PACKAGE_NAME_RE: re.Pattern[str] = re.compile(
       r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$',
       re.IGNORECASE,
   )
   ```
   If this regex fails to match, the helper `_explain_invalid_package_name(value)` is called to generate a specific reason phrase.

2. **Collision check** against `_STDLIB_MODULE_NAMES`:
   ```python
   _STDLIB_MODULE_NAMES: frozenset[str] = sys.stdlib_module_names
   ```
   The normalized module name is tested for membership in this frozen set. If present, the name is rejected with a specific message naming the collision. The collision check runs only on well-formed names to ensure malformed input gets the detailed reason from the helper.

- **Parameter**: `value: str` — the input string to validate
- **Returns**: `str` — the input string unchanged if valid
- **Raises**: `ArgumentTypeError(f'Invalid package name: {value!r} — {reason}')` if the string does not match the PEP 508 pattern (where `{reason}` is from `_explain_invalid_package_name`)
- **Raises**: `ArgumentTypeError(f'Package name {value!r} collides with the Python standard-library module {module_name!r}')` if the normalized name matches a stdlib module

Examples:
- `validate_package_name('mypackage')` → `'mypackage'` ✓
- `validate_package_name('my-package')` → `'my-package'` ✓
- `validate_package_name('my_package')` → `'my_package'` ✓
- `validate_package_name('my.package')` → `'my.package'` ✓
- `validate_package_name('a')` → `'a'` ✓
- `validate_package_name('my-json')` → `'my-json'` ✓ (near-miss: normalizes to `my_json`, not in stdlib set)
- `validate_package_name('jsonschema')` → `'jsonschema'` ✓ (near-miss: contains stdlib name but does not equal it)
- `validate_package_name('email_utils')` → `'email_utils'` ✓ (near-miss: contains stdlib name but does not equal it)
- `validate_package_name('')` → raises `ArgumentTypeError('Invalid package name: '' — name must not be empty')`
- `validate_package_name('-bad')` → raises `ArgumentTypeError("Invalid package name: '-bad' — name must start and end with a letter or digit")`
- `validate_package_name('bad-')` → raises `ArgumentTypeError("Invalid package name: 'bad-' — name must start and end with a letter or digit")`
- `validate_package_name('has space')` → raises `ArgumentTypeError("Invalid package name: 'has space' — name contains a disallowed character: ' ' (only letters, digits, '.', '_', '-' are allowed)")`
- `validate_package_name('json')` → raises `ArgumentTypeError("Package name 'json' collides with the Python standard-library module 'json'")`
- `validate_package_name('os')` → raises `ArgumentTypeError("Package name 'os' collides with the Python standard-library module 'os'")`
- `validate_package_name('email')` → raises `ArgumentTypeError("Package name 'email' collides with the Python standard-library module 'email'")`

#### `validate_author_email(value: str) -> str`

Validates that a string has a basic email shape using a permissive regex pattern. Used as the `type=` validator in argument parsing for the `--author-email` flag.

A valid email must:
- Start with non-whitespace characters
- Contain exactly one `@` symbol  
- Follow with non-whitespace characters
- Contain exactly one `.`
- End with non-whitespace characters

Pattern: `^\S+@\S+\.\S+$` (one or more non-whitespace, `@`, one or more non-whitespace, `.`, one or more non-whitespace)

- **Parameter**: `value: str` — the input string to validate
- **Returns**: `str` — the input string unchanged if valid
- **Raises**: `ArgumentTypeError(f'Invalid author email: {value!r} — expected name@domain.tld')` if the string does not match the email pattern

Examples:
- `validate_author_email('a@b.co')` → `'a@b.co'` ✓
- `validate_author_email('user@example.com')` → `'user@example.com'` ✓
- `validate_author_email('not-an-email')` → raises `ArgumentTypeError('Invalid author email: 'not-an-email' — expected name@domain.tld')`
- `validate_author_email('user@example')` → raises `ArgumentTypeError('Invalid author email: 'user@example' — expected name@domain.tld')`

**Notes:**
- This is deliberately permissive and does not enforce RFC 5322 compliance (full email validation is out of scope)
- The regex rejects obviously wrong input without over-engineering

#### `validate_repository_url(value: str) -> str`

Validates that a string is an HTTP or HTTPS URL. Used as the `type=` validator in argument parsing for the `--repository-url` flag. Does not perform network reachability checks.

A valid URL must:
- Start with `http://` or `https://`
- Follow with one or more non-whitespace characters

Pattern: `^https?://\S+$`

- **Parameter**: `value: str` — the input string to validate
- **Returns**: `str` — the input string unchanged if valid
- **Raises**: `ArgumentTypeError(f'Invalid repository URL: {value!r} — expected http(s)://…')` if the string does not match the URL pattern

Examples:
- `validate_repository_url('https://x.com/r')` → `'https://x.com/r'` ✓
- `validate_repository_url('http://example.com')` → `'http://example.com'` ✓
- `validate_repository_url('github.com/user/repo')` → raises `ArgumentTypeError('Invalid repository URL: 'github.com/user/repo' — expected http(s)://…')`
- `validate_repository_url('ftp://x.com')` → raises `ArgumentTypeError('Invalid repository URL: 'ftp://x.com' — expected http(s)://…')`

**Notes:**
- Only `http://` and `https://` schemes are accepted; other schemes (ftp, git, etc.) are rejected
- No network call is made to verify URL reachability or validity; only the scheme and format are checked

#### `normalize_module_name(value: str) -> str`

Converts a validated distribution name into an import-safe Python module identifier by replacing `.` and `-` with `_`.

- **Purpose**: The `validate_package_name` validator accepts PEP 508 / PyPI distribution names containing `.` and `-` (e.g., `my-cool.package`). However, these characters are not valid in Python import statements; this helper transforms the distribution name into a valid module identifier.
- **Input**: `value: str` — a distribution name already validated by `validate_package_name` (guaranteed to match the PEP 508 pattern)
- **Returns**: `str` — the module name with `.` and `-` replaced by `_`, other characters unchanged
  - `.` → `_`
  - `-` → `_`
  - `_` → `_` (preserved)
  - Case unchanged (uppercase remains uppercase, lowercase remains lowercase)
  - Runs of underscores are preserved (e.g., `a--b` → `a__b`, not collapsed to `a_b`)

Examples:
- `normalize_module_name('mypackage')` → `'mypackage'` (no change)
- `normalize_module_name('my-package')` → `'my_package'`
- `normalize_module_name('my_package')` → `'my_package'` (no change)
- `normalize_module_name('my.package')` → `'my_package'`
- `normalize_module_name('my-cool.package')` → `'my_cool_package'`
- `normalize_module_name('my_cool_pkg.v2')` → `'my_cool_pkg_v2'`
- `normalize_module_name('a')` → `'a'`
- `normalize_module_name('a--b')` → `'a__b'`

**Notes and limitations:**
- Input is expected to be already validated by `validate_package_name`, so this never returns `None`
- Uppercase letters in the input are preserved (e.g., `MyPackage` remains `MyPackage`, not lowercased)
- This mapping does not handle Python keywords (`class`, `import`, etc.) or names starting with digits (e.g., `9lives`) — these remain invalid module names. Such names should be rejected at validation time (currently out of scope)

#### `_environment_default(variable_name: str) -> str | None`

A private helper that retrieves an environment variable value, treating empty strings as unset.

- **Purpose**: Used by `parse_args()` to resolve metadata defaults from the environment when corresponding flags are omitted.
- **Parameter**: `variable_name: str` — the name of the environment variable (e.g., `'MODERNPACKAGE_AUTHOR_NAME'`)
- **Returns**: `str | None` — the environment variable value if present and non-empty, or `None` if absent or empty
- **Algorithm**: uses `os.environ.get(variable_name) or None` to collapse both missing (`None`) and empty-string values to `None`

Examples:
- `_environment_default('MODERNPACKAGE_AUTHOR_NAME')` with env var set to `'Ada'` → `'Ada'`
- `_environment_default('MODERNPACKAGE_DESCRIPTION')` with env var unset → `None`
- `_environment_default('MODERNPACKAGE_LICENSE')` with env var set to `''` (empty string) → `None`

#### `_git_config_default(key: str) -> str | None`

A private helper that reads an effective git config value, treating missing/unset/empty values as `None`.

- **Purpose**: Used by `parse_args()` to resolve `author-name` and `author-email` defaults from the user's git config when both corresponding flags and environment variables are omitted. Reads the merged (local-over-global) git config the way a commit would resolve it.
- **Parameter**: `key: str` — the git config key to read (e.g., `'user.name'` or `'user.email'`)
- **Returns**: `str | None` — the trimmed git config value if present and non-empty, or `None` if git is missing, the key is unset (git exits 1), the value is empty, or the command otherwise fails
- **Algorithm**: 
  1. Spawns `git config <key>` via `subprocess.run(check=False, capture_output=True, text=True)`
  2. Catches `FileNotFoundError` (git command not found) and returns `None` silently
  3. If return code is non-zero (key unset or other git failure), returns `None`
  4. If return code is zero, returns the trimmed stdout value, or `None` if stdout is empty
  5. Never raises; always degrades gracefully to `None`
- **Calls**: `subprocess.run()` with `check=False` to degrade silently on non-zero exit codes (design Decision 4 — an absent git default is expected, not an error)

Examples:
- `_git_config_default('user.name')` when git is installed and `user.name` is set to `'Ada Lovelace\n'` → `'Ada Lovelace'`
- `_git_config_default('user.name')` when git is installed and `user.name` is unset (git exits 1) → `None`
- `_git_config_default('user.email')` when git is not found → `None`
- `_git_config_default('user.name')` when the key exists but stdout is empty → `None`

#### `_user_config_path() -> Path | None`

A private helper that resolves the per-user TOML config file path using XDG Base Directory Specification conventions.

- **Purpose**: Used by `_load_config_file()` to determine where to read the per-user config file. Resolves `$XDG_CONFIG_HOME/modernpackage/config.toml`, falling back to `~/.config/modernpackage/config.toml` when `$XDG_CONFIG_HOME` is unset or empty.
- **Returns**: `Path | None` — the resolved config file path if the home directory can be determined, or `None` if `Path.home()` raises `RuntimeError` (e.g., in odd environments where the home directory cannot be resolved)
- **Algorithm**:
  1. Reads `$XDG_CONFIG_HOME` environment variable
  2. If set and non-empty, uses that directory as the base; else falls back to `~/.config`
  3. Appends `modernpackage/config.toml` to the base path
  4. Returns the resolved `Path`, or `None` if home directory resolution fails

Examples:
- With `XDG_CONFIG_HOME=/custom/xdg` → `/custom/xdg/modernpackage/config.toml`
- With `XDG_CONFIG_HOME=` (empty) and home `/home/user` → `/home/user/.config/modernpackage/config.toml`
- With `XDG_CONFIG_HOME` unset and home `/home/user` → `/home/user/.config/modernpackage/config.toml`
- When `Path.home()` raises `RuntimeError` → `None`

#### `_load_config_file() -> dict[str, object]`

A private helper that parses the per-user TOML config file into a mapping, or returns an empty dict on any error.

- **Purpose**: Used by `parse_args()` to read the per-user config file. Returns an empty dict on any error (missing file, malformed TOML, or read errors), with the behavior depending on the error type:
  - Missing file (`FileNotFoundError`): silent, returns `{}`
  - Malformed or unreadable (`TOMLDecodeError` or `OSError`): prints a notice to stderr and returns `{}`
- **Returns**: `dict[str, object]` — parsed TOML content (a mapping of all top-level keys to their values) if successful, or `{}` if the file is missing or unreadable
- **Algorithm**:
  1. Calls `_user_config_path()` to resolve the config file path
  2. If path is `None`, returns `{}`
  3. Attempts to open the file in binary mode and parse it with `tomllib.load()`
  4. Catches `FileNotFoundError` and returns `{}` silently (expected case: no config file yet)
  5. Catches `tomllib.TOMLDecodeError` or `OSError` (malformed or unreadable), prints a notice to stderr (`'Ignoring unreadable config file {path}: {error}'`), and returns `{}` (design Decision 6 — degrade gracefully at boundaries)
  6. Never raises; always degrades gracefully

Examples:
- File missing: returns `{}`
- File contains valid TOML (`author_name = "Ada"`) → `{'author_name': 'Ada'}`
- File contains malformed TOML → stderr notice `'Ignoring unreadable config file /home/user/.config/modernpackage/config.toml: ...'`, returns `{}`
- File unreadable (permission denied) → stderr notice, returns `{}`

#### `_config_file_default(config: Mapping[str, object], key: str) -> str | None`

A private helper that extracts a value from the config file mapping, treating it as set only if it is a non-empty string.

- **Purpose**: Used by `parse_args()` to read individual metadata fields from the loaded config file. Ensures type safety by coercing non-string and empty-string values to `None`, matching the empty-as-unset convention of the environment and git config readers (design Decision 5).
- **Parameters**:
  - `config: Mapping[str, object]` — the loaded config file mapping (from `_load_config_file()`)
  - `key: str` — the config key to read (e.g., `'author_name'`, `'license'`)
- **Returns**: `str | None` — the value from `config[key]` if it is a non-empty string, or `None` if the key is missing, the value is empty, or the value is non-string (int, bool, array, table, etc.)
- **Algorithm**:
  1. Retrieves `config.get(key)`, which returns `None` if key is absent
  2. Checks if the value is a non-empty `str` using `isinstance(value, str) and value`
  3. Returns the value unchanged if the check passes, or `None` otherwise

Examples:
- `_config_file_default({'license': 'MIT'}, 'license')` → `'MIT'`
- `_config_file_default({'license': ''}, 'license')` → `None` (empty string treated as unset)
- `_config_file_default({'license': 42}, 'license')` → `None` (non-string value treated as unset)
- `_config_file_default({}, 'license')` → `None` (missing key)

#### `_toml_escape(value: str) -> str`

A private helper that escapes special characters in a string to make it safe for insertion into TOML basic-string values.

- **Purpose**: Used by `_write_package_metadata()` and `_apply_license()` to escape values before substituting them into TOML template strings. Ensures that values containing backslashes and double-quotes cannot produce invalid TOML.
- **Parameter**: `value: str` — the string to escape
- **Returns**: `str` — the escaped string with backslashes and double-quotes properly escaped for TOML
- **Algorithm**: 
  1. Escapes all backslashes by replacing `\` with `\\` (must run first to avoid double-escaping)
  2. Escapes all double-quotes by replacing `"` with `\"`
- **Examples**:
  - `_toml_escape('simple')` → `'simple'` (no change)
  - `_toml_escape('with "quotes"')` → `'with \"quotes\"'`
  - `_toml_escape('path\\with\\backslashes')` → `'path\\\\with\\\\backslashes'`
  - `_toml_escape('both \\"edge cases\\"')` → `'both \\\\\"edge cases\\\\\"'`

**Notes:**
- Order matters: backslashes are escaped first to avoid double-escaping quotes that are introduced during backslash escaping
- The function does not validate TOML syntax; it assumes the caller will use the result in a TOML basic-string context (wrapped in `"..."`)
- This enables safe direct string substitution without requiring a TOML writer library

#### `_write_package_metadata(package_path: Path, *, author_name: str | None, author_email: str | None, description: str | None, package_license: str | None, repository_url: str | None) -> None`

A private helper that applies metadata substitutions to the cloned package's `pyproject.toml` file, replacing known template placeholders with supplied values.

- **Purpose**: Called by `init_new_package()` after cloning and before `just init`, to write user-supplied metadata into the package's configuration file. This ensures the metadata is present in the package's initial git commit and is part of the permanent scaffold.
- **Parameters** (all keyword-only):
  - `package_path: Path` — path to the cloned package directory
  - `author_name: str | None` — author name to write, or `None` to skip (default `None`)
  - `author_email: str | None` — author email to write, or `None` to skip (default `None`)
  - `description: str | None` — package description to write, or `None` to skip (default `None`)
  - `package_license: str | None` — license identifier to write, or `None` to skip (default `None`)
  - `repository_url: str | None` — repository URL to write, or `None` to skip (default `None`)
- **Behavior**:
  1. Constructs the path to `pyproject.toml` inside the package directory
  2. Attempts to read the file; if it does not exist, prints a notice to stderr and returns without raising
  3. For each non-`None` field, performs a targeted `str.replace()` of a known template placeholder with the TOML-escaped value
  4. Only writes the file if at least one substitution changed it (idempotent: repeated calls with the same values are no-ops)
  5. Never raises; always degrades gracefully on missing files
- **Template placeholders matched**:
  - `author_name`: replaces `'Name Surname'` (in `[project].authors[0].name`)
  - `author_email`: replaces `'email@example.com'` (in `[project].authors[0].email`)
  - `description`: replaces `'Package configuration example using bleeding edge toolset.'` (in `[project].description`)
  - `repository_url`: replaces `'https://github.com/albertas/modernpackage'` (in `[project.urls].homepage`)
  - `package_license`: delegated to `_apply_license()` helper for insertion and classifier cleanup
- **Graceful degradation**: If the `pyproject.toml` file is missing (e.g., in mocked unit tests that never create a real clone), the function prints a diagnostic notice to stderr and returns without raising. This allows unit tests that mock `Popen` (and thus never create a real filesystem copy) to pass unchanged.

Examples:
```python
_write_package_metadata(
    Path('/tmp/my_package'),
    author_name='Jane Doe',
    author_email='jane@example.org',
    description='A real package.',
    package_license=None,
    repository_url='https://example.org/repo',
)
# Replaces author name, email, description, and URL in pyproject.toml
# Leaves package_license placeholder untouched (None)

_write_package_metadata(
    Path('/tmp/my_package'),
    author_name=None,
    author_email=None,
    description=None,
    package_license=None,
    repository_url=None,
)
# No changes (all None values are skipped; file is not rewritten)
```

#### `_apply_license(content: str, package_license: str) -> str`

A private helper that inserts a PEP 639 license key into the TOML content and removes the hardcoded MIT classifier.

- **Purpose**: Called by `_write_package_metadata()` when a license value is supplied. Keeps license-specific logic isolated, helping maintain cyclomatic complexity ≤ 8 in the main writer function.
- **Parameters**:
  - `content: str` — the TOML content (read from `pyproject.toml`)
  - `package_license: str` — the license identifier to write (e.g., `'MIT'`, `'Apache-2.0'`)
- **Returns**: `str` — the modified TOML content with the license key inserted and the hardcoded MIT classifier removed
- **Behavior**:
  1. Constructs the license line: `license = "<escaped_value>"`
  2. Inserts it after the stable `readme = "README.md"` line (placing it inside `[project]`)
  3. Removes the hardcoded `"License :: OSI Approved :: MIT License"` classifier line (4-space indent, trailing comma, newline)
  4. Returns the modified content
- **Design rationale**: 
  - License is inserted after `readme` (a stable anchor line) rather than after description (which may be `None` and thus absent), ensuring consistent insertion point
  - When a license value is supplied, the MIT classifier is removed to avoid contradictory hardcoded licensing information
  - When license is `None`, `_apply_license()` is not called, so the classifier remains (allowing unspecified licenses to retain the template's default)
- **Examples**:
  ```python
  content = """...
  readme = "README.md"
  ...
      "License :: OSI Approved :: MIT License",
  ..."""
  
  result = _apply_license(content, 'Apache-2.0')
  # Result contains:
  # readme = "README.md"
  # license = "Apache-2.0"
  # ... (no MIT classifier)
  ```

#### `_remove_project_scripts(pyproject_path: Path) -> None`

A private helper that removes the `[project.scripts]` table from a cloned package's `pyproject.toml`.

- **Purpose**: Called by `_strip_scaffolding()` to remove console-script entry points from the generated package, avoiding dangling references to the deleted `main.py`. Keeps entry-point removal isolated and testable.
- **Parameters**:
  - `pyproject_path: Path` — the path to `pyproject.toml` to modify (e.g., `clone_dir / 'pyproject.toml'`)
- **Returns**: `None` (mutates the file in place)
- **Behavior**:
  1. Reads the file line-by-line (preserving line endings)
  2. Searches for the line `[project.scripts]\n`
  3. If found, marks that line as the start of the table and walks forward to find the next section header (a line starting with `[`)
  4. Deletes all lines from the `[project.scripts]` header through the line before the next section (leaving surrounding tables intact)
  5. Writes the modified content back to the file
  6. If the file is missing or the table is not present, returns silently (no-op, no error)
- **Design rationale**:
  - Uses line-based deletion rather than TOML parsing to avoid introducing a new dependency and preserve formatting of surrounding tables
  - Gracefully handles missing files (unit tests seed minimal trees where `pyproject.toml` may not exist) and absent tables (clone-shape-agnostic)
  - Deletion is surgical: only the `[project.scripts]` header, its entries, and the trailing blank line are removed; neighboring tables remain untouched

#### `_strip_scaffolding(package_path: Path, package_name: str) -> None`

A private helper that removes the scaffolder's own CLI, tests, documentation, and entry points from a cloned package tree.

- **Purpose**: Called from `init_new_package()` after `_write_package_metadata()` and before the `just init` subprocess, to remove the scaffolder's own machinery from the clone. Run before rename and git commit so the initial commit captures a clean tree.
- **Parameters**:
  - `package_path: Path` — the root directory of the cloned package (e.g., `Path.cwd() / 'my_package'`)
  - `package_name: str` — the distribution name chosen by the user (e.g., `'my-package'`), written directly into the README H1
- **Returns**: `None` (mutates the filesystem in place)
- **Behavior**:
  1. Iterates over paths in `_SCAFFOLDING_PATHS_TO_DELETE`
  2. For each path (relative to `package_path`):
     - If it is a directory: removes it and its contents via `shutil.rmtree(..., ignore_errors=True)`
     - If it is a file: removes it via `Path.unlink(missing_ok=True)`
     - Tolerates missing paths (no error if the path does not exist)
  3. Writes `_TEST_MAIN_STUB` to `tests/test_main.py` (overwriting any existing test suite)
  4. Writes `_README_STUB_TEMPLATE.format(package_name=package_name)` to `README.md` (overwriting the scaffolder's detailed README with the user's chosen distribution name as the H1)
  5. Calls `_remove_project_scripts(package_path / 'pyproject.toml')` to delete the console-script entry points
- **Assumptions**:
  - The clone root and `tests/` directory exist (guaranteed by `git clone`)
  - Deleted paths may be absent (graceful degradation for variant template shapes)
- **Design rationale**:
  - Deletes wholesale (no attempt to preserve or modify individual files) to ensure a clean slate
  - The test stub is written with the literal `modernpackage` token and is renamed by `just init`'s sed pass. The README is written with the user's chosen distribution name directly, bypassing the sed pass for that file.
  - Runs **before** `just init` so the single git commit captures the clean tree without scaffolding
  - Tolerates absent paths so the function is shape-agnostic (works if the template evolves, adds, or removes files)
  - Raises `RuntimeError` on errors (e.g., permission denied), funnel through `main()` exception handler

Examples:
```python
# Strips a cloned package in place
_strip_scaffolding(Path('/tmp/my_package'), 'my-package')
# Deletes: modernpackage/main.py, tests/test_e2e.py, docs/, BACKLOG.md, backend_template/
# Writes: tests/test_main.py (stub), README.md (stub with H1: # my-package)
# Modifies: pyproject.toml (removes [project.scripts])
# After this call, just init can safely run with no scaffolding in the tree
```

#### `_add_backend(package_path: Path) -> None`

A private helper that injects the FastAPI backend template into a cloned package, called only when `backend=True` in `init_new_package()`.

- **Purpose**: Called from `init_new_package()` after `_strip_scaffolding()` and before `_stage_injected_files()`, to inject the backend template files and their dependencies. Runs before `just init` so the injected files are seen by the rename sed and included in the initial git commit.
- **Parameters**:
  - `package_path: Path` — the root directory of the cloned package
- **Returns**: `None` (mutates the filesystem and pyproject.toml in place)
- **Behavior**:
  1. Calls `shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)` to copy the backend template tree into the clone root, merging into existing `<module>/` and `tests/` directories
  2. Calls `_append_backend_dependencies(package_path / 'pyproject.toml')` to inject runtime and dev dependencies
  3. Calls `_append_backend_recipes(package_path / 'Justfile')` to append migration recipes
- **Design rationale**:
  - Template is shipped as committed package data (via `[tool.hatch.build] include = ["backend_template/**"]`), not inline as string constants (keeps `main.py` lean)
  - Runs between `_strip_scaffolding` and `_stage_injected_files`, ensuring a clean ordering (remove scaffolding → inject backend → stage for rename → `just init`)
  - Tolerates absent `pyproject.toml` or `Justfile` (graceful boundary, like `_write_package_metadata`)

Examples:
```python
_add_backend(Path('/tmp/my_service'))
# Injects: modernpackage/app.py, modernpackage/db.py, modernpackage/health.py
#          tests/test_app.py, migrations/, alembic.ini, Containerfile, compose.yml, .dockerignore
# Modifies: pyproject.toml (adds backend deps), Justfile (adds migration recipes)
```

#### `_append_backend_dependencies(pyproject_path: Path) -> None`

A private helper that injects backend runtime and dev dependencies into a generated package's `pyproject.toml`.

- **Purpose**: Called by `_add_backend()` to populate `[project.dependencies]` with backend runtime deps and extend the dev group with `httpx` (required by FastAPI's TestClient).
- **Parameters**:
  - `pyproject_path: Path` — the path to the cloned package's `pyproject.toml` file
- **Returns**: `None` (mutates the file in place via TOML-safe string replacement)
- **Behavior**:
  1. Reads the file contents
  2. Replaces `dependencies = []` with `dependencies = [\n    "fastapi>=0.115",\n    "sqlalchemy[asyncio]>=2.0",\n    ...` (newline + indent per dep, matching TOML style)
  3. Replaces `dev = [\n` with `dev = [\n    "httpx",\n` (prepends httpx to the dev group)
  4. Writes the modified content back to the file
- **Graceful boundary**: If the file is missing or `dependencies = []` is not found, prints a notice to stderr and returns without raising
- **Design rationale**:
  - Uses surgical line-replacement (like `_remove_project_scripts`) rather than a full TOML parser, keeping changes minimal and verifiable in diffs
  - Deps are lower-bound-pinned only (`>=X.Y`), floating to latest available
  - `httpx` is dev-only (not a runtime dep), keeping the generated service's production image lean

#### `_append_backend_recipes(justfile_path: Path) -> None`

A private helper that appends migration recipes to a generated package's `Justfile`.

- **Purpose**: Called by `_add_backend()` to append `just migrate`, `just makemigration`, and `just migration-check` recipes (standalone, not part of `just check` chain).
- **Parameters**:
  - `justfile_path: Path` — the path to the cloned package's `Justfile`
- **Returns**: `None` (mutates the file in place via string concatenation)
- **Behavior**:
  1. Reads the file contents
  2. Appends `_BACKEND_RECIPES` constant (multiline string) to the end
  3. Writes the modified content back to the file
- **Graceful boundary**: If the file is missing, prints a notice to stderr and returns without raising
- **Design rationale**:
  - Appends (does not overwrite) to preserve existing recipes like `init`, `check`, `test`, etc.
  - Recipes use two-space indentation to match the template Justfile; `migrate: sync` pattern (dependency on `sync`) ensures the venv is up-to-date before running migrations

#### `_add_frontend(package_path: Path) -> None`

A private helper that injects the React frontend template into a cloned package, called only when `fullstack=True` in `init_new_package()`.

- **Purpose**: Called from `init_new_package()` after `_add_backend()` and before `_stage_injected_files()`, to inject the frontend template tree into a `frontend/` subdirectory. Runs before `just init` so the injected files are seen by the rename sed and included in the initial git commit. Adds NO Python dependencies (frontend is fully isolated).
- **Parameters**:
  - `package_path: Path` — the root directory of the cloned package
- **Returns**: `None` (mutates the filesystem and Justfile in place)
- **Behavior**:
  1. Calls `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True)` to copy the frontend template tree into the clone's `frontend/` subdirectory
  2. Calls `_append_frontend_recipes(package_path / 'Justfile')` to append Node recipes
- **Design rationale**:
  - Template is shipped as committed package data (via `[tool.hatch.build] include = ["frontend_template/**"]`), not inline as string constants (keeps `main.py` lean)
  - Frontend is isolated in a subdirectory to avoid polluting the Python package root (avoids import discovery, ruff/mypy/pytest collection, coverage gates)
  - Runs after `_add_backend` so the backend is always present when frontend is injected (frontend API client requires backend schema)
  - Tolerates absent `Justfile` (graceful boundary)
  - No subprocess calls and no npm invocation at scaffold time (frontend deps are installed separately via `just frontend-install`)

Examples:
```python
_add_frontend(Path('/tmp/my_app'))
# Injects: frontend/src/main.tsx, frontend/src/App.tsx, frontend/src/App.test.tsx
#          frontend/package.json, frontend/vite.config.ts, frontend/vitest.config.ts
#          frontend/tsconfig.json, frontend/eslint.config.js, frontend/openapi-ts.config.ts
#          frontend/src/client/ (pre-generated OpenAPI client)
# Modifies: Justfile (adds frontend recipes)
# Does NOT modify: pyproject.toml (no Python deps added)
```

#### `_append_frontend_recipes(justfile_path: Path) -> None`

A private helper that appends frontend build and test recipes to a generated package's `Justfile`.

- **Purpose**: Called by `_add_frontend()` to append Node.js recipes: `frontend-install`, `frontend-build`, `frontend-test`, `frontend-lint`, `generate-client`, and an aggregate `frontend-check` recipe (standalone, not part of Python `just check` chain).
- **Parameters**:
  - `justfile_path: Path` — the path to the cloned package's `Justfile`
- **Returns**: `None` (mutates the file in place via string concatenation)
- **Behavior**:
  1. Reads the file contents
  2. Appends `_FRONTEND_RECIPES` constant (multiline string) to the end
  3. Writes the modified content back to the file
- **Graceful boundary**: If the file is missing, prints a notice to stderr and returns without raising
- **Design rationale**:
  - Appends (does not overwrite) to preserve existing recipes like `init`, `check`, `test`, etc.
  - Recipes use two-space indentation to match the template Justfile
  - All recipes are scoped to the `frontend/` subdirectory via `cd frontend && ...` (no `: sync` dependency; that is a Python concept)
  - NOT chained into the root `check` recipe (keeps Python `just check` Node-free, matching backend-recipes precedent)
  - `frontend-check` aggregates frontend quality gates for convenience: `npm run format:check && npm run lint && npm run typecheck && npm run test`

#### `_stage_injected_files(package_path: Path) -> None`

A private helper that stages injected backend and frontend files so `just init`'s `git grep` sees them, called only when `backend=True` or `fullstack=True` in `init_new_package()`.

- **Purpose**: Called from `init_new_package()` immediately after `_add_backend()` (and optionally `_add_frontend()`) and before `just init`, to stage the injected files with `git add -A` so they are tracked and renamed by `just init`'s rename sed.
- **Parameters**:
  - `package_path: Path` — the root directory of the cloned package (the git working tree)
- **Returns**: `None` (runs `git add -A` subprocess and raises on failure)
- **Behavior**:
  1. Spawns `git add -A` via `Popen` with `cwd=package_path`
  2. Waits for completion via `communicate()` and captures stderr
  3. **If `returncode != 0`**: raises `RuntimeError` with message `'git add failed with exit code {returncode}: {stderr}'`
- **Design rationale**:
  - Injected template files carry the literal `modernpackage` token in imports and strings; staging ensures they are seen by `git grep -l 'modernpackage'` and renamed by the sed pass
  - Runs before `just init`, so the single git commit captures the clean, renamed tree
  - Subprocess seam mirrors existing `Popen` calls in `init_new_package` (tested via mock)

#### `_validated_or_error(parser: ArgumentParser, value: str | None, validator: Callable[[str], str]) -> str | None`

A private helper that validates a non-`None` value using a validator function, converting `ArgumentTypeError` to `parser.error()` for clean CLI error exits.

- **Purpose**: Used by `parse_args()` to validate email and repository URL values sourced from the environment, ensuring they follow the same rules as flag-supplied values. Routes validation failures through `parser.error()` so they exit cleanly (code 2) instead of raising a raw traceback.
- **Parameters**:
  - `parser: ArgumentParser` — the argument parser instance (used to call `parser.error()` on validation failure)
  - `value: str | None` — the value to validate (if `None`, returns `None` immediately)
  - `validator: Callable[[str], str]` — a validator function that either returns the input unchanged or raises `ArgumentTypeError` on validation failure
- **Returns**: `str | None` — the input value unchanged if it is `None` or validates successfully; does not return if validation fails (raises `SystemExit`)
- **Behavior**: If `value is not None`, calls `validator(value)`. If the validator raises `ArgumentTypeError`, catches it and calls `parser.error(error_message)`, which prints to stderr and raises `SystemExit(2)`. If the validator returns successfully, returns the validated value.

Examples:
- `_validated_or_error(parser, None, validate_author_email)` → `None` (no validation needed)
- `_validated_or_error(parser, 'a@b.co', validate_author_email)` → `'a@b.co'` (valid)
- `_validated_or_error(parser, 'nope', validate_author_email)` → raises `SystemExit(2)` with message `'Invalid author email: 'nope' — expected name@domain.tld'` printed to stderr

**Notes:**
- Re-validating a flag-supplied value (which was already validated by the `type=` handler at parse time) is idempotent and harmless, so validation may be applied uniformly to the final non-`None` value regardless of its source.
- `ArgumentParser.error()` is typed `NoReturn`, so mypy and ruff (`RET503`) remain clean (no explicit return needed after calling it).

#### `parse_args() -> Namespace`

Parses command-line arguments using `argparse.ArgumentParser`, applies environment variable defaults for omitted flags, applies git config defaults for certain omitted env vars, applies config file defaults as the weakest source, and validates email and URL values.

- **Arguments**:
  - `-v` / `--version`: optional flag (default `False`) — prints the package version and exits
  - `--dry-run`: optional flag (default `False`) — previews what scaffolding would do without making changes; prints a plan and exits
  - `--backend` / `--fastapi`: optional store-true flag (default `False`) — scaffolds a FastAPI backend service with async SQLAlchemy, migrations, and containerization
  - `--fullstack` / `--reactjs`: optional store-true flag (default `False`) — scaffolds both FastAPI backend (as above) and React frontend (Vite, Vitest, generated OpenAPI client) in isolated `frontend/` subdirectory
  - `package_name`: optional positional argument (validated via `validate_package_name`)
  - `--author-name`: optional flag (default `None`, free string, no validation). If omitted, falls back via the precedence ladder: `_environment_default(_AUTHOR_NAME_ENV)`, then `_git_config_default(_GIT_CONFIG_USER_NAME_KEY)`, then `_config_file_default(config, 'author_name')`.
  - `--author-email`: optional flag (default `None`, validated via `validate_author_email`). If omitted, falls back via the precedence ladder: `_environment_default(_AUTHOR_EMAIL_ENV)`, then `_git_config_default(_GIT_CONFIG_USER_EMAIL_KEY)`, then `_config_file_default(config, 'author_email')`, then validates via `_validated_or_error()`.
  - `--description`: optional flag (default `None`, free string, no validation). If omitted, falls back via: `_environment_default(_DESCRIPTION_ENV)`, then `_config_file_default(config, 'description')`.
  - `--license`: optional flag (default `None`, free string, no validation). If omitted, falls back via: `_environment_default(_LICENSE_ENV)`, then `_config_file_default(config, 'license')`.
  - `--repository-url`: optional flag (default `None`, validated via `validate_repository_url`). If omitted, falls back via: `_environment_default(_REPOSITORY_URL_ENV)`, then `_config_file_default(config, 'repository_url')`, then validates via `_validated_or_error()`.

- **Process**:
  1. **Parse**: creates `ArgumentParser`, defines all arguments with `default=None`, calls `parser.parse_args()` to get initial `Namespace`
  2. **Load config file**: calls `_load_config_file()` once to read the per-user TOML config file (missing file returns `{}` silently; malformed file prints a notice and returns `{}`)
  3. **Environment fallback**: for each of the five metadata fields, if the namespace value is `None` (flag was omitted), substitutes the environment variable value via `_environment_default()`
  4. **Git config fallback** (for `author_name` and `author_email` only): if the value is still `None` after the environment fallback, consults git config via `_git_config_default()` to establish the first layer of the precedence ladder
  5. **Config file fallback**: if the value is still `None` after the previous step, consults the config file mapping via `_config_file_default(config, key)` to establish the weakest fallback source
  6. **Validate**: for email and repository URL, calls `_validated_or_error()` to validate the final (possibly env-sourced, git-config-sourced, or config-file-sourced) value; invalid values exit cleanly with code 2 and a CLI-style error message instead of a traceback
  7. **Return**: returns the fully resolved namespace

- **Returns**: `Namespace` — an `argparse.Namespace` object with fields:
  - `version` (bool) — whether `--version` was provided
  - `dry_run` (bool) — whether `--dry-run` was provided
  - `backend` (bool) — whether `--backend` or `--fastapi` was provided (scaffolds FastAPI backend)
  - `fullstack` (bool) — whether `--fullstack` or `--reactjs` was provided (scaffolds FastAPI backend + React frontend)
  - `package_name` (str | None) — the package name (from flag or `None`)
  - `author_name` (str | None) — author name (from flag, env var, git config, config file, or `None`)
  - `author_email` (str | None) — author email (from flag, env var, git config, config file, or `None`, validated)
  - `description` (str | None) — description (from flag, env var, config file, or `None`)
  - `license` (str | None) — license identifier (from flag, env var, config file, or `None`)
  - `repository_url` (str | None) — repository URL (from flag, env var, config file, or `None`, validated)

**Precedence for `author_name` and `author_email`**: **flag > env > git config > config file > None**. For other fields, precedence is **flag > env > config file > None** (no git config fallback).

**Git config fallback**: When both flag and environment variable are absent, `author_name` and `author_email` fall back to the user's git config (`user.name` and `user.email` respectively), reading the merged (local-over-global) configuration. Git config values flow through the same validation as env values: email addresses must match the basic email pattern, or the command exits with code 2 and a CLI error.

**Config file fallback**: When flag, environment variable, and (for author fields) git config are all absent or empty, all five metadata fields consult the per-user TOML config file via `_config_file_default()`. A missing config file (or a file missing a key) is silent. A malformed or unreadable file prints a notice to stderr and continues with `None` for that field.

**Empty environment variables**: An environment variable set to an empty string (`''`) is treated as unset and returns `None`, allowing the next fallback level (git config, config file, or `None`) to be consulted.

**Complexity**: The function has a McCabe cyclomatic complexity of ≤ 10 (enforced by `pyproject.toml:tool.ruff.lint.mccabe.max-complexity`), with the validation logic extracted into the `_validated_or_error()` helper and the config file helpers extracted into `_load_config_file()` and `_config_file_default()` to keep the post-parse block clear and maintainable.

#### `init_new_package(package_name: str, *, author_name: str | None = None, author_email: str | None = None, description: str | None = None, package_license: str | None = None, repository_url: str | None = None, dry_run: bool = False, backend: bool = False, fullstack: bool = False) -> int`

Orchestrates the package initialization flow by cloning, rewriting, and validating. Uses `normalize_module_name` to derive the import-safe directory name from the user-provided distribution name. When `dry_run=True`, prints a preview plan, then exits without cloning or making any changes. When `backend=True`, injects a FastAPI backend template with async SQLAlchemy, health probes, and containerization. When `fullstack=True`, injects both the FastAPI backend and a React frontend (Vite, Vitest, OpenAPI client) in an isolated `frontend/` subdirectory.

1. **Positional Parameter**: `package_name: str` — name of the new package to create (validated distribution name, may contain `.` or `-`)
2. **Keyword Parameters** (optional, all default to `None` or `False`):
   - `author_name: str | None = None` — author name to include in the package metadata (free string, not yet written to files)
   - `author_email: str | None = None` — author email to include in the package metadata (validated via `validate_author_email`, not yet written to files)
   - `description: str | None = None` — package description to include in metadata (free string, not yet written to files)
   - `package_license: str | None = None` — license identifier to include in metadata (free string, not yet written to files)
   - `repository_url: str | None = None` — repository URL to include in metadata (validated via `validate_repository_url`, not yet written to files)
   - `dry_run: bool = False` — if `True`, preview what scaffolding would do without making changes (no clone, no directory creation)
   - `backend: bool = False` — if `True`, injects a FastAPI backend template with app factory, async DB layer, health probes, Alembic migrations, and containerization (Containerfile, Docker Compose)
   - `fullstack: bool = False` — if `True`, injects both the FastAPI backend (as above) and a React frontend (Vite, Vitest, OpenAPI client) in isolated `frontend/` subdirectory; `backend` is a subset of `fullstack` so when both are provided, `fullstack` takes precedence
3. **Returns**: `int` — exit code (0 on success, 1 if `just check` fails, or 0 if dry-run succeeds)

**Metadata writing**: The metadata parameters are automatically written to the generated package's `pyproject.toml` file via `_write_package_metadata()`, called after the successful clone and before `just init`. This ensures the metadata is included in the package's initial git commit.
3. **Derivation**: Converts the package name to a module name:
   ```python
   module_name = normalize_module_name(package_name)
   ```
   For example, if the user provides `my-cool.package`, the derived `module_name` is `my_cool_package`.
4. **Process**:
   - Resolves target path using the module name: `Path.cwd() / module_name`
   - **Step 0: Dry-run short-circuit** — **If `dry_run=True`**: calls `_print_dry_run_plan()` to print a high-level preview plan to stdout, then returns `0` immediately without proceeding to the clone. The plan includes the target directory, template URL, per-field metadata substitutions (showing which fields have values and which keep the template default), and the well-known `just init` outcomes (rename `modernpackage/ → <module>/`, version reset to `0.0.1`). No directory is created, no clone occurs, and no other subprocess is spawned.
   - **Step 1: Clone** — Spawns `git clone https://github.com/albertas/modernpackage <module_name>` via `Popen` with `stderr=PIPE` (target directory uses underscores, not hyphens/dots)
     - Waits for completion via `communicate()` and captures both stdout and stderr
     - **If `returncode != 0`**: calls `humanize_git_clone_error(decoded stderr)` to map common failure patterns to friendly messages; raises `RuntimeError` with either:
       - `'{friendly message}\n\ngit clone failed with exit code {returncode}: {decoded stderr}'` if a known pattern is found, or
       - `'git clone failed with exit code {returncode}: {decoded stderr}'` as fallback for unknown errors
   - **Step 2: Write metadata** — **If clone succeeds (`returncode == 0`)**: calls `_write_package_metadata()` to write user-supplied metadata into the package's `pyproject.toml`. All non-`None` values are applied as targeted TOML-escaped substitutions of known template placeholders; `None` values are skipped. If the `pyproject.toml` file is missing, a notice is printed to stderr and the step continues without raising.
   - **Step 3: Strip scaffolding** — **After metadata writing**: calls `_strip_scaffolding()` to remove the scaffolder's own machinery from the cloned tree. This deletes the scaffolder CLI (`main.py`), its tests (`test_e2e.py`), documentation (`docs/`), and project-metadata files (`BACKLOG.md`); replaces the test suite with a minimal stub; replaces the README with a generic template; and removes console-script entry points. Also ensures the cloned `backend_template/` directory is removed (present in the clone by default but always stripped, so the no-flag output remains byte-for-byte identical). Runs **before** `just init` so the single git commit captures a clean tree. Missing paths are tolerated (graceful degradation for variant template shapes).
   - **Step 4: Inject backend and/or frontend (if requested)** — **If `backend=True` or `fullstack=True`**: after stripping, calls `_add_backend()` to inject the FastAPI backend template. This copies the committed `backend_template/` directory (from the installed package or source checkout) into the clone root, merges FastAPI, SQLAlchemy, asyncpg, alembic, and uvicorn runtime dependencies into `[project.dependencies]`, appends the test-only `httpx` dependency to the dev group, and appends migration recipes (`just migrate`, `just makemigration`, `just migration-check`) to the clone's `Justfile`.
     — **Additionally, if `fullstack=True`** (and the backend was just injected): calls `_add_frontend()` to inject the React frontend template. This copies the committed `frontend_template/` directory (from the installed package or source checkout) into `frontend/` subdirectory, appending frontend recipes (`just frontend-install`, `just frontend-build`, `just frontend-test`, `just frontend-lint`, `just generate-client`, `just frontend-check`) to the clone's `Justfile`. Frontend is isolated in a subdirectory and adds NO Python dependencies.
     — After all injections complete, calls `_stage_injected_files()` to run `git add -A` so the injected files (which carry the literal `modernpackage` token) are staged and seen by `just init`'s rename sed. If both `backend=False` and `fullstack=False`, this step is skipped and the output is byte-for-byte identical to today.
   - **Step 5: Initialize** — **After backend injection (if any)**: continues to spawn `just init <module_name>` (cwd: the cloned directory, using the normalized module name) with `stderr=PIPE`
     - Wraps the `just init` `Popen` call in a `try`/`except FileNotFoundError` block:
       - **If `FileNotFoundError` is raised**: catches the exception and raises `RuntimeError` with an actionable message: `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`
       - **If `Popen` succeeds**: waits for completion via `communicate()` and captures both stdout and stderr
         - **If `returncode != 0`**: raises `RuntimeError` with message `'just init failed with exit code {returncode}: {decoded stderr}'`
         - **If `returncode == 0`**: continues to Step 6
   - **Step 6: Compile** — **If Step 5 succeeds**: spawns `just compile` (cwd: the cloned directory) via `Popen` to regenerate the `uv.lock` file, incorporating all cloned and injected dependencies
     - Does not capture stdout/stderr; inherits parent streams so compilation progress is visible to the user
     - Spawns the subprocess and waits for completion via `communicate()`
       - **If `returncode != 0`**: prints error message to stderr and raises `RuntimeError` with message `'compile failed with exit code {returncode}: {decoded stderr}'`
       - **If `returncode == 0`**: continues to Step 7
   - **Step 7: Sync** — **If Step 6 succeeds**: spawns `just sync` (cwd: the cloned directory) via `Popen` to create the virtual environment and install locked dependencies
     - Does not capture stdout/stderr; inherits parent streams so sync progress is visible to the user
     - Spawns the subprocess and waits for completion via `communicate()`
       - **If `returncode != 0`**: prints error message to stderr and raises `RuntimeError` with message `'sync failed with exit code {returncode}: {decoded stderr}'`
       - **If `returncode == 0`**: continues to Step 8
   - **Step 8: Validate** — **If Step 7 succeeds**: runs `just check` (cwd: the cloned directory) via `Popen` and reports the outcome using the module name
     - Does not capture stdout/stderr; inherits parent streams so check progress is visible to the user
     - Spawns the subprocess and waits for completion via `communicate()`
     - **If `returncode == 0`**: prints a success message to stdout: `'just check passed — {module_name} scaffold is valid.'` (using the normalized module name), then calls `_print_init_summary(package_name, new_package_path)` to print a summary block showing the created package name, directory path, and reset version (`_RESET_VERSION`), then returns `0`
     - **If `returncode != 0`**: prints a failure message to stderr: `'just check failed with exit code {returncode} — review the output in {module_name}.'` (using the normalized module name) and returns `1`
     - Does not raise an error on non-zero exit code; `just check` failure is reported but does not block the function; the failure is propagated via the return code instead

Error messages include the decoded stderr output, providing visibility into the root cause of subprocess failures (e.g., network errors, missing commands, permission issues). The `git clone` error path is enhanced with pattern-matched, human-readable explanations of common failure modes. The `just init` missing-command error path is caught at the point of spawning the subprocess, before any execution attempts, and provides a clear, actionable installation instruction.

The `just init` recipe (in the cloned repo) performs the actual transformation on the already-stripped tree:
- Renames all "modernpackage" occurrences to the new package name (including the stub test and README files)
- Resets the version to `0.0.1`
- Renames the package directory (`modernpackage/` → `<name>/`)
- Reinitializes git (clears `.git`, runs `git init`, commits the clean initial state)

The `just check` recipe (in the cloned repo) validates the newly scaffolded package by running all quality gates: format check, ruff lint, complexity audit, mypy type check, unit tests, pip-audit security scan, and deadcode detection. At this point, the generated package contains only a minimal stub test (imported once to satisfy coverage requirements) and a generic README, with no scaffolder CLI, documentation, or test-suite code.

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
  1. Calls `parse_args()` to get user input (including the `--dry-run`, `--backend`, and metadata flags)
  2. **If** `version` flag is set: prints `modernpackage <__version__>` and returns `0`
  3. **Elif** `package_name` is provided:
     - Calls `init_new_package()` with the package name, all metadata keyword arguments, the `dry_run` flag, and the `backend` flag inside a `try`/`except RuntimeError` block:
       ```python
       init_new_package(
           package_name=parsed_args.package_name,
           author_name=parsed_args.author_name,
           author_email=parsed_args.author_email,
           description=parsed_args.description,
           package_license=parsed_args.license,
           repository_url=parsed_args.repository_url,
           dry_run=parsed_args.dry_run,
           backend=parsed_args.backend,
       )
       ```
     - **If** `RuntimeError` is raised: catches it, prints the error message to `sys.stderr` (which includes captured stderr from the failed subprocess), and returns `1`
     - **If** no error: returns the value from `init_new_package()` (which is `0` if `just check` passed, `1` if it failed, or `0` if dry-run succeeded)
  4. **Else**: silent no-op (no error, no message) and returns `0`

The error handling ensures that subprocess failures (from `git clone` or `just init`) are surfaced to the user as clean, readable messages on stderr instead of Python tracebacks. The returned exit code is translated to the process exit status by the console script wrapper (which calls `sys.exit(main())`), allowing shell scripts and CI/CD pipelines to detect failures properly. Validation failures (from `just check`) are now also reflected in the process exit code.

The metadata keyword arguments are passed through even though they are not yet written to files, establishing the plumbing for later V4 work that will perform the actual substitution in `pyproject.toml`.

## Type Annotations & Mypy Verification

### Full Type Coverage

All public functions in `modernpackage/main.py` carry complete type annotations:

- **`validate_package_name(value: str) -> str`** — parameter and return types specified (validation-only, returns input unchanged)
- **`validate_author_email(value: str) -> str`** — parameter and return types specified (validation-only, returns input unchanged)
- **`validate_repository_url(value: str) -> str`** — parameter and return types specified (validation-only, returns input unchanged)
- **`normalize_module_name(value: str) -> str`** — parameter and return types specified (pure string transform)
- **`parse_args() -> Namespace`** — return type specified (no parameters)
- **`init_new_package(package_name: str, *, author_name: str | None = None, author_email: str | None = None, description: str | None = None, package_license: str | None = None, repository_url: str | None = None) -> int`** — all parameter types and return type specified
- **`main() -> int`** — return type specified (no parameters)

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
- `modernpackage/main.py` — CLI orchestrator with 6 public functions and 7 private helpers:
  - Public validators: `validate_package_name`, `validate_author_email`, `validate_repository_url`
  - Public utilities: `normalize_module_name`, `parse_args`, `init_new_package`, `main`
  - Private helpers: `_explain_invalid_package_name`, `humanize_git_clone_error`, `_toml_escape`, `_write_package_metadata`, `_apply_license`, `_strip_scaffolding`, `_remove_project_scripts`
- `tests/__init__.py` — test package marker
- `tests/test_main.py` — comprehensive test suite (including tests for validators, normalization, metadata writing, scaffolding removal, and integration)

Result: `Success: no issues found in 4 source files`

This ensures all code paths are covered by type hints and comply with strict type-checking rules.

## Build & Versioning

### Build Configuration

- **Build backend**: `hatchling` (modern, minimal Python build system)
- **Package files**: includes `**/*.py`, `backend_template/**`, `frontend_template/**`, excludes `tests/**`, `frontend_template/node_modules/**`, `frontend_template/dist/**`
  - `backend_template/` is shipped as package data and copied into generated packages when `--backend` is set
  - `frontend_template/` is shipped as package data and copied into generated packages when `--fullstack` is set
  - Excluding `frontend_template/node_modules/` and `frontend_template/dist/` keeps the wheel size small (no npm lock file artifacts or build outputs in the distribution)
  - The scaffolder's `pyproject.toml` excludes `frontend_template/**` from ruff linting (no `.py` files, but explicit ignore for INP001 defensiveness)
- **Version source**: dynamic, read from `modernpackage/__init__.py` at build time (no hard-coded version in `pyproject.toml`)
- **Python requirement**: `>= 3.14`
- **Runtime dependencies**: none (empty list)
- **Test dependencies**: ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi (with a minimum version floor for the constrained package)

### Publishing

`just publish` automates the release workflow: it bumps the patch version component of `__version__` in `modernpackage/__init__.py` via `just bump`, commits the version file to git with a message that includes the new version (e.g., "Bump version to 0.0.13"), pushes the commit to the remote repository, clears `dist/`, builds via `uv build`, and publishes via `uv publish`. This ensures that every published package has a unique, incremented version and that the pushed repository contains the released code with the matching version.

The `just bump` recipe can also be invoked standalone to increment the patch version without publishing (e.g., for testing or manual version control). It uses POSIX shell arithmetic and GNU sed to extract the current version, compute the new patch component, and rewrite the version line in place.

### Dependency Locking

The project uses uv's native lockfile as the single source of truth for dependency pins:

- **`uv.lock`**: generated via `uv lock --upgrade` to pin all transitive dependencies (runtime and the `dev` group).

The `Justfile` defines a `lock` recipe whose body is `uv lock --upgrade`. `uv sync` installs the project and the `dev` group directly from `uv.lock`. The lock recipe resolves against the private GitLab uv index configured in `pyproject.toml`, which may lag behind PyPI; the resolved versions are capped by what that index serves.

## Configuration Hub

### `pyproject.toml`

Single unified configuration file for all tools:

- **`[project]`**: package metadata, entry points (`modernpackage` and `mp`); the `dev` dependency group is declared under `[dependency-groups]`
- **`[tool.pytest.ini_options]`**: test runner config
  - `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`
  - Measures coverage against the `modernpackage` package only (excludes `tests/`)
  - Fails if coverage is below 95%
  - Default run excludes `e2e` marked tests (mocked unit tests only)
  - `markers` lists registered markers: `e2e` (tests that perform real external calls)
  - `norecursedirs = ["backend_template", "frontend_template"]` — excludes the template directories from pytest's test collection and discovery
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

- **`sync`**: installs the project and locked `dev` group from `uv.lock` via `uv sync` (required by most recipes as a prerequisite)
- **`lock`**: refreshes `uv.lock` to the latest resolvable versions via `uv lock --upgrade`
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

All tools read their configuration from `pyproject.toml`. The Justfile delegates to them via `uv run`, which manages the virtual environment and dependency versions (pinned in `uv.lock`).

## Test Strategy

### Test Coverage Goal

**95% coverage of `modernpackage/` source** — all code paths must be exercised with deterministic, mocked, parallel tests.

### Parallelism & Determinism

Tests run in parallel across `nproc --ignore=1` CPU cores using `pytest-xdist`. All tests are:
- **Independent**: no shared state or ordering dependencies between tests
- **Mocked**: all external effects (subprocess, network, filesystem) are mocked at the seam
- **Deterministic**: coverage aggregates transparently across workers; final coverage measurement is deterministic despite parallel execution

### Test Organization

Tests live in `tests/test_main.py` (mocked unit tests) and `tests/test_e2e.py` (end-to-end test) using:

- Plain `def test_*` functions (no test classes)
- `unittest.mock.patch` for dependency injection (mocking `ArgumentParser`, `print`, `Popen`, etc.)
- `pytest.raises` for exception testing
- Unit tests (`tests/test_main.py`): no real subprocess/network calls; all external dependencies mocked
  - Includes dedicated tests for metadata writing helpers: `test_write_package_metadata_replaces_all_fields`, `test_write_package_metadata_none_is_noop`, `test_write_package_metadata_missing_file`, `test_write_package_metadata_escapes_quotes`, `test_write_package_metadata_writes_license`, `test_write_package_metadata_none_license_keeps_classifier`
  - Tests verify TOML correctness by parsing results with `tomllib.loads()` to ensure generated TOML is valid
- End-to-end tests (`tests/test_e2e.py`): real subprocess calls, network access, filesystem operations
  - Includes assertions that verify on-disk `pyproject.toml` contains supplied metadata values after scaffolding

### Test Markers

The `e2e` marker is registered in `pyproject.toml` to categorize tests:

- **`e2e`**: marks tests that perform real external calls (network, subprocess, filesystem). These are excluded from the default `just test` run (which runs only mocked unit tests) and are reserved for an explicit `just test-e2e` invocation. Pre-registering the marker prevents future `filterwarnings = error` strictness from breaking on unregistered marker usage.

### End-to-End Tests: Scaffolding Validation

The e2e tests (`tests/test_e2e.py`, marked with `@pytest.mark.e2e`) validate different scaffolding configurations by cloning the local template, running `just init`, and verifying the generated packages pass their respective test suites. There are currently four e2e tests:

#### No-Flag Scaffold: `test_scaffolded_package_passes_check`

Validates the core no-flag scaffolding workflow:

1. **Skipping gracefully** if required tools are missing: checks `git`, `just`, and `uv` are on `PATH`; skips the test with a diagnostic message if any are missing
2. **Cloning the local template** from the repo root into a temporary directory (intentionally **not** the GitHub URL, so local template regressions are caught)
3. **Writing metadata** to the cloned package's `pyproject.toml` (author name/email, description, license, repository URL) before stripping
4. **Stripping scaffolding** via `_strip_scaffolding()` to remove scaffolder machinery (`main.py`, tests, docs, entry points) and operational artifacts (`errors/`, `issues/`, `workspace/`, `metrics.yml`), and to re-seed `lifecycle_state.yml` with a fresh `code_quality_is_good: true` stub
5. **Running `just init <package_name>`** to replicate the package (rename all "modernpackage" occurrences, reset version to `0.0.1`, reinitialize git)
6. **Verifying the result** by checking that the renamed `__init__.py` file exists and contains the pinned version `0.0.1`, and that all scaffolding has been removed:
   - Scaffolder CLI (`modernpackage/main.py`) is absent
   - Scaffolder tests (`tests/test_e2e.py`, `tests_e2e/`) are absent
   - Documentation (`docs/`) is absent
   - Project metadata (`BACKLOG.md`) is absent
   - Entry points are removed from `pyproject.toml`
   - Template remnants (`backend_template`, `frontend_template`) are absent
   - **Operational/process artifacts** (`errors/`, `issues/`, `workspace/` directories and `metrics.yml` file) are absent — verifying that the scaffolder's own vupi lifecycle state does not leak into generated packages; `lifecycle_state.yml` is instead re-seeded with a fresh `code_quality_is_good: true` stub
7. **Validating metadata** by checking that the supplied metadata values are correctly written to the generated `pyproject.toml`
8. **Validating all quality gates** by running `just check` against the scaffolded package and asserting exit code 0 (passes format, lint, complexity, typecheck, unit tests, security audit, dead code detection)

#### Backend Scaffold: `test_scaffolded_backend_package_passes_check`

Validates `--backend`/`--fastapi` scaffolding workflow, similar to the no-flag test but with backend injection:

1. Same clone, metadata, strip, init steps as the no-flag test
2. **Injects backend** via `main._add_backend()` after stripping
3. **Stages injected files** via manual `git add -A` (this test predates the internal staging in `_inject_templates`)
4. **Runs `just check`** and asserts backend passes all quality gates
5. **Verifies backend artifacts**: `app.py` and `health.py` exist in the package source, token "modernpackage" is absent from all source files, health probes are present (`/readyz` endpoint), migration recipes exist in `Justfile`, Alembic config files exist, and containerization (Containerfile, Docker Compose) is present

#### Fullstack Scaffold: `test_scaffolded_fullstack_package_passes_check`

Validates `--fullstack`/`--reactjs` scaffolding workflow, running both backend and frontend test suites:

1. Same clone, metadata, strip steps as the no-flag test
2. **Injects fullstack** via `main._inject_templates(destination, fullstack=True)` which automatically stages via internal `_stage_injected_files` call
3. **Runs `just init`** to replicate the package (no manual git staging needed due to internal staging in `_inject_templates`)
4. **Validates backend** by running `just check` and asserting exit code 0 (pytest passes)
5. **Installs frontend** via `just frontend-install` (runs `npm ci` to install Node dependencies)
6. **Runs frontend tests** via `just frontend-test` (runs `vitest run` for React component tests)
7. **Verifies structural expectations**: 
   - Backend source files present (`app.py`, `health.py`)
   - Frontend directory exists (`frontend/` is a directory)
   - Frontend recipes injected in generated `Justfile` (`frontend-install`, `frontend-test`, `frontend-check`)
   - Frontend recipes excluded from `check` chain (important because CI has no Node)
   - Token "modernpackage" renamed in frontend files (`frontend/package.json`, `frontend/src/App.test.tsx`)

**Graceful skipping for fullstack test**: Additionally requires `npm` on `PATH` for frontend test execution. When `npm` is unavailable (CI environments), the fullstack test skips while other e2e tests run.

#### Fullstack Runtime Integration: `test_fullstack_package_runs_end_to_end`

Validates that a scaffolded fullstack application runs end-to-end in a real Docker Compose stack and exercises the backend↔frontend integration path. This test goes beyond structural validation by running the complete application stack and testing real HTTP endpoints, API client generation, and frontend builds:

1. **Setup**: Same clone, metadata, strip, fullstack-inject, and init steps as the fullstack scaffold test
2. **Compose up & wait**: Brings the stack up via `compose up -d --build`, then polls `/readyz` until it returns HTTP 200:
   - `db` service (Postgres 17) starts
   - `migrate` service (Alembic) runs migrations
   - `app` service (uvicorn with FastAPI factory) starts
   - The `_wait_for_ready()` helper polls `http://127.0.0.1:8000/readyz` with a 120-second deadline, catching connection-level errors (port refuses early connections), sleeping 2 seconds between polls, and failing loudly if the timeout elapses. A green `/readyz` response (HTTP 200) indicates the app is healthy with a live database connection and applied migrations
3. **Backend HTTP assertions**: With the stack live, makes real HTTP requests from the test host:
   - `GET http://127.0.0.1:8000/livez` returns 200 with `{"status":"pass"}` (liveness check)
   - `GET http://127.0.0.1:8000/readyz` returns 200 (readiness check with live DB)
4. **Frontend installation**: Installs Node dependencies via `just frontend-install` (runs `npm ci`)
5. **API client regeneration**: With the backend still running, runs `just generate-client` to regenerate the OpenAPI client:
   - The `@hey-api/openapi-ts` generator fetches the live `http://localhost:8000/openapi.json` (not the committed snapshot)
   - Rewrites `frontend/src/client/` with real operation types and client stubs
   - Asserts the regenerated client contains operation names (`livez`, `readyz`) and is no longer the hand-written placeholder
6. **Frontend build**: Runs `just frontend-build` to compile the frontend against the regenerated client:
   - TypeScript type-checks pass against the real client types
   - Vite bundles the application to `frontend/dist/`
   - Asserts `frontend/dist/index.html` exists and is non-empty
7. **Teardown**: Always runs `compose down -v` in `try/finally` to:
   - Stop all containers
   - Remove the `pgdata` volume (prevents port/volume leakage between test runs)
   - Free port 8000 for subsequent test runs

**Graceful skipping**: Requires `docker compose` or `podman compose` or `podman-compose` on `PATH` (auto-detected), plus `npm`, plus the Python test tools. When any required tool is missing, skips cleanly instead of failing. Compose command auto-detection tries `docker compose`, then `podman compose`, then `podman-compose` (the portability set named in `backend_template/compose.yml:1`).

**Caveats**: This test pulls `postgres:17`, builds the application image, and runs `npm ci` + `vite build`, which takes several minutes and requires network access. It is excluded from `just check` (default quality gate) and requires explicit `just test-e2e` invocation. The test documents its runtime cost and skip conditions in the test docstring (matching the module docstring at lines 1–15) so developers understand why it might be slow or skipped in their environment.

**What it guarantees**: The scaffolded fullstack application is genuinely functional end-to-end: the compose stack brings up a real Postgres database with applied migrations, the FastAPI backend responds to health probes with a real database connection, the generated OpenAPI schema is consistent with the running backend, the frontend can be rebuilt against live schema, and TypeScript compilation succeeds against the generated client types. This is complementary to `test_scaffolded_fullstack_package_passes_check`, which validates file structure and unit tests; together they cover structural correctness, unit test execution, and end-to-end integration.

#### Backend Runtime Integration: `test_backend_package_runs_end_to_end`

Validates that a scaffolded backend-only application runs end-to-end in a real Docker Compose stack with a live Postgres database, exercising the complete migration workflow. This test verifies the backend bootstrapping process independently, without frontend complexity, ensuring that database health checks and schema changes work in a production-like environment.

**Location**: `tests_e2e/test_backend_e2e.py` (standalone directory with shared helper module `tests_e2e/_scaffold.py`)

**Test flow** (three phases, all in a single test function):

1. **Phase 1 — Scaffold backend-only package**: Scaffolds a backend-only package from the local checkout using proven helper functions:
   - Clones the local template repository into a temporary directory
   - Writes metadata (author, description, license, repository URL)
   - Strips scaffolder machinery (`main.py`, scaffolder tests, `docs/`, `BACKLOG.md`)
   - Injects the backend via `_add_backend()` (FastAPI, async SQLAlchemy, Alembic)
   - Stages injected files with `git add -A`
   - Runs `just init <module_name>` to rename "modernpackage" tokens and make the initial commit
   - **Assertion**: Backend-only layout verified — `app.py`, `db.py`, `health.py`, `compose.yml`, `alembic.ini`, `migrations/env.py`, and Justfile recipes are present; "modernpackage" token is absent from all source files

2. **Phase 2 — Bring stack up and assert health**:
   - Exposes the generated `db` service port to the host by appending `ports: ["127.0.0.1:5432:5432"]` to the ephemeral copy's `compose.yml` (design decision: modifies only the test's temporary copy, not the template)
   - Runs `compose up -d --build` to bring the stack up, then polls `/readyz` until it returns HTTP 200
   - Detects the compose command (probes `docker compose` → `podman compose` → `podman-compose`, skips if none found)
   - Uses the `_wait_for_ready()` helper to poll `http://127.0.0.1:8000/readyz` with a 120-second deadline, catching connection-level errors, sleeping 2 seconds between polls, and failing loudly if the timeout elapses. This backend-agnostic approach replaces docker-only `--wait` and works with both docker and podman
   - **Assertions**: Pre-migration health probes pass:
     - `GET http://127.0.0.1:8000/livez` returns 200 (liveness)
     - `GET http://127.0.0.1:8000/readyz` returns 200 (readiness with live Postgres and applied base schema)

3. **Phase 3 — Register a model, generate and apply a real migration, re-probe readiness**:
   - Appends a `Product` SQLAlchemy 2.0 model to the generated `module/db.py` with `Mapped` columns and deterministic naming convention support
   - Runs `just makemigration "add products"` and `just migrate` host-side with an explicit `DATABASE_URL` pointing to the exposed Postgres (design decision: Justfile recipes don't set `DATABASE_URL`, so the test injects it via environment)
   - **Assertions**:
     - At least one version file in `migrations/versions/` contains `create_table('products')` (proves autogenerate ran and produced the expected operation)
     - `GET http://127.0.0.1:8000/readyz` still returns 200 post-migration (proves the database remains responsive after schema change — the task's core requirement)
   - **Teardown**: Always runs `compose down -v` in `try/finally` to stop containers, remove the `pgdata` volume (preventing leakage between test runs), and free port 8000

**Shared helper module** (`tests_e2e/_scaffold.py`):
- Mirrors proven infra from `tests/test_e2e.py` (subprocess runner, compose detection, HTTP prober, git identity env) to avoid cross-test imports
- Exports `scaffold_backend_package(tmp_path) -> (destination, module_name)` to encapsulate the clone → metadata → strip → backend-inject → stage → init flow
- Exports `_expose_db_port(destination)` to modify the ephemeral compose.yml's `db` service
- Exports `_register_product_model(source_dir)` to append the Product model to the generated `db.py`
- Exports constants: `REPO_ROOT` (resolves to repo root from `tests_e2e/_scaffold.py`'s parent), `REQUIRED_TOOLS` (git, just, uv), `_HOST_DATABASE_URL` (postgresql+asyncpg connection string to localhost:5432)

**Graceful skipping**: Requires `git`, `just`, `uv` on `PATH` for scaffolding and testing; additionally requires a compose command (`docker compose`, `podman compose`, or `podman-compose`) for stack operations. The test skips cleanly with a diagnostic message if any required tool is missing. Compose command auto-detection tries the portability set in precedence order.

**Caveats**: This test pulls `postgres:17`, builds the application image, runs `uv sync` and `alembic` operations (which pull asyncpg and other deps), and makes real HTTP requests to a running stack. It takes several minutes and requires network access. It is excluded from `just check` (default quality gate) and requires explicit `just test-e2e` invocation.

**What it guarantees**: A scaffolded backend-only application is genuinely functional end-to-end: the compose stack brings up a real Postgres database with applied base schema, the FastAPI backend responds to health probes with a real database connection, host-side migration tools can connect to the exposed Postgres, new models can be registered and migrated via the scaffold's own `just makemigration` and `just migrate` targets, and the readiness probe remains healthy after schema changes. This complements `test_scaffolded_backend_package_passes_check` (structural validation and unit test execution) by verifying actual runtime behavior with a real database.

#### Fullstack Feature Integration: `test_fullstack_feature_runs_end_to_end`

Validates that a scaffolded fullstack application can host a database-backed feature working end-to-end: model → migration → backend API endpoints → HTTP round-trip → browser rendering. This test goes beyond the existing fullstack runtime test by exercising feature injection, database operations, and complete frontend-to-backend data flow through browser automation.

**Location**: `tests_e2e/test_fullstack_feature_e2e.py` (standalone test file with shared helpers in `tests_e2e/_scaffold.py`)

**Test flow** (three phases, all in a single test function):

1. **Phase 1 — Scaffold fullstack package with feature framework**:
   - Clones the local template repository into a temporary directory
   - Writes metadata (author, description, license, repository URL)
   - Strips scaffolder machinery (`main.py`, scaffolder tests, `docs/`, `BACKLOG.md`)
   - Injects the fullstack via `main._inject_templates(destination, fullstack=True)` (backend + frontend templates with recipes)
   - Registers a products feature page by overwriting `frontend/src/App.tsx` with a version that:
     - Preserves the shipped health status display (so `status.spec.ts` still passes)
     - Adds a products section that fetches `/api/products` on mount and renders product names in a `<ul>`
   - Writes a Playwright spec `frontend/e2e/products.spec.ts` that asserts the seeded product name is visible
   - Stages files with `git add -A`
   - Runs `just init <module_name>` to rename "modernpackage" tokens and make the initial commit
   - **Assertions**: Fullstack layout verified — `app.py`, `db.py`, `frontend/src/App.tsx`, `frontend/playwright.config.ts`, and Justfile recipes are present; "modernpackage" token is absent from all Python source files

2. **Phase 2 — Register products feature and exercise backend API**:
   - Injects the `Product` SQLAlchemy model into the generated `module/db.py` by appending model definition
   - Writes `products.py` router with:
     - `GET /api/products` to list all products as JSON array
     - `POST /api/products` to create a new product (accepts `{"name": "..."}`, returns the created row with `id` and `name`)
     - Both endpoints use async SQLAlchemy with the scaffold's `DbSessionDep` (dependency injection)
   - Wires the router into `app.py` by editing it to import and include the products router under `/api` prefix (asserts anchors before replacing)
   - Detects the compose command (auto-detects `docker compose` → `podman compose` → `podman-compose`, skips if none found)
   - Exposes the generated `db` service's port 5432 to the host so host-side migration tools can reach Postgres
   - Brings up the stack via `compose up -d --build`, then polls `/readyz` until it returns HTTP 200 (builds the app image with injected model + router, starts Postgres, runs migrations)
   - Uses the `_wait_for_ready()` helper to poll `http://127.0.0.1:8000/readyz` with a 120-second deadline, replacing docker-only `--wait` with a backend-agnostic approach that works with both docker and podman
   - **Assertions**:
     - `GET http://127.0.0.1:8000/livez` returns 200 (liveness)
     - `GET http://127.0.0.1:8000/readyz` returns 200 (readiness with live Postgres)
   - Registers the `Product` model and runs host-side migrations:
     - Runs `just makemigration "add products"` with explicit `DATABASE_URL` pointing to exposed Postgres
     - Runs `just migrate` to apply the migration
     - **Assertions**: At least one version file in `migrations/versions/` contains `create_table('products')`
   - Tests the backend API with real HTTP round-trip:
     - `POST http://127.0.0.1:8000/api/products` with `{"name": "E2E Widget"}` returns 200 or 201 and body contains "E2E Widget"
     - `GET http://127.0.0.1:8000/api/products` returns 200 and body contains "E2E Widget"

3. **Phase 3 — Build frontend and verify browser rendering**:
   - Installs frontend Node dependencies via `just frontend-install` (runs `npm ci`)
   - Regenerates the OpenAPI client via `just generate-client`:
     - Fetches the live `http://localhost:8000/openapi.json` from the running backend
     - Regenerates `frontend/src/client/` with product operation types
     - **Assertions**: Regenerated client contains "products" substring
   - Builds the frontend via `just frontend-build` (runs `vite build`):
     - TypeScript type-checks pass
     - Vite bundles to `frontend/dist/`
     - **Assertions**: `frontend/dist/index.html` exists
   - Runs Playwright e2e tests via `just frontend-test-e2e`:
     - `products.spec.ts` navigates to `/` and asserts "E2E Widget" is visible in the DOM
     - `status.spec.ts` confirms the health status display still renders (heading + app/database health)
     - **Graceful skip**: If Playwright browser installation is unavailable (e.g., headless CI), skips cleanly instead of failing
   - **Teardown**: Always runs `compose down -v` in `try/finally` to:
     - Stop all containers
     - Remove the `pgdata` volume (prevents port/volume leakage between test runs)
     - Free port 8000 for subsequent test runs

**Shared helper additions** (`tests_e2e/_scaffold.py`):
- Exports `scaffold_fullstack_package(tmp_path) -> (destination, module_name)` to encapsulate the clone → metadata → strip → fullstack-inject → stage → init flow
- Exports `_register_products_feature(destination, module_name)` to inject the Product model, products.py router, and wire it into app.py
- Exports `_http_post_json(url, payload)` to mirror `_http_get` for POST operations (returns `(status_code, body)`, surfaces HTTP error statuses without raising)
- Exports new constants: `_APP_TSX_SOURCE` (frontend App.tsx with products section), `_PRODUCTS_SPEC_SOURCE` (Playwright spec for products visibility), `_PRODUCTS_ROUTER_SOURCE` (FastAPI router with GET/POST `/products`)

**Graceful skipping**: Requires `git`, `just`, `uv`, `npm` on `PATH` for scaffolding and frontend operations; additionally requires a compose command (`docker compose`, `podman compose`, or `podman-compose`) for stack operations and browsers for Playwright. The test skips cleanly with a diagnostic message if any required tool is missing, or if Playwright browser installation fails. Compose command auto-detection tries the portability set in precedence order.

**Caveats**: This test pulls `postgres:17`, builds the application image, runs `npm ci` + client generation + `vite build`, and runs browser automation. It takes several minutes and requires network access. It is excluded from `just check` (default quality gate) and requires explicit `just test-e2e` invocation. Like other fullstack tests, it is slow and network-dependent.

**What it guarantees**: A scaffolded fullstack application can successfully host a database-backed feature working end-to-end: the model lands in the database, migrations apply, endpoints serve HTTP correctly, and the frontend can fetch and render the data through browser automation. This complements `test_fullstack_package_runs_end_to_end` (which validates the shipped health page) by exercising the complete feature injection and data flow cycle — a realistic test of adding a new feature to a generated application.

#### Common Characteristics

**Why e2e tests are excluded by default:**
- They require network access for `uv sync` and `pip-audit` (slow, unreliable in offline/CI environments)
- They require external tools (`git`, `just`, `uv`, and `npm` for fullstack) on `PATH`
- They take several minutes to complete (vs. ~1 second for mocked unit tests)
- They are opt-in for developer workflow (`just test-e2e` for manual verification) and not enforced in default CI/CD (`just check`)

**What they guarantee:**
- The local template scaffolds correctly and produces valid packages
- Generated packages pass their respective test suites (backend pytest, frontend Vitest, or both)
- Regressions in the template code are caught end-to-end, not just in unit tests
- For fullstack packages specifically: both backend and frontend components are correctly injected and functional
- For fullstack packages additionally: the generated application runs end-to-end in a real Docker Compose stack with a live Postgres database, the backend responds correctly to HTTP health probes, the frontend can be rebuilt against the live OpenAPI schema, and TypeScript compilation succeeds against the generated client

**Intentional design choices:**
- Clone the **local committed checkout** (not the GitHub URL) so template uncommitted edits are not exercised, matching CI behavior
- Use `subprocess.run(..., check=False, capture_output=True, text=True)` to gracefully capture and surface errors rather than crash on subprocess failure
- Inject git author/committer identity (`GIT_AUTHOR_NAME`, etc.) because the inner `just init` runs `git commit` and requires a configured identity
- Document deviations in the module docstring to explain the intentional differences from production (`modernpackage.main:init_new_package`, which clones from GitHub)

### No-Flag Verification Tests

**Guarantee**: A package scaffolded with no extra flags contains zero backend or frontend code, config, dependencies, recipes, or references.

The scaffolder enforces this guarantee through two layers of testing:

#### Mocked Unit Test: `test_init_new_package_no_flags_injects_nothing`

Located in `tests/test_main.py`, this fast mocked test verifies that a no-flag `init_new_package()` call:
- Does **not** invoke `_add_backend()` or `_add_frontend()` (the injector functions)
- Makes exactly **5** subprocess calls in order: `git clone`, `just init`, `just compile`, `just sync`, `just check` (no extra calls like `git add -A` that would appear on the inject path)

This test runs in ~1 ms and serves as a regression guard on the control-flow gate (`if backend or fullstack:` at the injector entry point). It complements existing positive guards that verify `--backend` and `--fullstack` correctly invoke their injectors.

**Why this test is valuable**: It fails immediately if any code path accidentally injects backend/frontend into the no-flag flow, or if the compile/sync steps are skipped, catching regressions at development time before they propagate to e2e tests.

#### End-to-End Test: `test_scaffolded_package_has_no_backend_or_frontend`

Located in `tests/test_e2e.py` with the `@pytest.mark.e2e` marker, this comprehensive test scaffolds a real no-flag package and asserts the absence of every backend/frontend artifact:

1. **Directory checks**: Verifies these directories do not exist:
   - `backend_template`, `frontend_template`, `frontend` (template injection remnants)
   - `migrations` (Alembic directory for databases)
   - `tests_e2e` (scaffolder's end-to-end test directory that must not leak into generated packages)

2. **File checks**: Verifies these configuration files do not exist:
   - `alembic.ini` (Alembic config)
   - `compose.yml` (Docker Compose)
   - `Containerfile` (container build definition)
   - `.dockerignore` (container ignore rules)

3. **Dependency checks**: Parses `pyproject.toml` and verifies:
   - `dependencies = []` (no runtime deps injected)
   - No forbidden tokens: fastapi, sqlalchemy, asyncpg, alembic, uvicorn, httpx

4. **Recipe checks**: Parses the `Justfile` and verifies no backend/frontend recipes present:
   - No `migrate`, `makemigration`, `migration-check` (backend recipes)
   - No `frontend-*`, `generate-client` (frontend recipes)

5. **Source code checks**: Scans the package source tree and verifies no import tokens:
   - No `import fastapi`, `from fastapi`
   - No `import sqlalchemy`, `from sqlalchemy`
   - No `import asyncpg`, `import alembic`, `import uvicorn`
   - No `from react`, `vite` (frontend markers)

**Why this test is valuable**: It locks the entire no-flag guarantee end-to-end, covering the real clone → strip → init pipeline. Future changes that accidentally leak backend/frontend artifacts will fail this test before reaching production.

**Markers and exclusion**: Both tests use markers:
- Unit test: included in default `just test` run (mocked, fast)
- E2E test: marked `@pytest.mark.e2e`, excluded from `just test` (manual `just test-e2e` only)
- Neither test is included in the `just check` default flow, to avoid slowing the primary gate

**Coverage impact**: These tests exercise the stripping and validation paths but add minimal new executed code (mostly assertion-only). The 95% coverage gate remains achievable without lowering thresholds.

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

The coverage gate is measured **against mocked unit tests only** (the default `just test` run); e2e tests are not included in the coverage measurement because they exercise the public CLI (which is already covered by unit test mocks).

**Metadata writing coverage**: The 95% coverage gate ensures all branches of the metadata writing helpers (`_toml_escape`, `_write_package_metadata`, `_apply_license`) and their failure paths (missing file, `None` values, special characters) are exercised:
- Each metadata field (author_name, author_email, description, license, repository_url) has a dedicated test case covering presence and absence
- License handling has separate tests for the present/absent cases
- Special character handling (quotes and backslashes) is tested separately
- File-missing case is tested to verify graceful degradation without raising

### Test Execution

Tests run in parallel across all-but-one CPU cores (via `nproc --ignore=1`) using `pytest-xdist`. The default run excludes `e2e` marked tests, running only mocked unit tests. Coverage is aggregated transparently across parallel workers.

```bash
just test              # run parallel unit tests (mocked, excludes e2e) with coverage
just test-e2e         # run only e2e marked tests (real external calls)
just check             # run all quality gates (including parallel tests, excludes e2e)
```

On a 1-core machine, `nproc --ignore=1` yields 0; `pytest-xdist` treats `-n 0` as single-process (acceptable fallback).

## Self-Replication Flow

When a user runs `modernpackage my-cool.package --author-name "Ada Lovelace" --license "MIT"`:

1. `main()` parses arguments and validates that `my-cool.package` is a valid PEP 508 distribution name; validates author name and calls `init_new_package('my-cool.package', author_name='Ada Lovelace', package_license='MIT', ...)`
2. `init_new_package()` derives the module name: `module_name = normalize_module_name('my-cool.package')` → `'my_cool_package'`
3. `init_new_package()` clones the official repo to `./my_cool_package`, capturing stderr for detailed error reporting
4. On successful clone, `_write_package_metadata()` is called to write metadata into the cloned package's `pyproject.toml`:
   - Replaces `'Name Surname'` with `'Ada Lovelace'`
   - Inserts `license = "MIT"` after the `readme` line
   - Removes the hardcoded `"License :: OSI Approved :: MIT License"` classifier
   - Any `None` values are skipped (placeholders remain untouched)
5. On successful metadata writing, the `just init` recipe (in the clone) transforms it:
   - Renames all "modernpackage" → "my_cool_package"
   - Resets version to `0.0.1`
   - Reinitializes git
   - The metadata is already in place in the initial git commit
6. On successful initialization, `just compile` is run to regenerate the `uv.lock` file, incorporating all cloned and injected dependencies (if any)
7. On successful compile, `just sync` is run to create the virtual environment and install all locked dependencies
8. On successful sync, `just check` is run to validate the newly scaffolded package against all quality gates (formatting, linting, complexity, type checking, tests, security audit, dead code detection)
9. Result: a new, independent Python package ready for development, in a directory named `my_cool_package` with supplied metadata already written to `pyproject.toml` and included in the initial commit, all import paths using underscores instead of hyphens/dots, with a fresh lockfile and installed dependencies

This self-replication pattern allows the package to be both a tool and a template, bootstrapping new projects with the same modern tooling setup. The clone, initialization, and validation steps report detailed error output if they fail, making it easy to diagnose issues (network errors, missing dependencies, permission problems, etc.). The normalization of the distribution name to a module name ensures that the created directory and all import paths are valid Python identifiers.

## Metadata Writing

### Design Approach

Metadata is written to `pyproject.toml` via targeted, TOML-escaped string replacement rather than a full TOML round-trip. This approach:
- **Avoids new dependencies**: no TOML writer library required (e.g., `tomli-w`, `tomlkit`)
- **Preserves template formatting**: template comments, ordering, and structure are maintained
- **Is surgically precise**: only known placeholders are replaced, leaving unrelated keys untouched
- **Handles special characters safely**: the `_toml_escape()` helper escapes backslashes and quotes before substitution, ensuring values containing these characters cannot produce invalid TOML

### Hook Point: After Clone, Before `just init`

Metadata writing happens in `init_new_package()` between the clone step and the `just init` recipe. This ensures:
- The metadata is present when `just init` runs (included in the initial git commit)
- Author name, email, description, and license are safe from the `just init` sed rewriting (they never contain the "modernpackage" token)
- Repository URL may contain "modernpackage" (accepted risk; URLs with the literal token would be rewritten by sed; the e2e test deliberately uses token-free URLs)

### Null Handling

When a value is `None` (not resolved from any source), the corresponding placeholder is left untouched. For example:
- If `author_name` is `None`, `'Name Surname'` remains in the file
- If `package_license` is `None`, the MIT classifier remains and no license field is added
- This allows partial scaffolding: users can supply only the metadata they care about and let the template defaults handle the rest

### Complexity Constraint

The metadata writing is split into two functions to maintain cyclomatic complexity ≤ 8 (enforced by `pyproject.toml`):
- `_write_package_metadata()` handles all non-license fields (author_name, author_email, description, repository_url) and delegates license handling to the helper
- `_apply_license()` is a separate private function that handles license insertion and classifier removal, keeping the parent function lean and readable

## Known Gaps & Deviations

### Error handling in `init_new_package()`

Both the `git clone` and `just init` subprocess calls capture stderr and include it in error messages:

**Git clone step**: Both stdout and stderr are captured via `Popen(..., stderr=PIPE)` and `communicate()`, which returns a `(stdout, stderr)` tuple. If the return code is non-zero (indicating failure), a `RuntimeError` is raised with the message `'git clone failed with exit code {returncode}: {stderr}'`. The decoded stderr output provides visibility into the root cause (e.g., network errors, invalid URLs, authentication failures). This prevents the function from continuing to the `just init` step when cloning fails.

**Just init step**: The `Popen` call for `just init` is wrapped in a `try`/`except FileNotFoundError` block to detect when the `just` command is not installed. If `FileNotFoundError` is raised (indicating the executable cannot be found), a `RuntimeError` is raised with an actionable message: `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`. This check occurs before subprocess execution, providing immediate feedback to the user.

If the `Popen` call succeeds but the subprocess exits with a non-zero return code, a `RuntimeError` is raised with the message `'just init failed with exit code {returncode}: {stderr}'`. The decoded stderr output provides visibility into the root cause (e.g., rewrite errors, git failures within the init script). A failed `just init` leaves the cloned directory in an incomplete state, so the error is caught and reported immediately rather than silently continuing.

### Version Consistency

The `just publish` recipe ensures version consistency across the repository and PyPI release: it automatically invokes `just bump` to increment the patch version, commits the updated version file to the repository with a descriptive commit message that includes the new version (e.g., "Bump version to 0.0.13"), pushes to the remote, and then builds and publishes to PyPI. This guarantees that the version in the pushed commit matches the version in the published wheel, eliminating manual version management errors.

### Justfile command surface

The `Justfile` provides a comprehensive command surface for all development, testing, and publishing workflows:
- **`just test`** and **`just test-e2e`** run in parallel across `nproc --ignore=1` workers with full test discovery and coverage measurement
- **`just check`** enforces the full gate (format, lint, complexity, typecheck, test, audit, deadcode) as the primary quality gate
- **`just fix`** auto-fixes all correctable violations (format + lint + deadcode)
- **`just bump`** increments the patch version in `modernpackage/__init__.py` (e.g., `0.0.9` → `0.0.10`)
- **`just publish`** runs `just bump`, commits the version file with a descriptive message including the new version, pushes to the remote repository, then builds and publishes to PyPI
- **`just lock`** upgrades all locked dependencies
- **`just init <name>`** replicates the package with a new name (named parameter, default `"modernpackage"`)
