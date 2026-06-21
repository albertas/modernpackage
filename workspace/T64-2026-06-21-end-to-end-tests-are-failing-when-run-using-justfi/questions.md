# Research Questions

## Context
Focus on the repository's end-to-end test setup: the `e2e`-marked tests under
`tests/` and `tests_e2e/`, the pytest configuration in `pyproject.toml`, the
Justfile recipes that invoke them, and the package-scaffolding code in
`modernpackage.main` together with the `backend_template`/`frontend_template`
trees that the tests exercise. Examine how these pieces fit together and where
test collection, environment setup, and the scaffold flow can diverge.

## Questions
1. How are the `e2e`-marked tests defined, located, and discovered — what
   pytest configuration (markers, `addopts`, test paths, import mode, recursion
   settings) governs collection, and how do the per-directory layouts of
   `tests/` and `tests_e2e/` (presence/absence of `__init__.py`, shared helper
   modules, conftest) affect it?

2. What Justfile recipes run the end-to-end tests (including the `e` /
   `test-e2e` aliases and their prerequisites), exactly what command lines do
   they expand to, and how do those command lines interact with the
   `pyproject.toml` pytest defaults?

3. How do the existing end-to-end tests obtain the package under test — do they
   clone the committed checkout, install in editable mode, or use another
   mechanism — and what helper functions in the test modules and
   `modernpackage.main` perform scaffolding, metadata writing, stripping,
   template injection, and `just init`?

4. What does the generated package's `just check` chain execute (format, lint,
   complexity, typecheck, test, audit), and what external tools, network
   access, services, or runtime versions does each step require?

5. In the existing end-to-end tests, how are modifications applied to an
   already-scaffolded package (e.g. adding models, routers, migrations, or
   frontend files), and how is the package re-verified after those
   modifications?

6. What environment and tooling prerequisites do the end-to-end tests assume or
   guard against (required executables, compose/Node toolchains, Python version,
   git identity, port/database configuration), and how are missing prerequisites
   currently handled (skips vs. failures)?
