# Design Discussion

## Current State

The optional, opt-in scaffolding capability described by this task **already
exists** in the codebase. It was delivered incrementally across the immediately
preceding tasks (T53 `--fastapi`, T54 frontend docs, T55 `--fullstack`/`--reactjs`,
T56 clean default output, T57 fullstack test execution — see `git log`). The CLI
is a single module, `modernpackage/main.py` (1135 lines).

What is present today:

- **Flags & aliases**: `--backend`/`--fastapi` and `--fullstack`/`--reactjs`,
  both `store_true`, parsed in `parse_args()` (`main.py:363-376`) and threaded as
  keyword args into `init_new_package(..., backend=..., fullstack=...)`
  (`main.py:1120-1130`). `--fullstack` is a strict superset of `--backend`
  (`if backend or fullstack`, `main.py:1065`).
- **Injection flow**: clone → metadata → `_strip_scaffolding` →
  `_inject_templates` → `git add -A` → `just init` → `just check`
  (`main.py:1007-1108`, `_inject_templates` at `main.py:979-989`).
- **Frontend template**: `frontend_template/` is a complete Vite 8 / React 19 /
  Vitest 4.1 project — `package.json` scripts (`package.json:6-17`),
  `vite.config.ts` with `/api` proxy + Vitest config (`vite.config.ts:1-16`),
  three-tsconfig split, ESLint flat config, committed `openapi.json` snapshot, and
  a **placeholder** `src/client/index.ts` (`frontend_template/src/client/index.ts:1-4`).
- **Frontend wiring**: `_add_frontend` copies the tree into an isolated
  `frontend/` subdir and appends six `cd frontend &&` recipes; it adds **zero**
  Python deps and spawns **no** subprocess (`main.py:962-976`,
  `_append_frontend_recipes` at `main.py:946-959`).
- **Clean default**: both template trees are in `_SCAFFOLDING_PATHS_TO_DELETE`
  and are always stripped, then conditionally re-injected — guaranteeing no-flag
  output is byte-identical to the pre-flag scaffold (`main.py:519-526`, Q3).
- **Tests**: `tests/test_main.py` (148 unit tests, frontend injection at
  `test_main.py:1753,1769,1791,1826`) and `tests/test_e2e.py` (4 e2e tests
  including the fullstack case at `test_e2e.py:272` which runs `just frontend-install`
  + `just frontend-test`).

## Desired End State

A user running `modernpackage myapp --fullstack` (or `--reactjs`) gets a project
with a working FastAPI backend **and** a `frontend/` React app, each coherent and
passing its own checks; a user running `modernpackage myapp` with no flags gets a
backend-free, frontend-free base package. **This end state is already met.** This
task is therefore a **verification and consolidation** pass, not new feature work.

Verify correctness by:
1. `just test` — full unit suite passes (frontend injection tests included).
2. `just test-e2e` (with `npm` available) — the fullstack e2e case scaffolds,
   renames the `modernpackage` token, runs `just frontend-install` +
   `just frontend-test`, and asserts Vitest output (`test_e2e.py:272`).
3. The negative e2e case confirms no backend/frontend artifacts leak into the
   default scaffold (`test_e2e.py:196`).
4. `just check` on the source repo stays green.

## Patterns to Follow

- **Isolation of the Node project** in `frontend/` to keep Python tooling from
  discovering it (`_add_frontend`, `main.py:962-976`; rationale
  `architecture.md:1122-1123`). Mirror this for any new frontend files.
- **Literal `modernpackage` rename pivot**: every injected file keeps the literal
  token so `just init`'s `git grep | sed` rewrites it; injected files must be
  `git add -A`-staged first (`_stage_injected_files`, `main.py:925-944`;
  `Justfile:62-67`).
- **No Node tooling at scaffold time**: `_add_frontend` adds no Python deps and
  spawns no child process — Node steps are deferred to the user via recipes
  (`main.py:967-968`). Preserve this.
- **Graceful boundary degradation**: writers that touch generated files print a
  `[notice]` and return on a missing file rather than raising
  (`_append_frontend_recipes`, `main.py:951-958`); reserve `RuntimeError` for
  invariant violations and subprocess failures (`main.py:940-943`).
- **Frontend recipes excluded from the root `check` chain** (need Node) — by
  design, documented at `main.py:590-594` and `invocation.md:229`.
- **Patterns NOT to follow / known intentional gaps**:
  - `src/client/index.ts` ships as a placeholder, not a real generated client
    (`frontend_template/src/client/index.ts:1-4`). This is **intentional** — the
    real client is produced by `just generate-client` against a running backend.
    Do not attempt to commit a "real" generated client.
  - There is no source-repo recipe that runs the frontend template's own Vitest
    suite outside e2e; `check-backend-template` is lint-only (`Justfile:76-77`).
    This matches the backend template's treatment — do not add Node to the source
    repo's `check`.

## Design Decisions

These are judgment calls made in lieu of asking the user (per process rules).

1. **Treat T58 as verification/consolidation, not re-implementation** — The frontend
   scaffolding the task asks for already exists and is tested. Re-building it would
   violate "Surgical Changes" and "Simplicity First". The implementation phase
   should confirm the existing capability via the existing test suites and only
   touch code to close concrete gaps, if any are found.
2. **Keep `src/client/index.ts` a placeholder** — Generating a real client requires
   a live backend at scaffold time, which contradicts the "no subprocess / no Node
   at scaffold time" pattern. The committed `openapi.json` snapshot + `generate-client`
   recipe is the correct sync mechanism (`reactjs_frontend.md:124-169`).
3. **Do not add frontend tests to the root `check` chain** — Consistent with the
   backend template (DB-dependent recipes also excluded). Frontend coverage lives in
   the e2e fullstack case, which already runs `just frontend-test`.
4. **`--fullstack` remains a strict superset of `--backend`** — Keep the single
   `if backend or fullstack` guard (`main.py:1065`); do not introduce a frontend-only
   mode (the React app's `/api` proxy and generated client assume a backend exists).
5. **No documentation rewrite** — `docs/reactjs_frontend.md` and `docs/invocation.md`
   already describe the behavior accurately; only update them if implementation
   changes observable behavior.

## What We're NOT Doing

- NOT adding new CLI flags, a frontend-only mode, or new aliases.
- NOT committing a real generated API client (placeholder stays).
- NOT adding Node/`npm` to the source repo's `just check` chain.
- NOT refactoring `main.py` into multiple modules as part of this task.
- NOT addressing the backend-only open items (e.g. missing non-root `USER` in
  `Containerfile`, `docs/containerization.md:193-197`) — out of scope for a
  frontend-focused task; flag them in the backlog instead.
- NOT changing the default (no-flag) scaffold output in any way.

## Open Risks

- **The task may be redundant.** If the implementation phase confirms the
  capability is complete and all tests pass, the correct outcome is a no-op change
  set plus a verification record — not invented work. Surface this to the user
  rather than manufacturing edits.
- **e2e requires `npm`.** The fullstack e2e case `pytest.skip`s when `npm` is
  absent (`test_e2e.py`), so a clean `just test-e2e` run on an environment without
  Node would silently skip the most important coverage. Verify `npm` is present
  when validating.
- **Dependency drift.** Pinned ranges in `frontend_template/package.json`
  (react@^19, vite@^8, vitest@^4.1) may resolve to newer minor versions over time;
  an e2e failure here would be an upstream-tooling issue, not a scaffolding defect.
- **Placeholder client divergence.** If the backend's health-endpoint schema
  changes, the committed `openapi.json` snapshot and placeholder types could drift
  from reality until a user regenerates — acceptable given Decision 2, but worth a
  note in generated-project docs.
