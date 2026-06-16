# Research Questions

## Context
Focus on the `modernpackage/` Python package, the project's `tests/`, and the
top-level build and configuration files (`pyproject.toml`, `Makefile`,
`Justfile`, `requirements*.txt`, `README.md`). The codebase is a small CLI tool;
investigate its runtime behaviour, its build/tooling configuration, and how it
is packaged and tested.

## Questions
1. What is the CLI entry point of the package, what command-line arguments and
   options does it accept, and how does control flow from argument parsing to
   the resulting actions?
2. Trace the package-initialisation flow: when a new package name is provided,
   what external commands are invoked, what files are cloned or renamed, and how
   does the `Makefile` `init` target transform the cloned project?
3. How is the package built, versioned, and published — what does
   `pyproject.toml` declare for build backend, entry-point scripts, version
   source, and dependency groups, and what role do `requirements.txt` /
   `requirements-dev.txt` play?
4. What developer tooling is configured (linting, formatting, type checking,
   vulnerability/dead-code scanning, testing, coverage), how is each configured,
   and through which `Makefile` and `Justfile` targets are they invoked?
5. How are the tests structured, what behaviour do they currently cover, and
   what mocking or fixtures do they rely on?
6. What is the overall file/module structure of the repository, and how do the
   modules and configuration files relate to one another?
