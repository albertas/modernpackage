# Design Discussion

## Current State

Two e2e tests exist, sharing a scaffold/compose/http vocabulary:

- **Backend-only** `tests_e2e/test_backend_e2e.py:22-95` — scaffolds a backend
  package via `scaffold_backend_package` (`tests_e2e/_scaffold.py:132-168`),
  exposes the db port (`_expose_db_port`, `_scaffold.py:83-102`), brings up
  compose with `--wait`, registers a `Product` model (`_register_product_model`,
  `_scaffold.py:121-129`), drives `just makemigration`/`just migrate` host-side
  with `_HOST_DATABASE_URL` (`_scaffold.py:80`), and asserts a version file
  contains `create_table('products')` plus a post-migration `/readyz` 200. It
  proves migrations apply but **never adds endpoints or reads data back**.

- **Fullstack** `tests/test_e2e.py:424-550` — scaffolds with
  `_inject_templates(fullstack=True)` (`:463`), brings up compose, asserts
  `/livez` + `/readyz`, runs `frontend-install` → `generate-client` →
  `frontend-build`, then `just frontend-test-e2e` (Playwright). The only browser
  assertion is the shipped status spec (`frontend_template/e2e/status.spec.ts:3-8`):
  heading + `healthy` + `ready`. It proves **the stack boots**, not that a
  DB-backed feature works.

The backend ships health routes only (`backend_template/modernpackage/health.py`),
mounted with no prefix (`app.py:33`). There is a request-scoped session dep
`DbSessionDep` (`db.py:60`) that no shipped route uses. The frontend renders
heading + health via native `fetch` (`App.tsx:6-17`, `:36-46`) and does **not**
use the generated client. Vite proxies `/api`, `/livez`, `/readyz` →
`localhost:8000` for both `server` and `preview` (`vite.config.ts:9-21`).

**Gap:** no test creates a row and reads it back through the rendered frontend.

## Desired End State

A new test `tests_e2e/test_fullstack_feature_e2e.py` that, against a real
compose stack, proves a products feature works end to end:

1. Scaffold a **fullstack** package.
2. Inject a `Product` model, backend `POST`/`GET /api/products` endpoints, and a
   frontend products-list page.
3. Bring up the stack; run the products migration host-side.
4. Create a product via host-side `POST /api/products`; assert it reads back via
   host-side `GET /api/products`.
5. Run a Playwright spec asserting the created product's name is visible on the
   page (the browser reads it through the `vite preview` proxy → live backend).

**Verification:** `just test-e2e` (or the marked test) passes where compose +
Node + browsers are available; skips (never fails) where they are not. The
Playwright spec sees the seeded product name in the DOM.

## Patterns to Follow

- **Skip-not-fail discipline** — loop `shutil.which` over required tools and
  `pytest.skip` (`test_backend_e2e.py:23-25`); `_detect_compose_command` → skip
  on `None` (`_scaffold.py:50-64`); Playwright browser-install failure → skip
  (`tests/test_e2e.py:539-545`). `_run(check=False)` everywhere (`_scaffold.py:28-40`).
- **Teardown in `try/finally`** with `compose down -v` (`test_backend_e2e.py:94-95`).
- **Host-side migration seam** — `_expose_db_port` before `up`
  (`test_backend_e2e.py:45`), then `just makemigration`/`just migrate` with
  `os.environ | {'DATABASE_URL': _HOST_DATABASE_URL}` (`:65-79`).
- **Model registration by appending to `db.py`** so `Base.metadata` carries the
  table for autogenerate (`_register_product_model`, `_scaffold.py:121-129`;
  `env.py` imports `Base`).
- **Router shape** — `APIRouter()` + `Depends`, async handlers
  (`health.py:14,31-46`); use `DbSessionDep` (`db.py:60`) for session access.
- **Frontend data fetch** — native `fetch(path)` + `response.json()`
  (`App.tsx:6-17`); route products under `/api/...` so the Vite proxy forwards
  it (`vite.config.ts:10,17`).
- **Playwright spec** — `page.goto('/')` + `getByText(...).toBeVisible()`
  auto-waits (`status.spec.ts:3-8`).
- **Stable-substring assertions** over exact generated structure
  (`test_e2e.py:503-520`, `test_backend_e2e.py:82-89`).

**Do NOT follow:** App.tsx's avoidance of the generated client is fine to mirror
for simplicity, but do not try to wire the typed `@hey-api` client — it only
exists post-`generate-client` and is regenerated, not committed (research Q4,
Open Areas). Keep using native `fetch`. Also do not de-duplicate the two
compose-detection blocks (research Cross-Cutting) — out of scope.

## Design Decisions

1. **Test location**: new file `tests_e2e/test_fullstack_feature_e2e.py`, not an
   extension of `tests/test_e2e.py` — the task says "in the `tests_e2e/`
   directory", and `_scaffold.py` already lives there as the shared helper home.
2. **Reuse + extend `_scaffold.py`**: add `scaffold_fullstack_package(tmp_path)`
   mirroring the fullstack flow (`test_e2e.py:447-470`: clone → metadata → strip
   → `_inject_templates(fullstack=True)` → `just init`) and reuse all existing
   helpers (`_run`, `_detect_compose_command`, `_http_get`, `_expose_db_port`,
   `_register_product_model`, `_HOST_DATABASE_URL`, `_GIT_IDENTITY_ENV`). Add
   `npm` to the runtime tool list for this test (`test_e2e.py:35`).
3. **Feature injection runs AFTER `just init`** (the model/endpoints/page are not
   part of the template), so injected source must reference the **renamed**
   module name, never the literal `modernpackage` token (init's sed already ran,
   `Justfile:60-74`). New helper `_register_products_feature(destination,
   module_name)` parameterizes imports on `module_name`.
4. **Backend endpoints in a new `products.py` module**, mounted with prefix
   `/api` (`app.include_router(products_router, prefix='/api')`). Inject the
   module file, then edit `app.py` by anchoring on the unique line
   `app.include_router(health_router)` (`app.py:33`) and appending the products
   include after it. `GET /api/products` lists; `POST /api/products` inserts and
   returns the row — both use `DbSessionDep` and async SQLAlchemy
   (`select`/`session.add`/`commit`). Minimal Pydantic `ProductIn`/`ProductOut`
   so the live openapi/`generate-client` stay valid.
5. **Create via backend POST, read via frontend**: the task's "create" path is
   the host-side `POST /api/products`; the "read back through the frontend page"
   path is the Playwright assertion. No UI creation form — keeps scope to the
   "products list page" the task names.
6. **Add `_http_post_json(url, payload)` to `_scaffold.py`** (urllib, JSON body,
   returns `(status, body)`), mirroring `_http_get` (`_scaffold.py:67-77`).
7. **Frontend**: replace `App.tsx` wholesale with a version that **preserves**
   heading + health (so `status.spec.ts` still passes) and adds a products
   section that `fetch('/api/products')` on mount and renders names in a `<ul>`.
   Add `e2e/products.spec.ts` asserting the seeded name is visible. Replacing in
   full is lower-risk than surgically patching TSX.
8. **Seed name is a deterministic literal** (e.g. `'E2E Widget'`) shared between
   the host-side POST and the Playwright spec text.
9. **Ordering**: scaffold → register feature files → `_expose_db_port` → compose
   `up --wait --build` (image bakes in model + endpoints) → `/livez`+`/readyz` →
   host-side `makemigration`+`migrate` (creates `products` table) → POST create →
   host-side GET assert → `frontend-install`/`generate-client`/`frontend-build`
   → `frontend-test-e2e` → `finally: down -v`. Migration runs after `up` because
   the table is autogenerated host-side, exactly as the backend test does.

## What We're NOT Doing

- No UI creation form, no update/delete endpoints — only create/read per task.
- Not committing a products migration into the template (autogenerated host-side,
  ephemeral, as in `test_backend_e2e.py`).
- Not using the typed generated client in App.tsx; native `fetch` only.
- Not refactoring or relocating the existing `tests/test_e2e.py` fullstack test.
- Not de-duplicating the compose-detection blocks.
- Not adding the new recipes-or-template changes to `modernpackage/main.py`; the
  feature is injected by the test helper, not shipped in the scaffold.

## Open Risks

- **`app.py` edit anchor**: `app.include_router(health_router)` (`app.py:33`) is
  currently unique; the helper must assert the anchor is present before replacing
  (mirror `_expose_db_port`'s assert, `_scaffold.py:100`).
- **Migration timing**: app starts before the `products` table exists; `/readyz`
  only does `SELECT 1` so it stays green. POST must run only after `just migrate`.
- **Vite preview proxy**: products must sit under `/api` or the browser request
  is not forwarded (`vite.config.ts:17`). Endpoints are mounted with `/api`.
- **React render timing**: products fetch is async on mount; rely on Playwright's
  auto-waiting `toBeVisible()` rather than fixed sleeps.
- **`generate-client` must still succeed** now that openapi includes products —
  keep the Pydantic response models well-formed; assert only on stable
  substrings if the client is inspected at all.
- **Runtime cost**: pulls `postgres:17`, builds the app image, runs `npm ci` +
  `vite build` + browser download — minutes-long and network-dependent (same
  caveat as `test_e2e.py:434-437`); guarded by skips.
