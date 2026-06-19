# Design Discussion

## Current State

A fullstack e2e test already exists:
`test_scaffolded_fullstack_package_passes_check` (`tests/test_e2e.py:272-369`).
It scaffolds a `--fullstack` package through the production injection path
(`main._inject_templates(..., fullstack=True)`, `test_e2e.py:309`), runs the
generated `just check` (backend pytest only) and `just frontend-test`
(`vitest run`). But it proves only that *well-formed files* are produced — it
does **not** prove the application runs:

- Backend pytest uses fakes — `_FakeEngine`/`_FakeConnection` and
  `dependency_overrides` (`backend_template/tests/test_app.py:18-43`). No live
  Postgres, no migrations executed, `/readyz` never hits a real `SELECT 1`.
- Frontend Vitest renders `<App/>` only and asserts a heading
  (`frontend_template/src/App.test.tsx:1-10`); `App.tsx` makes no API calls. No
  HTTP, no real backend connection.
- The generated API client is a hand-written placeholder
  (`frontend_template/src/client/index.ts:1-4`); `generate-client`
  (`main.py:608-609`) and `frontend-build` are defined but never invoked
  (research Q2 "Left unexercised"; Open Areas).
- No test runs `compose.yml` / `Containerfile` at runtime — container behavior
  is asserted only by file-content checks (`test_e2e.py:186-192`).

The production run path the package ships is `compose.yml` (`backend_template/compose.yml`):
three services — `db` (postgres:17, `pg_isready` healthcheck), `migrate`
(`alembic upgrade head`, waits on `db: service_healthy`), and `app` (uvicorn
`--factory`, waits on `migrate: service_completed_successfully`,
`compose.yml:4-14`). `app` publishes `127.0.0.1:8000:8000` (`compose.yml:7`) and
its container `HEALTHCHECK` hits `/readyz` (`Containerfile:24-25`).

## Desired End State

A new e2e test that proves the scaffolded fullstack application is **genuinely
functional**, exercising the three pillars the existing test skips:

1. **Backend runtime + DB integration.** Bring the stack up via the shipped
   compose file (`db` + `migrate` + `app`). Compose `up --wait` succeeding
   already proves: Postgres healthy, migrations applied, and `app`'s `/readyz`
   healthcheck passing. Then assert from the host that
   `GET http://127.0.0.1:8000/livez` returns 200 `{"status":"pass"}` and
   `GET /readyz` returns 200 (a real `SELECT 1` over a real engine —
   `health.py:19-46`).
2. **Backend↔frontend integration.** With the backend live, run
   `just generate-client` (`main.py:608-609`) so `@hey-api/openapi-ts` fetches
   `http://localhost:8000/openapi.json` (`openapi-ts.config.ts:4-6`) and
   regenerates `src/client/`. Assert the regenerated client references the real
   `/livez` and `/readyz` operations (i.e. it is no longer the placeholder).
3. **Frontend builds against the real client.** Run `just frontend-build`
   (`tsc --noEmit && vite build`, `main.py:601-602`) and assert it succeeds and
   emits `frontend/dist/`.

**Verification:** `just test-e2e` (`Justfile:17-18`) runs the new test green on a
machine with compose + Node; environments lacking the required tools skip
cleanly (no failure). All containers/volumes are torn down afterward.

## Patterns to Follow

- Test shape: `@pytest.mark.e2e`-decorated top-level `def test_*`, no classes
  (`test_e2e.py:272`); register nothing new (marker already in
  `pyproject.toml:42-44`).
- Skip guard: loop over a `REQUIRED_TOOLS`-derived tuple and `pytest.skip` per
  missing tool (`test_e2e.py:286-289`). Extend with the chosen compose command
  detection.
- Subprocess: reuse `_run()` (`test_e2e.py:39-51`) —
  `subprocess.run(..., check=False, capture_output=True, text=True)`; assert on
  `returncode` with an f-string carrying `stdout`/`stderr`
  (`test_e2e.py:296, 316, 319`).
- Scaffolding sequence: `git clone REPO_ROOT` → `_write_package_metadata` →
  `_strip_scaffolding` → `_inject_templates(fullstack=True)` → `just init` with
  `os.environ | _GIT_IDENTITY_ENV` (`test_e2e.py:295-316`). Reuse verbatim.
- `frontend-install` must run before any other frontend recipe — `frontend-test`
  / `generate-client` / `frontend-build` do not depend on it
  (`test_e2e.py:321-323`, research Q4).
- Graceful boundary degradation for the compose-detection helper: probe with
  `check=False` and inspect `returncode`, matching the helper convention across
  `main._*` (research Cross-Cutting).

**Patterns to NOT follow:**

- Do **not** mirror the faked-DB approach of `test_app.py:18-43` — defeating the
  whole point of this test is to run a real database.
- Do **not** assert backend health by reading files (as `test_e2e.py:186-192`
  does); assert by making real HTTP requests against the running service.
- Do **not** trust the committed `frontend_template/openapi.json` snapshot — the
  generator reads the live URL, not the file (research Q6); the backend must be
  up before `generate-client`.

## Design Decisions

1. **New test, not an edit of the existing one** — keep
   `test_scaffolded_fullstack_package_passes_check` (cheap, no-container scaffold
   check) and add `test_fullstack_package_runs_end_to_end`. Mirrors the
   one-concern-per-test convention of the existing four e2e tests.
2. **Run via the shipped `compose.yml`, not ad-hoc uvicorn + Postgres** — it is
   the documented production run path and transitively exercises `Containerfile`,
   the `migrate` service, and the dependency ordering. Maximum realism, least
   bespoke wiring.
3. **`compose up --wait` as the primary integration assertion** — `--wait`
   blocks until healthchecks pass; the `app` healthcheck *is* `/readyz`
   (`Containerfile:24-25`), so a successful `--wait` already proves DB + migrate
   + app readiness. Host-side HTTP assertions are confirmation, not the only
   signal.
4. **Compose command auto-detection** — probe `docker compose`, then
   `podman compose`, then `podman-compose` (the portability set named in
   `compose.yml:1`); skip if none found, alongside the `npm` guard.
5. **HTTP from the stdlib `urllib.request`**, not `httpx` — `httpx` is a
   *backend-template* dev dep, not guaranteed in the outer repo's test env;
   `urllib` is exactly what the `Containerfile` healthcheck uses
   (`Containerfile:25`).
6. **Integration proven via `generate-client` + `frontend-build`**, not a
   browser/dev-server flow — these are deterministic, CI-friendly, and directly
   exercise the schema-sync wiring (research Open Areas) without Playwright or a
   running Vite server.
7. **Mandatory teardown in `try/finally`** — `compose down -v` (remove volumes)
   runs even on assertion failure to avoid leaking containers/the `pgdata`
   volume and to free port 8000 for reruns.

## What We're NOT Doing

- Not removing or weakening the existing scaffold-only fullstack test.
- Not driving a browser, Playwright, or the Vite dev server / `/api` proxy
  (`vite.config.ts:5-11`).
- Not adding new application code, endpoints, or a real DB-backed model — testing
  the template as shipped only.
- Not adding `frontend-check` (format/lint/typecheck) — out of scope, as in the
  existing test (`test_e2e.py:329-330`).
- Not changing `just check` to include backend/frontend service recipes — they
  stay excluded by design (`main.py:577-578, 590-594`).
- Not publishing/pulling images beyond what `compose build` needs.

## Open Risks

- **Compose/Node availability & runtime cost:** the test pulls `postgres:17`,
  builds the app image, and runs `npm ci` + `vite build` — minutes-long and
  network-dependent. Mitigated by skip guards; document in the module/test
  docstring (matching `test_e2e.py:1-15`).
- **Port 8000 contention** in CI/parallel runs (`compose.yml:7` binds a fixed
  host port). If flaky, consider a project-scoped compose project name or
  override port; flag for the planning phase.
- **`openapi.json` path vs `/api` proxy mismatch:** the schema exposes
  `/livez`,`/readyz` at root while the dev proxy expects `/api` (research Q6).
  `generate-client` reads the root `openapi.json` directly, so this does not
  block the test, but assertions must target the root paths.
- **Client placeholder vs regenerated shape:** assert on stable substrings
  (`livez`, `readyz`) rather than exact generated file structure, which
  `@hey-api/openapi-ts` versions may change.
- **Cleanup leakage** if the process is killed mid-run (no `finally`); rely on
  `try/finally` and document that a manual `compose down -v` may be needed after
  a hard kill.
