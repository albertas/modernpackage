# Task

Extend the project's `Justfile` with developer-workflow targets that mirror the
existing `Makefile`: run tests, `ruff format`, `ruff` lint, `mypy` typecheck,
code-complexity check (McCabe `C901`), and a combined `check` target that runs
all of them. Also ensure the dev dependencies these targets need are declared.

This gives contributors a single, consistent `just`-based entrypoint for code
quality checks, matching the conventions already used elsewhere in the repo.
