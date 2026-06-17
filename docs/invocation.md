# modernpackage — CLI Invocation

[overview.md](overview.md)

## Entry Points

`modernpackage` defines two console script entry points in `pyproject.toml`:
- `modernpackage` — full name entry point
- `mp` — alias for quick invocation

Both route to `modernpackage.main:main()`, so they are functionally identical.

## Command-Line Interface

### No arguments (no-op)

```bash
modernpackage
```

Calls `main()` with no arguments. If neither `--version` nor a package name is provided, the function exits silently with no action.

### Version flag

```bash
modernpackage --version
modernpackage -v
```

Prints the installed version of `modernpackage` and exits:
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

#### Failure path

If the `git clone` step fails (e.g., due to network errors, invalid URL, or repository not found), the error is caught in `main()` and printed to stderr:

```
git clone failed with exit code <code>: <stderr output>
```

The error message includes the captured stderr output from the failed `git clone` command, providing visibility into the root cause. The command exits without creating the target directory.

If the `just init` step fails after cloning completes (e.g., due to missing `just` command, rewrite errors, or other failures), the error is caught in `main()` and printed to stderr:

```
just init failed with exit code <code>: <stderr output>
```

The error message includes the captured stderr output from the failed `just init` command. The command exits and the `<package_name>` directory is left in an incomplete state (the cloned files are present, but the transformation to the new package name was not completed).

Both errors are printed to `sys.stderr` as clean messages, without a Python traceback, making error diagnosis straightforward for end users.

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
