# Research Questions

## Context
Focus on the package-scaffolding flow (`init_new_package` in
`modernpackage/main.py` and the `init` recipe in the `Justfile`), the test
suite under `tests/`, and the test-tooling configuration in `pyproject.toml`
and the `Justfile`. Also look at how the project's quality gate is defined and
what external resources it depends on.

## Questions
1. How does the package-scaffolding flow work end to end — what does
   `init_new_package` do, what does the `Justfile` `init` recipe do step by
   step, and what source location does the new package's files come from?
2. How is the `e2e` test marker defined and wired up — where is it registered,
   how does the default test run treat it, and how are e2e tests invoked
   separately?
3. What existing patterns do the tests in `tests/` use for filesystem isolation,
   subprocess invocation, and mocking versus performing real external calls?
4. What does the `check` recipe in the `Justfile` run, and what does each
   sub-step (format, lint, complexity, typecheck, test, audit) require to
   succeed?
5. Which steps of scaffolding and of `just check` depend on external resources
   (network, git remotes, package indexes, installed system tools like `just`,
   `git`, `uv`), and where are those resources configured?
6. How is the project's Python environment and dependency installation managed
   for running tests and recipes (the `sync` recipe, `uv`, requirements files,
   and optional dependency groups)?
