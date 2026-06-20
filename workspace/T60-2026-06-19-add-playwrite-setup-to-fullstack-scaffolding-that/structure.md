# Structure Outline

## Approach

Add a frontend health **status page** plus a **Playwright e2e setup** to the
`--fullstack` scaffold by editing `frontend_template/` (carried wholesale by the
existing `_add_frontend` copytree — no new appender) and appending one on-demand
recipe to `_FRONTEND_RECIPES` in `main.py`. Status page uses plain same-origin
`fetch` through Vite proxy paths; Playwright stays out of `check`/CI, exercised
only by `@pytest.mark.e2e`. Sliced so the integration demo (Vitest-testable, no
browser) lands first, then Playwright tooling, then the recipe, then the live
e2e wiring — each phase independently valuable if a later one is dropped.

---

## Phase 1: Status page + proxy + unit test (browser-less integration demo)

Delivers design pillar 1 end-to-end: `App.tsx` fetches `/livez` + `/readyz` on
mount through the Vite proxy and renders app/db health, degrading to
"unavailable" on failure. Fully verifiable under existing jsdom Vitest.

**Files**: `frontend_template/src/App.tsx`, `frontend_template/src/App.test.tsx`,
`frontend_template/vite.config.ts`

**Key changes**:
- `App(): JSX.Element` — now stateful. Internal state shape:
  `type HealthState = "checking" | "healthy" | "unhealthy" | "unavailable"`
  for app; `"checking" | "ready" | "not ready" | "unavailable"` for db.
- `useEffect` on mount → `fetch('/livez')` and `fetch('/readyz')`; map
  `res.ok` + body `status: "pass"` → healthy/ready, non-ok → unhealthy/not
  ready, thrown/rejected → unavailable. Preserve `<h1>modernpackage</h1>`.
- `vite.config.ts`: add `'/livez'` and `'/readyz'` to `server.proxy`
  (target `http://localhost:8000`, `changeOrigin: true`), mirroring `/api`.
- `App.test.tsx`: keep heading assertion; add cases that stub
  `globalThis.fetch` to return `{ok:true, json:()=>({status:'pass'})}`,
  a 503 fail body, and a rejection — assert rendered "healthy"/"ready",
  "unhealthy"/"not ready", "unavailable" labels respectively.

**Verify**: `cd frontend_template && npm run test` passes (repo dev only). In a
scaffolded fullstack package (`_inject_templates(fullstack=True)`),
`just frontend-test` exits 0; `grep -q '/livez' frontend/vite.config.ts`
succeeds; `grep -q 'modernpackage' frontend/src/App.tsx` succeeds (rename token
preserved).

---

## Phase 2: Playwright tooling in the template

Adds the Playwright config, dependency, npm script, and a spec, and keeps Vitest
and Playwright separated by directory + glob (design Decision 2).

**Files**: `frontend_template/package.json`,
`frontend_template/playwright.config.ts` (new),
`frontend_template/e2e/status.spec.ts` (new),
`frontend_template/vite.config.ts`

**Key changes**:
- `package.json`: add `"@playwright/test": "^1.x"` to `devDependencies`; add
  npm script `"test:e2e": "playwright test"`.
- `playwright.config.ts`: `export default defineConfig({ testDir: './e2e',
  use: { baseURL: 'http://localhost:4173' }, webServer: { command: 'npm run
  preview', url: 'http://localhost:4173', reuseExistingServer: !process.env.CI }
  })` (Decision 6; `vite preview` default port 4173).
- `vite.config.ts`: add `preview.proxy` for `/livez` + `/readyz` (server.proxy
  does NOT cover `vite preview` — Open Risk); add `test.exclude` to keep Vitest
  off `e2e/**` (Decision 2).
- `e2e/status.spec.ts`: `test('status page shows healthy/ready', async ({ page })
  => { await page.goto('/'); await expect(page.getByText(/healthy/i))...;
  await expect(page.getByText(/ready/i))... })` — assert stable status
  substrings, not DOM internals (Patterns).

**Verify**: in a scaffolded package, after `just frontend-install`,
`cd frontend && npx playwright test --list` lists `status.spec.ts` (config
parses); `just frontend-test` still exits 0 and does NOT collect `e2e/`
(`test.exclude` works); `grep -q '@playwright/test' frontend/package.json`.

---

## Phase 3: `frontend-test-e2e` recipe + scaffolder unit tests

Appends the on-demand recipe and updates the `main.py` unit tests so the recipe
ships but stays out of the generated `check:` chain.

**Files**: `modernpackage/main.py` (`_FRONTEND_RECIPES`), `tests/test_main.py`

**Key changes**:
- `_FRONTEND_RECIPES`: append
  ```
  frontend-test-e2e:
    cd frontend && npx playwright install --with-deps chromium && npm run test:e2e
  ```
  (no `: sync` dep; `cd frontend &&` scoping). `frontend-check` unchanged — does
  NOT gain `test:e2e` (keeps `check` browser-free).
- `tests/test_main.py`: extend `test_append_frontend_recipes` to expect
  `frontend-test-e2e`; extend frontend-injection assertions (research Q1
  `:1629-1789`) to expect `playwright.config.ts`, `e2e/status.spec.ts`, and the
  `@playwright/test` dep token. `test_injected_files_have_no_unrenamed_token`
  (`:1646`) must still pass over the new files.

**Verify**: `just check` (repo) passes — `pytest tests/test_main.py` green. In a
scaffolded package, `just --list | grep -q frontend-test-e2e` succeeds and the
`check:` recipe still excludes `frontend-` (assert preserved at
`tests/test_e2e.py:418-421`): `just --dump check | grep -vq frontend-`.

---

## Phase 4: Wire Playwright into the Python e2e test

Runs the browser e2e against the live stack inside the existing fullstack e2e,
skip-guarded on browser/Node availability.

**Files**: `tests/test_e2e.py` (`test_fullstack_package_runs_end_to_end`,
`:424-532`)

**Key changes**:
- Inside the `try` block, after the `frontend-build` assertions (`:522-530`) and
  while compose is still up, run `just frontend-test-e2e` via `_run([...],
  cwd=destination)` and assert `returncode == 0` (browser asserts "healthy"/
  "ready" against the live stack through `vite preview` proxy).
- Add a skip guard for browser unavailability mirroring `_REQUIRED_RUNTIME_TOOLS`
  / `_detect_compose_command` (`:60-88`): if `npx playwright install` fails or
  browsers absent, `pytest.skip(...)` rather than fail (Patterns / Open Risks).
- All existing assertions (`:481-530`) remain unchanged.

**Verify**: `just test-e2e` (i.e. `pytest -m e2e`) — the extended test either
passes end-to-end on a machine with compose + Node + browsers, or skips cleanly
where they are absent (no failure). Confirm with
`pytest -m e2e tests/test_e2e.py::test_fullstack_package_runs_end_to_end -rs`
showing PASS or SKIP, never ERROR/FAIL.

---

## Testing Checkpoints

- **After Phase 1**: scaffolded fullstack `just frontend-test` green; `App.tsx`
  fetches health via proxy paths and renders healthy/ready/unavailable; rename
  token `modernpackage` intact. Integration demo works without any browser.
- **After Phase 2**: `playwright.config.ts` + `e2e/status.spec.ts` +
  `@playwright/test` dep present; `npx playwright test --list` parses; Vitest
  excludes `e2e/`; `preview.proxy` set.
- **After Phase 3**: repo `pytest tests/test_main.py` green; generated package
  exposes `frontend-test-e2e`; `check:` still excludes `frontend-`.
- **After Phase 4**: `just test-e2e` passes or skips cleanly; existing e2e
  assertions still hold. Full pillar-2 browser e2e exercised against live stack.

> Note: Phases 1–3 are fully verifiable in default (browser-free) environments.
> Phase 4 is the only phase whose green path requires compose + Node + browser
> binaries; it is designed to **skip**, not fail, otherwise.
