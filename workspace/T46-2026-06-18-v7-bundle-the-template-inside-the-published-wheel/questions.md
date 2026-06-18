# Research Questions

## Context
Focus on the `modernpackage` CLI package (`modernpackage/main.py`,
`modernpackage/__init__.py`), the build/packaging configuration in
`pyproject.toml` (hatchling build backend, include/exclude rules, version
source), and the `Justfile` (especially the `init`, `publish`, and `check`
recipes). Also look at how tests in `tests/` exercise the scaffolding flow and
the docs under `docs/`.

## Questions
1. Trace the end-to-end scaffolding flow in `modernpackage/main.py`: from CLI
   argument parsing through preflight checks, the `git clone` of the template,
   the `pyproject.toml` metadata rewrite, and the `just init` / `just check`
   subprocess calls — what produces the final package directory, and what does
   each step assume about where the template comes from?

2. How is the wheel/sdist currently built and what files does it contain? Look
   at the hatchling configuration in `pyproject.toml` (`[tool.hatch.build]`
   include/exclude, version source) and the `publish` recipe in the `Justfile`,
   and determine what is and is not packaged into the distributed artifact today.

3. What does the `just init` recipe in the `Justfile` do step by step (the
   `modernpackage` -> package-name substitution, version reset, directory
   rename, `git init`/commit, `.git`/`.venv` removal), and which of those steps
   depend on the cloned repository being a real git working tree?

4. How does the code locate and read files relative to the package or the
   working directory at runtime (e.g. `Path.cwd()`, `Path(__file__)`,
   `importlib.resources`, `tomllib` reads), and what patterns already exist for
   referencing package-internal versus cloned-template paths?

5. How do the existing tests (`tests/test_main.py`, `tests/test_e2e.py`) mock or
   exercise the `git clone` and `just init` subprocess steps, and what does the
   e2e test assert about a freshly scaffolded package?

6. Where is the template repository URL and related template configuration
   defined and referenced across the codebase (constants in `main.py`, docs,
   preflight reachability probe), and what other behavior is coupled to the
   clone-from-remote approach?
