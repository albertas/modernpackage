# Research Questions

## Context
Focus on the project's end-to-end test infrastructure (`tests/test_e2e.py`, the
`tests_e2e/` directory, and any shared scaffold helpers), the `Justfile`
recipes that run and alias these tests, and the pytest/coverage configuration in
`pyproject.toml`. Also examine the package scaffolding code in
`modernpackage/main.py` and the generated package's own `just check` / `just
init` flow that the e2e tests exercise.

## Questions
1. How are end-to-end tests selected and executed? Trace the `Justfile` `e`,
   `test-e2e`, and `test` recipes, the `pytest` `addopts`/markers/`norecursedirs`
   settings and coverage flags in `pyproject.toml`, and how the `e2e` marker
   interacts with the default `-m 'not e2e'` selection when the alias runs.

2. What does each end-to-end test actually do? Enumerate the tests in
   `tests/test_e2e.py` and `tests_e2e/`, and trace the common scaffold flow they
   use (clone, metadata write, strip, template injection, `just init`) and what
   each asserts.

3. How is the package installed and made available inside the scaffolded package
   during e2e tests — where, if anywhere, does editable-mode installation happen,
   and how does the generated package resolve the `modernpackage`/`vupi`
   tooling it depends on?

4. How does the scaffolding code in `modernpackage/main.py` work? Trace
   `_write_package_metadata`, `_strip_scaffolding`, `_add_backend`,
   `_inject_templates`, `normalize_module_name`, and `just init`, and what
   inputs/state they require to produce a package that passes `just check`.

5. What external tooling and runtime environment do the e2e tests depend on
   (git, just, uv, npm, docker/podman compose, network for `pip-audit`/`uv
   sync`), how are missing dependencies handled (skips vs failures), and which
   are present in this environment?

6. When the e2e suite is run via the Justfile alias right now, what is the
   concrete failure? Run `just e` (or `just test-e2e`) and capture the failing
   test names, error messages, and the stage at which each fails.

7. What is the generated package's `just check` composed of, and how do its
   sub-checks (format, lint, complexity, typecheck, test, audit) behave when run
   against a freshly scaffolded and then modified package?
