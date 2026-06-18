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

The main CLI orchestrator with type-annotated functions and module-level regex constants.

#### Module-Level Constants

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

#### Functions

The main CLI orchestrator with type-annotated functions:

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

Parses command-line arguments using `argparse.ArgumentParser`, applies environment variable defaults for omitted flags, applies git config defaults for certain omitted env vars, and validates email and URL values.

- **Arguments**:
  - `-v` / `--version`: optional flag (default `False`)
  - `package_name`: optional positional argument (validated via `validate_package_name`)
  - `--author-name`: optional flag (default `None`, free string, no validation). If omitted, falls back via the precedence ladder: `_environment_default(_AUTHOR_NAME_ENV)`, then `_git_config_default(_GIT_CONFIG_USER_NAME_KEY)`.
  - `--author-email`: optional flag (default `None`, validated via `validate_author_email`). If omitted, falls back via the precedence ladder: `_environment_default(_AUTHOR_EMAIL_ENV)`, then `_git_config_default(_GIT_CONFIG_USER_EMAIL_KEY)`, then validates via `_validated_or_error()`.
  - `--description`: optional flag (default `None`, free string, no validation). If omitted, substitutes `_environment_default(_DESCRIPTION_ENV)`.
  - `--license`: optional flag (default `None`, free string, no validation). If omitted, substitutes `_environment_default(_LICENSE_ENV)`.
  - `--repository-url`: optional flag (default `None`, validated via `validate_repository_url`). If omitted, substitutes `_environment_default(_REPOSITORY_URL_ENV)`, then validates via `_validated_or_error()`.

- **Process**:
  1. **Parse**: creates `ArgumentParser`, defines all arguments with `default=None`, calls `parser.parse_args()` to get initial `Namespace`
  2. **Environment fallback**: for each of the five metadata fields, if the namespace value is `None` (flag was omitted), substitutes the environment variable value via `_environment_default()`
  3. **Git config fallback** (for `author_name` and `author_email` only): if the value is still `None` after the environment fallback, consults git config via `_git_config_default()` to establish the precedence ladder: **flag > env > git config > None**
  4. **Validate**: for email and repository URL, calls `_validated_or_error()` to validate the final (possibly env-sourced or git-config-sourced) value; invalid values exit cleanly with code 2 and a CLI-style error message instead of a traceback
  5. **Return**: returns the fully resolved namespace

- **Returns**: `Namespace` — an `argparse.Namespace` object with fields:
  - `version` (bool) — whether `--version` was provided
  - `package_name` (str | None) — the package name (from flag or `None`)
  - `author_name` (str | None) — author name (from flag, env var, git config, or `None`)
  - `author_email` (str | None) — author email (from flag, env var, git config, or `None`, validated)
  - `description` (str | None) — description (from flag, env var, or `None`)
  - `license` (str | None) — license identifier (from flag, env var, or `None`)
  - `repository_url` (str | None) — repository URL (from flag, env var, or `None`, validated)

**Precedence for `author_name` and `author_email`**: **flag > env > git config > None**. For other fields, precedence is **flag > env > None** (no git config fallback).

**Git config fallback**: When both flag and environment variable are absent, `author_name` and `author_email` fall back to the user's git config (`user.name` and `user.email` respectively), reading the merged (local-over-global) configuration. Git config values flow through the same validation as env values: email addresses must match the basic email pattern, or the command exits with code 2 and a CLI error.

**Empty environment variables**: An environment variable set to an empty string (`''`) is treated as unset and returns `None`, allowing the next fallback level (git config) to be consulted.

**Complexity**: The function has a McCabe cyclomatic complexity of ≤ 8 (enforced by `pyproject.toml:tool.ruff.lint.mccabe.max-complexity`), with the validation logic extracted into the `_validated_or_error()` helper to keep the post-parse block clear and maintainable.

#### `init_new_package(package_name: str, *, author_name: str | None = None, author_email: str | None = None, description: str | None = None, package_license: str | None = None, repository_url: str | None = None) -> int`

Orchestrates the package initialization flow by cloning, rewriting, and validating. Uses `normalize_module_name` to derive the import-safe directory name from the user-provided distribution name.

1. **Positional Parameter**: `package_name: str` — name of the new package to create (validated distribution name, may contain `.` or `-`)
2. **Keyword Parameters** (optional, all default to `None`):
   - `author_name: str | None = None` — author name to include in the package metadata (free string, not yet written to files)
   - `author_email: str | None = None` — author email to include in the package metadata (validated via `validate_author_email`, not yet written to files)
   - `description: str | None = None` — package description to include in metadata (free string, not yet written to files)
   - `package_license: str | None = None` — license identifier to include in metadata (free string, not yet written to files)
   - `repository_url: str | None = None` — repository URL to include in metadata (validated via `validate_repository_url`, not yet written to files)
3. **Returns**: `int` — exit code (0 on success, 1 if `just check` fails)

**Important note on metadata parameters**: The metadata parameters are accepted by the function signature and threaded through from the CLI for foundation-building (forming the infrastructure for later V4 work). They are currently **not written to `pyproject.toml` or any other files** — that writing is deferred to later V4 work. The parameters are acknowledged internally to satisfy linting requirements (unused-argument detection).
3. **Derivation**: Converts the package name to a module name:
   ```python
   module_name = normalize_module_name(package_name)
   ```
   For example, if the user provides `my-cool.package`, the derived `module_name` is `my_cool_package`.
4. **Process**:
   - Resolves target path using the module name: `Path.cwd() / module_name`
   - **Step 1: Clone** — Spawns `git clone https://github.com/albertas/modernpackage <module_name>` via `Popen` with `stderr=PIPE` (target directory uses underscores, not hyphens/dots)
     - Waits for completion via `communicate()` and captures both stdout and stderr
     - **If `returncode != 0`**: calls `humanize_git_clone_error(decoded stderr)` to map common failure patterns to friendly messages; raises `RuntimeError` with either:
       - `'{friendly message}\n\ngit clone failed with exit code {returncode}: {decoded stderr}'` if a known pattern is found, or
       - `'git clone failed with exit code {returncode}: {decoded stderr}'` as fallback for unknown errors
   - **Step 2: Initialize** — **If `returncode == 0`**: continues to spawn `just init <module_name>` (cwd: the cloned directory, using the normalized module name) with `stderr=PIPE`
     - Wraps the `just init` `Popen` call in a `try`/`except FileNotFoundError` block:
       - **If `FileNotFoundError` is raised**: catches the exception and raises `RuntimeError` with an actionable message: `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`
       - **If `Popen` succeeds**: waits for completion via `communicate()` and captures both stdout and stderr
         - **If `returncode != 0`**: raises `RuntimeError` with message `'just init failed with exit code {returncode}: {decoded stderr}'`
         - **If `returncode == 0`**: continues to Step 3
   - **Step 3: Validate** — **If Step 2 succeeds**: runs `just check` (cwd: the cloned directory) via `Popen` and reports the outcome using the module name
     - Spawns the subprocess and captures both stdout and stderr via `communicate()`
     - **If `returncode == 0`**: prints a success message to stdout: `'just check passed — {module_name} scaffold is valid.'` (using the normalized module name) and returns `0`
     - **If `returncode != 0`**: prints a failure message to stderr: `'just check failed with exit code {returncode} — review the output in {module_name}.'` (using the normalized module name) and returns `1`
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
  1. Calls `parse_args()` to get user input (including the five new metadata flags)
  2. **If** `version` flag is set: prints `modernpackage <__version__>` and returns `0`
  3. **Elif** `package_name` is provided:
     - Calls `init_new_package()` with the package name and all metadata keyword arguments inside a `try`/`except RuntimeError` block:
       ```python
       init_new_package(
           package_name=parsed_args.package_name,
           author_name=parsed_args.author_name,
           author_email=parsed_args.author_email,
           description=parsed_args.description,
           package_license=parsed_args.license,
           repository_url=parsed_args.repository_url,
       )
       ```
     - **If** `RuntimeError` is raised: catches it, prints the error message to `sys.stderr` (which includes captured stderr from the failed subprocess), and returns `1`
     - **If** no error: returns the value from `init_new_package()` (which is `0` if `just check` passed, or `1` if it failed)
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
- `modernpackage/main.py` — CLI orchestrator with 6 public functions and 2 private helpers:
  - Public validators: `validate_package_name`, `validate_author_email`, `validate_repository_url`
  - Public utilities: `normalize_module_name`, `parse_args`, `init_new_package`, `main`
  - Private helpers: `_explain_invalid_package_name`, `humanize_git_clone_error`
- `tests/__init__.py` — test package marker
- `tests/test_main.py` — comprehensive test suite (including tests for validators, normalization, and integration)

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

Tests live in `tests/test_main.py` (mocked unit tests) and `tests/test_e2e.py` (end-to-end test) using:

- Plain `def test_*` functions (no test classes)
- `unittest.mock.patch` for dependency injection (mocking `ArgumentParser`, `print`, `Popen`, etc.)
- `pytest.raises` for exception testing
- Unit tests (`tests/test_main.py`): no real subprocess/network calls; all external dependencies mocked
- End-to-end tests (`tests/test_e2e.py`): real subprocess calls, network access, filesystem operations

### Test Markers

The `e2e` marker is registered in `pyproject.toml` to categorize tests:

- **`e2e`**: marks tests that perform real external calls (network, subprocess, filesystem). These are excluded from the default `just test` run (which runs only mocked unit tests) and are reserved for an explicit `just test-e2e` invocation. Pre-registering the marker prevents future `filterwarnings = error` strictness from breaking on unregistered marker usage.

### End-to-End Test: Scaffolding Validation

The e2e test (`tests/test_e2e.py:test_scaffolded_package_passes_check`, marked with `@pytest.mark.e2e`) validates the core scaffolding workflow by:

1. **Skipping gracefully** if required tools are missing: checks `git`, `just`, and `uv` are on `PATH`; skips the test with a diagnostic message if any are missing
2. **Cloning the local template** from the repo root into a temporary directory (intentionally **not** the GitHub URL, so local template regressions are caught)
3. **Running `just init <package_name>`** to replicate the package (rename all "modernpackage" occurrences, reset version to `0.0.1`, reinitialize git)
4. **Verifying the result** by checking that the renamed `__init__.py` file exists and contains the pinned version `0.0.1`
5. **Validating all quality gates** by running `just check` against the scaffolded package and asserting exit code 0 (passes format, lint, complexity, typecheck, unit tests, security audit, dead code detection)

**Why this test is excluded by default:**
- It requires network access for `uv sync` and `pip-audit` (slow, unreliable in offline/CI environments)
- It requires `git`, `just`, and `uv` on `PATH` (extra tool dependencies)
- It takes several minutes to complete (vs. ~1 second for mocked unit tests)
- It is opt-in for developer workflow (`just test-e2e` for manual verification) and not enforced in default CI/CD (`just check`)

**What it guarantees:**
- The local template scaffolds correctly and produces a valid package
- The scaffolded package passes all quality gates (same bar as production)
- Regressions in the template code are caught end-to-end, not just in unit tests

**Intentional design choices:**
- Clones the **local committed checkout** (not the GitHub URL) so template uncommitted edits are not exercised, matching CI behavior
- Uses `subprocess.run(..., check=False, capture_output=True, text=True)` to gracefully capture and surface errors rather than crash on subprocess failure
- Injects git author/committer identity (`GIT_AUTHOR_NAME`, etc.) because the inner `just init` runs `git commit` and requires a configured identity
- Documents deviations in the module docstring to explain the intentional differences from production (`modernpackage.main:init_new_package`, which clones from GitHub)

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

The coverage gate is measured **against mocked unit tests only** (the default `just test` run); the e2e test is not included in the coverage measurement because it exercises the public CLI (which is already covered by unit test mocks).

### Test Execution

Tests run in parallel across all-but-one CPU cores (via `nproc --ignore=1`) using `pytest-xdist`. The default run excludes `e2e` marked tests, running only mocked unit tests. Coverage is aggregated transparently across parallel workers.

```bash
just test              # run parallel unit tests (mocked, excludes e2e) with coverage
just test-e2e         # run only e2e marked tests (real external calls)
just check             # run all quality gates (including parallel tests, excludes e2e)
```

On a 1-core machine, `nproc --ignore=1` yields 0; `pytest-xdist` treats `-n 0` as single-process (acceptable fallback).

## Self-Replication Flow

When a user runs `modernpackage my-cool.package`:

1. `main()` parses arguments and validates that `my-cool.package` is a valid PEP 508 distribution name; calls `init_new_package('my-cool.package')`
2. `init_new_package()` derives the module name: `module_name = normalize_module_name('my-cool.package')` → `'my_cool_package'`
3. `init_new_package()` clones the official repo to `./my_cool_package`, capturing stderr for detailed error reporting
4. On successful clone, the `just init` recipe (in the clone) transforms it:
   - Renames all "modernpackage" → "my_cool_package"
   - Resets version to `0.0.1`
   - Reinitializes git
5. On successful initialization, `just check` is run to validate the newly scaffolded package against all quality gates (formatting, linting, complexity, type checking, tests, security audit, dead code detection)
6. Result: a new, independent Python package ready for development, in a directory named `my_cool_package` with all import paths using underscores instead of hyphens/dots

This self-replication pattern allows the package to be both a tool and a template, bootstrapping new projects with the same modern tooling setup. The clone, initialization, and validation steps report detailed error output if they fail, making it easy to diagnose issues (network errors, missing dependencies, permission problems, etc.). The normalization of the distribution name to a module name ensures that the created directory and all import paths are valid Python identifiers.

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
