# modernpackage

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset.

## Usage

Install and run:
```bash
pip install modernpackage
modernpackage <your-package-name>     # or `mp <your-package-name>`
                                       # creates a new package and validates it with just check
                                       # prints "just check passed" or "just check failed"

# Example: Create a package with a name containing hyphens and dots
modernpackage my-cool.package           # Valid PEP 508 distribution name
                                        # Creates directory: my_cool_package
                                        # All Python imports: from my_cool_package import ...
```

View the installed version:
```bash
modernpackage --version               # or `mp -v`
```

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
