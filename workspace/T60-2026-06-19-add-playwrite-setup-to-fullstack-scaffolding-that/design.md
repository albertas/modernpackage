# Design Discussion

## Current State

The scaffolding CLI injects an isolated React/Vite frontend under `frontend/`
only when `--fullstack` is passed (`_add_frontend`, `main.py:962-977`), via a
single `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend')`.
Frontend Justfile recipes are appended from the `_FRONTEND_RECIPES` constant
(`main.py:595-614`); there is **no** frontend dependency appender — all npm deps
live directly in `frontend_template/package.json` (`research.md:14`).

Today the frontend is a stub: `App.tsx:1-3` renders only `<h1>modernpackage</h1>`
with no state, no fetch, no client usage. The generated API client is a
hand-written placeholder exporting `Record<string, unknown>` types
(`src/client/index.ts:1-4`), regenerated against the live backend's
`/openapi.json` only at e2e time (`test_e2e.py:498`). The backend exposes the
integration contract: `GET /livez` → always `200 {"status":"pass"}`
(`health.py:31-34`) and `GET /readyz` → `200` when the DB is reachable else
`503 {"status":"fail"}` (`health.py:37-46`).

Frontend testing is **Vitest + Testing Library only** (jsdom), configured in
`vite.config.ts:12-17`; the sole test asserts the heading
(`App.test.tsx:5-9`). The dev server proxies only `/api` →
`http://localhost:8000` (`vite.config.ts:7-11`) — health endpoints at the root
(`/livez`, `/readyz`) are **not** proxied. The existing "end-to-end" test
(`test_fullstack_package_runs_end_to_end`, `test_e2e.py:424-532`) brings up the
compose stack, probes HTTP, regenerates the client, and runs `vite build`, but
performs **no browser automation**. Playwright is entirely absent everywhere
(`research.md:88-89`).

Node/DB/container checks are always on-demand: never in the `check` chain, never
in CI; only `@pytest.mark.e2e` tests run them via `just test-e2e`
(`research.md:84`, `pyproject.toml:39-44`).

## Desired End State

A `--fullstack`-generated package ships:

1. **A status page** in `App.tsx` that fetches the backend health endpoints and
   renders application health (from `/livez`) and database health (from
   `/readyz`), degrading gracefully to a "checking…/unavailable" state when the
   backend is unreachable — a working frontend-to-backend integration demo.
2. **A Playwright e2e setup** under `frontend/e2e/` with config, a `@playwright/test`
   dev dependency, an npm script, and a Justfile recipe that drives a real
   browser against the served frontend + live backend stack and asserts the
   status page reflects real health.

**Verification:**
- `just check` (repo and generated package) stays green — Playwright excluded.
- `just frontend-test` (Vitest) still passes; the status-page unit test mocks
  `fetch` and asserts rendered health labels.
- `just frontend-test-e2e` passes against a running stack (browser asserts
  "healthy"/"ready" text), exercised by an extended/new `@pytest.mark.e2e` test.
- Existing e2e assertions (`test_e2e.py:418-421`, `:507-520`) still hold.

## Patterns to Follow

- **Frontend ships in the template, copied wholesale.** Add Playwright config,
  `e2e/` specs, and package.json deps directly to `frontend_template/`;
  `_add_frontend`'s copytree (`main.py:962-977`) carries them. No new appender.
- **On-demand recipes, never in `check`.** Append the Playwright recipe to
  `_FRONTEND_RECIPES` (`main.py:595-614`), mirroring `frontend-test`/`generate-client`.
  The generated `check:` must keep excluding `frontend-` (asserted
  `test_e2e.py:418-421`) — Playwright needs Node + browsers + a DB.
- **Skip-guard runtime tools.** Follow `_REQUIRED_RUNTIME_TOOLS` /
  `_detect_compose_command` (`test_e2e.py:60-88`, `:440-445`): skip, don't fail,
  when npm/compose/browsers are absent.
- **Assert on stable substrings.** Like `test_e2e.py:507-520` asserts `livez`/
  `readyz` substrings (not exact generated structure), browser assertions should
  target stable status text, not DOM internals.
- **`cd frontend &&` recipe scoping** with no `: sync` dep (`main.py:593-594`).
- **Preserve the literal `modernpackage` token** in all injected files so
  `just init`'s sed rename rewrites it (`research.md:83`, `test_main.py:1646`).
- **Pattern NOT to follow:** do not call backend health via absolute
  `http://localhost:8000` URLs from `App.tsx` (CORS, hard-coded host). Route
  through Vite proxy paths instead (see Decision 3).

## Design Decisions

1. **Playwright lives in `frontend_template/`, tests under `frontend/e2e/`** —
   it is browser/frontend tooling. `@playwright/test` added to package.json
   `devDependencies`; `playwright.config.ts` at the frontend root with
   `testDir: './e2e'`. Carried by the existing copytree; no CLI dependency
   appender needed.

2. **Keep Vitest and Playwright separate by directory + glob.** Playwright specs
   use `e2e/*.spec.ts`; Vitest keeps `src/**/*.test.tsx` and excludes `e2e/`
   (add `test.exclude` in `vite.config.ts`). Prevents Vitest from collecting
   browser specs and vice versa.

3. **Status page reaches the backend through Vite proxy paths.** Add `/livez`
   and `/readyz` to the proxy (`vite.config.ts:7-11`) for both `server` and
   `preview` (Playwright serves the built app via `vite preview`). `App.tsx`
   fetches same-origin relative paths — no CORS, no hard-coded host. (Using the
   generated typed client is optional; the placeholder client makes a plain
   `fetch` the simpler, always-working default — see Risks.)

4. **`App.tsx` fetches health on mount and degrades gracefully.** Initial state
   "checking…", then "healthy"/"unhealthy" (app) and "ready"/"not ready" (db)
   from response status/body; on fetch failure, "unavailable". Keeps the
   `modernpackage` heading so the existing render assertion stays valid.

5. **Status-page unit test mocks `fetch`.** A new/updated `App.test.tsx` stubs
   `globalThis.fetch` to return pass/fail bodies and asserts rendered labels;
   runs under existing jsdom Vitest with no backend. The heading assertion
   (`App.test.tsx:5-9`) is preserved.

6. **Playwright orchestrated via its own `webServer`.** `playwright.config.ts`
   uses `webServer: { command: 'npm run preview', url: '…' }` to launch the
   built frontend; the backend stack is brought up by compose in the e2e test
   (Decision 7). Browser install handled by the recipe (`npx playwright install
   --with-deps chromium`) or skip-guarded in the test.

7. **One Justfile recipe `frontend-test-e2e`, plus a Python e2e step.** Append
   the recipe to `_FRONTEND_RECIPES`. Extend
   `test_fullstack_package_runs_end_to_end` (`test_e2e.py:424-532`) — already
   has compose up + client regen + build — to run `just frontend-test-e2e`
   inside the `try` block while the stack is live, after `frontend-build`.
   Add npm/browser skip guards.

8. **Update affected unit tests, not the `check`/CI gates.** Update
   `test_append_frontend_recipes` and the frontend-injection assertions in
   `tests/test_main.py` (`research.md:19`) to expect the new recipe/files.
   Leave `pyproject.toml`, repo `Justfile` `check`, and both CI configs
   untouched (`research.md:79-80`).

## What We're NOT Doing

- Not adding Playwright to the `check` chain or to GitHub/GitLab CI.
- Not adding Playwright to the backend or non-fullstack scaffolds.
- Not replacing Vitest/Testing Library — they remain the unit layer.
- Not wiring up `@tanstack/react-query` (declared but unused — `research.md:90`).
- Not creating ORM models or new backend endpoints; `/livez` + `/readyz` are the
  contract.
- Not adding a CLI frontend **dependency** appender; deps stay in package.json.
- Not changing `just init`'s rename, compose, Containerfile, or migrations.

## Open Risks

- **Vite preview proxy.** `server.proxy` does not apply to `vite preview`;
  `preview.proxy` must be set too. If Playwright uses `npm run dev` instead, only
  `server.proxy` matters. Pick one serving mode and configure its proxy.
- **Browser binary availability in CI/e2e.** `npx playwright install` downloads
  browsers (network + minutes); the e2e test must skip-guard cleanly when
  unavailable, like the existing compose/npm guards.
- **Generated client churn.** If the status page uses the typed client, it only
  works after `generate-client` (live backend); the placeholder
  (`Record<string,unknown>`) won't. Defaulting to plain `fetch` (Decision 3)
  avoids coupling the unit test to client regeneration.
- **e2e wall-clock.** Adding Playwright to the already minutes-long fullstack e2e
  (postgres pull, image build, `npm ci`, browser install) lengthens it; it stays
  out of default `check`/CI so this affects only `just test-e2e`.
- **Readyz timing.** `/readyz` returns `503` until DB+migrations are ready;
  compose `--wait` already blocks on the app healthcheck (`test_e2e.py:429-431`),
  so the browser should see "ready" by the time it runs.
