# modernpackage
This package allows to quickly initialise new Python package using bleeding edge tools like linters, just run:
- `pip install modernpackage`
- `modernpackage <your-package-name>`

Now you are able to:
- `cd <your-package-name>`
- `make check    # To run tests and linters`
- `make publish  # To publish your new package to PyPi.org to make it accessable to everyone`

This is also a boilerplate for a new python package, so you can create a new package this way as well:
- `git clone git@github.com:albertas/modernpackage.git <your-package-name>`
- `cd <your-package-name>`
- `make init <your-package-name>` - to start your modern package.

## Development
Commonly used commands for package development:
- `make check` - run unit tests and linters.
- `make fix` - format code and fix detected fixable issues.
- `make publish` - publishes current package version to pypi.org.
- `make compile` - bump and freeze dependency versions in requirements*.txt files
- `make sync` - upgrade installed dependencies in Virtual Environment (executed after `make compile`)

## Toolset
This package uses these cutting edge tools:
- ruff - for linting and code formatting
- mypy - for type checking
- pip-audit - for known vulnerability detection in dependencies
- deadcode - for unused code detection
- pytest - for collecting and running unit tests
- coverage - for code coverage by unit tests
- hatch - for publishing package to pypi.org
- uv - for Python virtual environment and dependency management
- pyproject.toml - configuration file for all tools
- Makefile - aliases for commonly used command line commands

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
