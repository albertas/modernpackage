# Research Questions

## Context
Focus on how this Python package manages its dependencies: the declaration
files (`pyproject.toml`), the `uv.lock` lock file, the compiled
`requirements.txt` / `requirements-dev.txt` files, and the build/CI tooling
(`Justfile`, `Makefile`, `.gitlab-ci.yml`). Also look at the package index
configuration and the documentation under `docs/`.

## Questions
1. How and where are dependencies declared in `pyproject.toml` (runtime
   dependencies, optional/extra groups, build-system requirements), and what
   version constraints, if any, are applied to each?
2. How are `uv.lock`, `requirements.txt`, and `requirements-dev.txt`
   generated, and which commands or recipes (in `Justfile`, `Makefile`, or
   elsewhere) produce and keep them consistent with `pyproject.toml`?
3. How are dependencies installed and synchronized for local development and
   for CI (trace the recipes/targets in `Justfile`, `Makefile`, and
   `.gitlab-ci.yml`), and which package index sources are configured?
4. What tooling exists for auditing, checking, or validating dependencies
   (e.g. `pip-audit`, `deadcode`), and how and when is it invoked relative to
   the combined `check` target?
5. How is the required Python version specified across the configuration
   files, and how does that interact with dependency resolution and the lock
   file's resolution markers?
6. What do the documents under `docs/` say about the project's dependency
   management, toolset, or versioning approach?
