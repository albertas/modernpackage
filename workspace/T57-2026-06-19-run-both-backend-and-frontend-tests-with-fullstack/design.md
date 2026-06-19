# Design Discussion

## Current State

The e2e layer (`tests/test_e2e.py`) has **three** `@pytest.mark.e2e` tests that scaffold a
package from the *local committed checkout* and assert it passes `just check`:

- `test_scaffolded_package_passes_check` (`tests/test_e2e.py:69`) — no-flag scaffold.
- `test_scaffolded_backend_package_passes_check` (`tests/test_e2e.py:137`) — `--backend`,
  injects via `main._add_backend(...)` + manual `git add -A` (`:158-160`).
- `test_scaffolded_package_has_no_backend_or_frontend` (`tests/test_e2e.py:196`) — negative test;
  asserts frontend is **absent** (`:228-269`).

**There is no `--fullstack` e2e test.** No automated gate runs the generated frontend's Vitest
suite. Frontend is only ever asserted *absent* (research.md Open Areas).

Injection flow for fullstack already exists in `main.py`:
- `init_new_package` → `_inject_templates(path, fullstack=fullstack)` (`main.py:1065-1066`).
- `_inject_templates` (`main.py:979-989`): always `_add_backend`; if fullstack also `_add_frontend`;
  then `_stage_injected_files` (`git add -A`, `:925-943`).
- `_add_frontend` (`main.py:962-976`): copytree into `frontend/`, append `_FRONTEND_RECIPES`; adds
  **no** Python deps, spawns **no** processes.
- Frontend recipes (`_FRONTEND_RECIPES`, `main.py:595-614`): `frontend-install` (`npm ci`),
  `frontend-build`, `frontend-test` (`npm run test` → `vitest run`), `frontend-lint`,
  `generate-client`, aggregate `frontend-check: frontend-install`.
- `frontend-*` recipes are **deliberately excluded from `check`** — generated CI has no Node
  (`main.py:590-594`), mirroring the backend migration-recipe exclusion (`main.py:576-578`).

Backend template tests (`backend_template/tests/test_app.py`) run as normal pytest under the
generated package's `just test` (part of `check`, `Justfile:53`); they fake the DB (`:17-42`), so
no live database is needed.

CI provides **no Node/npm and no database** (`.gitlab-ci.yml:13-22`,
`.github/workflows/check-modernpackage-on-python314.yml`). Default test runs and CI exclude e2e via
`addopts = "... -m 'not e2e'"` (`pyproject.toml:40`); e2e runs only via `just test-e2e`
(`Justfile:17-18`).

## Desired End State

A new e2e test — `test_scaffolded_fullstack_package_passes_check` — that:

1. Scaffolds a fullstack package from the local checkout (clone → metadata → strip →
   `_inject_templates(fullstack=True)` → `git add -A` → `just init`).
2. Runs `just check` and asserts `returncode == 0` — proves the **backend pytest suite** passes
   inside the generated `check` chain.
3. Installs and runs the **frontend Vitest suite** (`just frontend-install` then `just
   frontend-test`) and asserts each `returncode == 0`.
4. Asserts structural expectations: `frontend/` exists with renamed tokens (no literal
   `modernpackage` in `frontend/package.json` / `frontend/src/App.test.tsx`), backend files present,
   and frontend recipes present in the generated `Justfile`.

**Verification**: `just test-e2e` passes locally (where Node/npm is available). The test
`pytest.skip`s when `git`/`just`/`uv`/`npm` are missing, so CI (no Node) skips it cleanly rather
than failing — consistent with the existing Node-exclusion precedent.

## Patterns to Follow

- **Scaffold-from-local-checkout flow**: copy the structure of
  `test_scaffolded_backend_package_passes_check` (`tests/test_e2e.py:137-193`) — clone, metadata,
  strip, inject, stage, init, check, assert.
- **Subprocess helper**: use `_run(...)` (`tests/test_e2e.py:39-51`) for all commands; it already
  sets `check=False, capture_output=True, text=True`.
- **Tool skip guard**: loop `shutil.which(tool)` → `pytest.skip(...)` (`tests/test_e2e.py:71-73`).
  Extend the tool list for this test to include `npm`.
- **`just init` env**: pass `os.environ | _GIT_IDENTITY_ENV` (`tests/test_e2e.py:162-166`).
- **Token-rename assertions**: scoped reads + `'modernpackage' not in ...`, like the backend test's
  per-source loop (`tests/test_e2e.py:172-174`).
- **Injection entry point**: prefer `main._inject_templates(destination, fullstack=True)` over
  separate `_add_backend`/`_add_frontend` calls — it is the production path (`main.py:979-989`) and
  already performs `_stage_injected_files` (`git add -A`), so a manual stage is unnecessary.

**Do NOT follow / avoid**:
- Do **not** add `frontend-*` to the generated `check` chain — that would break generated CI which
  has no Node (`main.py:590-594`). The new test invokes frontend recipes *directly*, not via `check`.
- Do **not** run `frontend-check`'s lint/format/typecheck as the success criterion — the task scopes
  success to the **test suites** (pytest + Vitest). Run `frontend-test` directly (after install).

## Design Decisions

1. **Use `_inject_templates(fullstack=True)`** instead of manual `_add_backend` + `_add_frontend` —
   it is the real production flow and already stages files via `_stage_injected_files`, removing the
   need for a manual `git add -A` (the backend test predates relying on this and stages manually).
2. **Add `npm` to the skip guard for this test only** — frontend tests need Node/npm. Keep the
   module-level `REQUIRED_TOOLS = ('git','just','uv')` unchanged; define a local extended tuple
   (e.g. `('git','just','uv','npm')`) so other tests are unaffected. This makes CI skip rather than
   fail, matching the documented Node-absence precedent.
3. **Run `just frontend-install` then `just frontend-test`** (not `frontend-check`) — `frontend-test`
   (`vitest run`) does not depend on `frontend-install`, so install must run first; scoping to
   install+test keeps the assertion aligned with the task ("frontend test suite (Vitest) executed and
   passes") and avoids flakiness from lint/format/typecheck.
4. **`just check` covers the backend suite** — backend template tests run inside the generated
   `check` chain via `test` (`Justfile:53`); no separate backend invocation is needed.
5. **Assert token rename in `frontend/`** — read `frontend/package.json` and
   `frontend/src/App.test.tsx` and assert `'modernpackage'` is absent, confirming `just init`'s
   `git grep | sed` rename reached the staged frontend files (`Justfile:62-67`).
6. **Network/time caveat inherited** — like sibling tests, the inner `just check` runs `uv sync` +
   networked `pip-audit` and `npm ci` hits the network; document in the test docstring/comments. No
   new mitigation; offline runners already fail/skip the e2e layer.
7. **No new Justfile recipe or production-code change** — all injection machinery already exists;
   this task adds test coverage only.

## What We're NOT Doing

- Not adding `frontend-*` recipes (or Vitest) to any `check` chain (root or generated).
- Not adding Node/npm to CI (`.gitlab-ci.yml`, GitHub workflow) — the e2e test stays a deliberate,
  locally-run gate.
- Not changing `main.py` injection logic, `_FRONTEND_RECIPES`, or the frontend template.
- Not running a real database or `migrate` recipes (backend tests fake the DB).
- Not running frontend lint/format/typecheck/build as success criteria.
- Not refactoring the existing three e2e tests.

## Open Risks

- **Node/npm availability & version**: developers/CI running `just test-e2e` must have a compatible
  Node. The skip guard prevents hard failures, but a too-old Node could fail `npm ci`/Vitest. Mention
  the Node requirement near the test.
- **Runtime cost**: this test adds `npm ci` + Vitest on top of the already-minutes-long `just check`
  (`uv sync` + `pip-audit`). Acceptable for an opt-in e2e test, but it lengthens `just test-e2e`.
- **Token-rename completeness in frontend**: if any frontend file holding the `modernpackage` token
  is untracked at rename time, `sed` would miss it — `_stage_injected_files` should prevent this, but
  the assertions in decision 5 guard against regressions.
- **`frontend-test` recipe contract**: design assumes `frontend-test` does not depend on
  `frontend-install`. If that changes, the explicit install step becomes redundant (harmless) — but
  verify the recipe shape during structure/implementation.
