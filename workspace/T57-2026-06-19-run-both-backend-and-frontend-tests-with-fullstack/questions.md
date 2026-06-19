# Research Questions

## Context
Focus on the end-to-end test layer (`tests/test_e2e.py`), the package
generation code in `modernpackage/main.py`, and the two template trees
(`backend_template/`, `frontend_template/`). Also examine the Justfile recipe
wiring and the CI configuration that runs the test suite.

## Questions
1. How does the end-to-end test layer scaffold a package from the local
   checkout, and how does it invoke and assert on the generated package's
   `just check` / test commands? What pytest markers, fixtures, and tool/skip
   guards does it use?
2. How are the backend template's tests defined and executed in a generated
   package — what test runner, dependencies, and Justfile recipes are involved,
   and how do they fit into the generated `check` chain?
3. How are the frontend template's tests defined and executed — what scripts in
   `package.json`, what runner, and which Justfile recipes (e.g. the
   `frontend-*` recipes) drive them, and are those recipes part of the `check`
   chain?
4. How does package generation inject the frontend and backend templates for a
   `--fullstack` build (trace `_inject_templates`, `_add_frontend`,
   `_add_backend`, and the recipe/dependency appenders), and how do injected
   files get token-renamed and staged?
5. What runtime tooling does the test and CI environment provide (Node/npm,
   database, network), and how do the existing recipes and tests account for
   tooling that may be absent?
6. What is the existing relationship between the `check` chain and recipes that
   require external runtimes (databases, Node) — which recipes are deliberately
   excluded from `check`, and why?
