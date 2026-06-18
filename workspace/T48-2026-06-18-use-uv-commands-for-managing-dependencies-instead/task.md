# Task

Modernize the project's dependency management to use native `uv` commands
(`uv sync`, `uv add`, `uv lock`) in place of the legacy `uv pip` workflow
(`uv pip sync`, `uv pip install -e .[test]`, `uv pip compile`). Move the test
tooling dependencies out of the `[project.optional-dependencies].test` extra and
into a uv-managed dev dependency group, then update the Justfile (and Makefile,
if present) and any related CI/docs to match.

This keeps the scaffolding template aligned with current uv best practices so
that generated packages and the template itself manage dependencies the
recommended way.
