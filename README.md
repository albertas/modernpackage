# modernpackage

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset.

## Usage

Install and run:
```bash
pip install modernpackage
modernpackage <your-package-name>     # or `mp <your-package-name>`
                                       # prints preflight checklist to stdout ([ok] / [FAIL])
                                       # verifies git, just, and uv are on PATH
                                       # checks that target directory does not already exist
                                       # probes template repository reachability (fails fast on network issues)
                                       # validates the name (rejects stdlib collisions before scaffolding)
                                       # creates a new package and validates it with just check
                                       # prints "just check passed" or "just check failed"

# Example: Preflight checklist (on success)
modernpackage my-package

# Output:
# Preflight checks:
#   [ok]   package name valid
#   [ok]   required tools on PATH (git, just, uv)
#   [ok]   target directory available
#   [ok]   template remote reachable
# just check passed — my_package scaffold is valid.

# Example: Create a package with a name containing hyphens and dots
modernpackage my-cool.package           # Valid PEP 508 distribution name
                                        # Creates directory: my_cool_package
                                        # All Python imports: from my_cool_package import ...

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

# Example: Preflight checklist failure (missing git)
modernpackage my-package

# Output (stdout):
# Preflight checks:
#   [ok]   package name valid
#   [FAIL] required tools on PATH (git, just, uv)
#
# Output (stderr):
# required tool(s) not found on PATH: git — install the missing tool(s) before scaffolding:
#   - git: https://git-scm.com/downloads
# Exit code 1 (preflight check fails)
# No scaffolding occurs, no directory created

# Example: Preflight checklist failure (directory exists)
mkdir my-package
modernpackage my-package

# Output (stdout):
# Preflight checks:
#   [ok]   package name valid
#   [ok]   required tools on PATH (git, just, uv)
#   [FAIL] target directory available
#
# Output (stderr):
# target directory already exists: /path/to/my_package — choose a different package name or remove the existing directory
# Exit code 1 (preflight check fails)
# No scaffolding occurs

# Example: Multiple required tools missing (missing git and uv)
modernpackage my-package                # Error: required tool(s) not found on PATH: git, uv — install the missing tool(s) before scaffolding:
                                        #   - git: https://git-scm.com/downloads
                                        #   - uv: https://docs.astral.sh/uv/getting-started/installation/
                                        # Exit code 1 (preflight check fails)
                                        # No scaffolding occurs, no directory created

# Example: Target directory already exists
mkdir my-package
modernpackage my-package                # Error: target directory already exists: /path/to/my_package — choose a different package name or remove the existing directory
                                        # Exit code 1 (preflight check fails)
                                        # No scaffolding occurs

# Example: Template repository unreachable (network down or DNS failure)
modernpackage my-package                # Error: repository unreachable — check your network connection
                                        # 
                                        # template remote unreachable (git ls-remote exit code 2): fatal: Could not resolve host: github.com
                                        # Exit code 1 (preflight check fails)
                                        # No scaffolding occurs, no directory created
```

View the installed version:
```bash
modernpackage --version               # or `mp -v`
```

### Optional Metadata Flags

The CLI accepts five optional flags for package metadata:

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

Once your new package is created and validated, you can begin development. The initialization process automatically runs `just check` on the newly scaffolded package and reports whether all quality gates passed (you'll see "just check passed" or "just check failed"). 

**Note**: If you provided a package name with hyphens or dots (e.g., `my-cool.package`), the created directory will use underscores instead (e.g., `my_cool_package`). This ensures the directory name and all Python imports are valid identifiers.

To continue development:

```bash
cd my_cool_package              # Use the directory name (with underscores)
just check    # Run tests and linters (already run during scaffolding; use for ongoing validation)
just fix      # Auto-fix linting and formatting issues
just publish  # Publish your package to PyPI.org
```

To push to a Git repository (create the project on GitLab/GitHub first):
```bash
git remote add origin git@gitlab.com:<your-username>/<directory-name>.git
git push
```

## Development
Commonly used commands for package development:
- `just check` - run unit tests and linters (format, lint, complexity, typecheck, tests, security audit, dead code detection). Primary quality gate; excludes e2e tests.
- `just test` - run unit tests only (mocked, parallel, excludes e2e).
- `just test-e2e` - run end-to-end test that scaffolds a package and validates it with `just check` (slow, requires network and git/just/uv on PATH; skips gracefully if tools missing).
- `just fix` - format code and fix detected fixable issues.
- `just publish` - publishes current package version to pypi.org.
- `just compile` - bump and freeze dependency versions in requirements*.txt files.
- `just sync` - upgrade installed dependencies in Virtual Environment (executed after `just compile`).

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
