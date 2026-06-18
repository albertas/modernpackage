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

### Package initialization

```bash
modernpackage <package_name>
mp <name>
```

Initializes a new Python package with the given name in the current directory. The `package_name` argument is validated to be a valid PEP 508 / PyPI distribution name:
- Must start and end with an alphanumeric character (a-z, A-Z, 0-9)
- May contain hyphens (`-`), underscores (`_`), and dots (`.`) in between
- Validation is case-insensitive

If the name does not match this pattern, an error is raised:

```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Invalid package name: '<name>'
```

Examples of valid names: `mypackage`, `my-package`, `my_package`, `my.package`, `a`
Examples of invalid names: `-bad`, `bad-`, `has space`, empty string

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
- **If `just check` passes** (all quality gates succeed), a message is printed to stdout and exit code 0 is returned:
  ```
  just check passed — <module_name> scaffold is valid.
  ```
  Exit code: 0
  (where `<module_name>` is the normalized directory name with underscores)
  
- **If `just check` fails** (any quality gate fails), a message is printed to stderr and exit code 1 is returned:
  ```
  just check failed with exit code <code> — review the output in <module_name>.
  ```
  Exit code: 1
  (where `<module_name>` is the normalized directory name with underscores)

The package directory is created in both cases; validation failure is reported but does not prevent the package from being created (allowing the user to review and fix issues in the newly created directory). However, the exit code now reflects the validation outcome, allowing CI/CD pipelines and automated tools to detect when the scaffolded package does not meet quality standards.

#### Failure path

If the `git clone` step fails (e.g., due to network errors, invalid URL, or repository not found), the error is caught in `main()` and printed to stderr with exit code 1.

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

## Argument Parser

The CLI uses `argparse.ArgumentParser` with the following configuration:

- **`-v` / `--version`**: optional flag, `action='store_true'`, default `False` — prints package version
- **`package_name`**: optional positional argument, `nargs='?'`, validated via `type=validate_package_name()` — name of package to initialize (must be a valid PEP 508 / PyPI distribution name)

The parser is created and invoked in `parse_args()`, which returns an `argparse.Namespace` object with type-annotated fields:
- `version: bool` — whether the `--version` flag was provided
- `package_name: str | None` — the package name (if provided), or `None` if omitted

### Type Safety

The `parse_args()` function is fully type-annotated (`def parse_args() -> Namespace`) and verified by mypy in strict mode. All argument validation and type checking is enforced at parse time.

## Validation

**`validate_package_name(value)`** validates that a string is a valid PEP 508 / PyPI distribution name:

- Input: a string (typically the package name)
- Output: the input string unchanged if valid
- Error: raises `argparse.ArgumentTypeError(f'Invalid package name: {value!r}')` if the string does not match the PEP 508 pattern

The validation pattern matches:
- A single alphanumeric character (e.g., `'a'`)
- Or an alphanumeric character followed by any number of alphanumeric characters, hyphens, underscores, or dots, followed by an alphanumeric character (e.g., `'my-package'`, `'my_package'`, `'my.package'`)

Examples:
- `validate_package_name('mypackage')` → `'mypackage'` ✓
- `validate_package_name('MyPackage123')` → `'MyPackage123'` ✓
- `validate_package_name('my-package')` → `'my-package'` ✓
- `validate_package_name('my_package')` → `'my_package'` ✓
- `validate_package_name('my.package')` → `'my.package'` ✓
- `validate_package_name('a')` → `'a'` ✓
- `validate_package_name('-bad')` → raises `ArgumentTypeError` (leading hyphen is invalid)
- `validate_package_name('bad-')` → raises `ArgumentTypeError` (trailing hyphen is invalid)
- `validate_package_name('has space')` → raises `ArgumentTypeError` (space is invalid)
