# Structure Outline

## Approach

Build one new e2e test, `tests_e2e/test_fullstack_feature_e2e.py`, that scaffolds
a fullstack package, injects a `Product` feature (model + `/api/products`
endpoints + products-list page), brings up the real compose stack, creates a row
via host-side `POST`, reads it back via host-side `GET`, and finally asserts the
seeded name renders in the browser through Playwright. All injection logic and
HTTP/scaffold helpers extend the existing `tests_e2e/_scaffold.py`; we reuse
`_run`, `_detect_compose_command`, `_http_get`, `_expose_db_port`,
`_register_product_model`, `_HOST_DATABASE_URL`, and `_GIT_IDENTITY_ENV`
unchanged (design decisions 1–2). The work splits into three vertical slices that
each add and verify a complete layer of the round trip.

**Ordering note (applies to every phase):** in the new test, run scaffold +
file-level assertions **before** `_detect_compose_command()` so the file-shape
checks execute even where compose is absent (they then `pytest.skip` at the
compose gate). This makes each phase's cheap assertions agent-runnable
everywhere, mirroring `test_backend_e2e.py:27` → `:41`.

---

## Phase 1: Fullstack scaffold helper

Add a reusable helper that scaffolds a **fullstack** package (db + backend +
frontend) and renames the `modernpackage` token, plus a minimal test that proves
the scaffold lands all three layers. Establishes the foundation later phases
inject into.

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_fullstack_feature_e2e.py` (new)

**Key changes**:
- `scaffold_fullstack_package(tmp_path: Path) -> tuple[Path, str]` — new in
  `_scaffold.py`. Mirrors `scaffold_backend_package` (`_scaffold.py:132-168`) but
  calls `main._inject_templates(destination, fullstack=True)` instead of
  `main._add_backend` (see `tests/test_e2e.py:454-470`). Returns
  `(destination, module_name)` for `package_name = 'fullstack-feature.pkg'`.
- `_REQUIRED_RUNTIME_TOOLS: tuple[str, ...] = (*REQUIRED_TOOLS, 'npm')` — new
  constant in the test file (design decision 2; `test_e2e.py:35`).
- Test `test_fullstack_feature_runs_end_to_end(tmp_path)` skeleton with
  `@pytest.mark.e2e`, tool-skip loop, and Phase-1 file assertions.

**Verify**: `just test-e2e` (or `uv run pytest -m e2e
tests_e2e/test_fullstack_feature_e2e.py`) runs the scaffold and asserts, before
the compose gate: `(destination/module_name/'app.py').exists()`,
`(destination/'frontend'/'src'/'App.tsx').exists()`,
`(destination/'frontend'/'playwright.config.ts').exists()`,
`'frontend-test-e2e:' in (destination/'Justfile').read_text()`, and no
`'modernpackage'` token remains in `*.py` source. On a host without compose/node
the test still reaches and passes these assertions, then skips.

---

## Phase 2: Backend products feature (model → migration → API → host HTTP)

Inject the `Product` model, a `products.py` router mounted at `/api`, wire it
into `app.py`, run the migration host-side, then `POST` a product and `GET` it
back over HTTP. Proves a DB-backed feature works end to end at the API level —
independently valuable even if Phase 3's browser run is skipped.

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_fullstack_feature_e2e.py`

**Key changes**:
- `_SEED_PRODUCT_NAME: str = 'E2E Widget'` — shared literal (design decision 8).
- `_PRODUCTS_ROUTER_SOURCE: str` — module-source constant defining
  `router = APIRouter()`, Pydantic `ProductIn { name: str }` / `ProductOut {
  id: int; name: str }`, async `GET /products` (`select(Product)`) and
  `POST /products` (`session.add` + `commit` + return row), all using
  `DbSessionDep` (`db.py:60`). Imports parameterized on the renamed module
  (design decision 4).
- `_register_products_feature(destination: Path, module_name: str) -> None` — new
  in `_scaffold.py`. Calls `_register_product_model(source_dir)`, writes
  `source_dir/'products.py'` from `_PRODUCTS_ROUTER_SOURCE.format(module=module_name)`,
  then edits `app.py` by asserting the anchor `app.include_router(health_router)`
  (`app.py:33`) is present and appending
  `app.include_router(products_router, prefix='/api')` after it (design decision
  4; assert-before-replace per Open Risks).
- `_http_post_json(url: str, payload: dict, timeout: float = 30.0) -> tuple[int, str]`
  — new in `_scaffold.py`, mirroring `_http_get` (`_scaffold.py:67-77`): urllib
  request with JSON body + `Content-Type: application/json`, returns
  `(status_code, body)`, returns HTTP error status rather than raising.
- Test body extends Phase 1: `_register_products_feature(...)` →
  `_expose_db_port` → `compose up -d --wait --build` → assert `/livez` + `/readyz`
  200 → host-side `just makemigration 'add products'` + `just migrate` with
  `os.environ | {'DATABASE_URL': _HOST_DATABASE_URL}` → `_http_post_json` create →
  `_http_get` read-back. Teardown `compose down -v` in `finally`.

**Verify**: `just test-e2e` passes where compose is available. Concretely the
test asserts: `POST http://127.0.0.1:8000/api/products` with `{"name": "E2E
Widget"}` returns 200/201 and body contains `"E2E Widget"`; subsequent
`GET http://127.0.0.1:8000/api/products` returns 200 and body contains `"E2E
Widget"`; the autogenerated version file under `migrations/versions/` contains
`create_table('products')` (stable-substring, `test_backend_e2e.py:82-89`).

---

## Phase 3: Frontend products page + Playwright read-through

Replace `App.tsx` with a version that preserves the health `<dl>` (so
`status.spec.ts` still passes) and adds a products `<ul>` fetched from
`/api/products`; add `e2e/products.spec.ts` asserting the seeded name is visible.
Completes the task: the browser reads the created row through the
`vite preview` proxy → live backend.

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_fullstack_feature_e2e.py`

**Key changes**:
- `_APP_TSX_SOURCE: str` — full `App.tsx` replacement preserving the
  `modernpackage` heading + health `<dl>` (`App.tsx:36-46`) and adding a
  `useEffect` that `fetch('/api/products')` on mount and renders `name`s in a
  `<ul>` via native `fetch` (design decision 7; no generated client).
- `_PRODUCTS_SPEC_SOURCE: str` — `e2e/products.spec.ts`: `page.goto('/')` +
  `getByText('E2E Widget').toBeVisible()` (auto-waits; `status.spec.ts:3-8`).
- `_register_products_page(destination: Path) -> None` — new in `_scaffold.py`:
  overwrites `frontend/src/App.tsx` with `_APP_TSX_SOURCE` and writes
  `frontend/e2e/products.spec.ts` from `_PRODUCTS_SPEC_SOURCE`. Called in Phase 1
  scaffold region (before `just init` so files are git-staged and token-renamed,
  per research Q6) — `_register_products_page` writes the heading token
  `modernpackage` so init's sed renames it consistently.
- Test body extends Phase 2 after the host-side GET: `just frontend-install` →
  `just generate-client` → `just frontend-build` (assert `frontend/dist/index.html`)
  → `just frontend-test-e2e` with the Playwright-install skip guard
  (`test_e2e.py:538-548`).

**Verify**: `just test-e2e` passes end to end where compose + node + browsers are
available; skips (never fails) at the Playwright-install guard otherwise. The
`products.spec.ts` assertion confirms `E2E Widget` is visible in the rendered DOM
(browser → `vite preview` :4173 → live backend :8000). `just generate-client`
must still exit 0 with the products operations in openapi (Open Risks); assert
client text contains `'products'` if inspected.

---

## Testing Checkpoints

- **After Phase 1**: `scaffold_fullstack_package` produces a renamed package with
  backend (`app.py`, `db.py`), frontend (`App.tsx`, `playwright.config.ts`), and
  frontend recipes in the `Justfile`; no `modernpackage` token remains in `*.py`.
  Cheap file assertions pass even without compose.
- **After Phase 2**: with compose up, `POST /api/products` creates `E2E Widget`
  and `GET /api/products` reads it back (both 200, body contains the name); the
  autogenerated migration contains `create_table('products')`; `/livez` +
  `/readyz` stay 200. The DB-backed feature is proven at the API layer.
- **After Phase 3**: the full round trip passes — the seeded `E2E Widget` is
  visible in the browser DOM via Playwright; `status.spec.ts` still passes
  (health `<dl>` preserved); `generate-client`/`frontend-build` succeed. Missing
  compose/node/browsers → `pytest.skip`, never fail.
