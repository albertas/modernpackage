# Research Questions

## Context
Focus on the end-to-end test infrastructure (`tests_e2e/` and `tests/test_e2e.py`),
the backend application template (`backend_template/`), and the frontend template
(`frontend_template/`). The relevant concerns are how scaffolded fullstack
packages are stood up in tests, how the backend exposes routes and persists data,
how the frontend fetches and renders backend data, and how browser-level tests
run against a live stack.

## Questions
1. How do the existing end-to-end tests scaffold a fullstack package and bring
   the stack up and down? Trace the shared helpers in `tests_e2e/_scaffold.py`
   and `tests/test_e2e.py` (clone, metadata, template injection, `just init`,
   compose up/`--wait`, teardown) and note how tools/compose are detected and
   how missing tools cause skips rather than failures.

2. How does the backend application register routes and wire database access?
   Trace `app.py` (the FastAPI factory and lifespan), `health.py` (router
   registration and probe handlers), and `db.py` (declarative `Base`, engine,
   session factory, and the request-scoped session dependency).

3. How are database schema changes defined and applied in the backend template?
   Trace the SQLAlchemy model definition pattern, the Alembic setup
   (`alembic.ini`, `migrations/env.py`, `target_metadata`), the migration
   Justfile recipes, and how `tests_e2e/_scaffold.py` already registers a model
   and drives migrations host-side against the running database.

4. How does the frontend fetch data from the backend and render it, and how is
   the typed API client produced? Trace `frontend_template/src/App.tsx`, the
   Vite dev/preview proxy configuration (`vite.config.ts`), the client module
   (`src/client/index.ts`), and the `generate-client` flow (`openapi-ts.config.ts`).

5. How are browser-level (Playwright) end-to-end tests structured and executed?
   Trace `frontend_template/e2e/`, `playwright.config.ts`, the `frontend-test-e2e`
   Justfile recipe, and how the existing fullstack e2e test invokes it against
   the live compose stack (including how browser-install failures are handled).

6. What conventions govern the generated package's Justfile recipes and the
   token-rename step? Identify where backend and frontend recipes are defined
   (`modernpackage/main.py`), how `just init` renames the `modernpackage` token
   across injected backend and frontend files, and which recipes are excluded
   from the `check` chain and why.
