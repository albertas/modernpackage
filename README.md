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
- Update package version to 0.0.1 during `make init`. Version should be initialised to be v0.0.1
- make a cli command: this package should be installable. Ideally this flow should work:
  - `pip install modernpackage`
  - `modernpackage mynewpackage`
  - `cd mynewpackage` && `make check` && `make publish`
- Enable github and gitlab pipeline files to run `make check` in the pipeline.
- Add pre-commit hooks with all the tools enabled.
- codspeed.io could be considered for Continuous integration pipeline
