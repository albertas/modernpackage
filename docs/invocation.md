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
- **Exit code 0**: successful operation (version printed, package initialized, or no arguments provided)
- **Exit code 1**: failure in package initialization (git clone or just init failed)

The exit code is reflected in the process exit status, allowing shell scripts and CI/CD pipelines to detect failures.

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

Initializes a new Python package with the given name in the current directory. The `package_name` argument is validated to contain only alphanumeric characters (letters and digits). If the name contains non-alphanumeric characters, an error is raised:

```
usage: modernpackage [-v] [package_name]
modernpackage: error: argument package_name: Non-AlphaNumeric package name
```

#### Success path

Upon success, a new directory named `<package_name>` is created in the current working directory, containing a complete, ready-to-use Python package with:
- All source files cloned from `https://github.com/albertas/modernpackage`
- All occurrences of "modernpackage" renamed to the new package name
- Version reset to `0.0.1`
- Git repository reinitialized
- Quality validation run via `just check` to verify the scaffolded package passes all quality gates (formatting, linting, complexity, type checking, tests, security audit, dead code detection)

After all steps complete, the outcome of `just check` is reported:
- **If `just check` passes** (all quality gates succeed), a message is printed to stdout:
  ```
  just check passed — <package_name> scaffold is valid.
  ```
- **If `just check` fails** (any quality gate fails), a message is printed to stderr:
  ```
  just check failed with exit code <code> — review the output in <package_name>.
  ```

In both cases, `init_new_package` returns successfully; validation failure is reported but does not prevent the package from being created (allowing the user to review and fix issues in the newly created directory).

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

## Argument Parser

The CLI uses `argparse.ArgumentParser` with the following configuration:

- **`-v` / `--version`**: optional flag, `action='store_true'`, default `False` — prints package version
- **`package_name`**: optional positional argument, `nargs='?'`, validated via `type=check_alpha_numeric()` — name of package to initialize

The parser is created and invoked in `parse_args()`, which returns an `argparse.Namespace` object with type-annotated fields:
- `version: bool` — whether the `--version` flag was provided
- `package_name: str | None` — the package name (if provided), or `None` if omitted

### Type Safety

The `parse_args()` function is fully type-annotated (`def parse_args() -> Namespace`) and verified by mypy in strict mode. All argument validation and type checking is enforced at parse time.

## Validation

**`check_alpha_numeric(value)`** validates that a string contains only alphanumeric characters:

- Input: a string (typically the package name)
- Output: the input string unchanged if valid
- Error: raises `argparse.ArgumentTypeError('Non-AlphaNumeric package name')` if the string contains any non-alphanumeric character

Examples:
- `check_alpha_numeric('mypackage')` → `'mypackage'` ✓
- `check_alpha_numeric('MyPackage123')` → `'MyPackage123'` ✓
- `check_alpha_numeric('my-package')` → raises `ArgumentTypeError` (hyphen is invalid)
- `check_alpha_numeric('my_package')` → raises `ArgumentTypeError` (underscore is invalid)
