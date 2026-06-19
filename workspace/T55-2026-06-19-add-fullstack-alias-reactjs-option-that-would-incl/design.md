# Design Discussion

## Current State

The scaffolder has exactly one optional-injection feature today: `--backend`
(alias `--fastapi`). Its full shape, which this task mirrors:

- **Flag**: a single `store_true` argument with two option strings →
  `dest=backend`, `default=False` (`main.py:363-369`).
- **Threading**: `main()` reads `parsed_args.backend` and passes
  `backend=...` into `init_new_package` (`main.py:1033`); signature declares
  `backend: bool = False` (`main.py:922`).
- **Template tree**: `backend_template/` at repo root, resolved as
  `_BACKEND_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'backend_template'`
  (`main.py:544-546`), shipped via `[tool.hatch.build] include = ["backend_template/**"]`
  (`pyproject.toml:50-51`).
- **Strip-then-reinject**: the clone always carries `backend_template/`, so
  `_strip_scaffolding` unconditionally deletes it via
  `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:512-518`); `_add_backend` re-injects
  only `if backend:` (`main.py:969-971`), placed after strip and before
  `just init`.
- **Injection** (`_add_backend`, `main.py:898-911`): `shutil.copytree(..., dirs_exist_ok=True)`,
  then targeted `str.replace` edits to `pyproject.toml` (deps from
  `_BACKEND_DEPENDENCIES`/`_BACKEND_DEV_DEPENDENCIES`, `main.py:550-559`) and an
  append of `_BACKEND_RECIPES` to the `Justfile` (`main.py:564-573`).
- **Staging**: `_stage_injected_files` runs `git add -A` so `just init`'s
  `git grep -l 'modernpackage' | xargs sed` rename reaches the new files
  (`main.py:877-895`, `Justfile:62-67`). Injected files keep the literal
  `modernpackage` token so imports get rewritten.
- **Dry-run**: one guarded plan line in `_format_dry_run_plan` (`main.py:681-682`).
- **Backend recipes are deliberately NOT chained into `check`** — they need a
  live database (`main.py:561-563`).

There is **no** frontend template, **no** Node tooling, and **no**
`--frontend`/`--reactjs`/`--fullstack` flag anywhere in the repo.
`docs/reactjs_frontend.md` is reference-only: it recommends Vite 8 + React 19,
Vitest 4 testing, and `@hey-api/openapi-ts` generating `src/client` from
`http://localhost:8000/openapi.json` with a `git diff --exit-code` drift gate
(`reactjs_frontend.md:133-169`). Its `just check` mapping (`:404-417`) is
documentation, not implemented wiring.

## Desired End State

A `--fullstack` flag (alias `--reactjs`) that scaffolds **both** the existing
FastAPI backend **and** a new `frontend_template/` (Vite + React + TS, Vitest
unit tests, `@hey-api/openapi-ts` client synced to the backend OpenAPI schema).

Verify correct when:
1. `parse_args` accepts `--fullstack` and `--reactjs`, both setting one dest True.
2. A no-flag scaffold is byte-for-byte unchanged (no `frontend/`, no Node refs).
3. A `--fullstack` scaffold contains the injected backend AND a `frontend/`
   directory with `package.json`, `vite.config.ts`, a Vitest test, and a
   committed `src/client`.
4. The generated package's `just check` still passes (it must not invoke Node).
5. `just generate-client` regenerates `src/client` and `just frontend-check`
   runs the Node gates when Node is present.
6. Dry-run prints both the backend and frontend plan lines.
7. New CLI tests mirror the backend test suite and pass under `just check`.

## Patterns to Follow

- **Flag definition**: copy the `--backend`/`--fastapi` `add_argument` shape
  (`main.py:363-369`) for `--fullstack`/`--reactjs`.
- **Threading**: forward through `main()` (`main.py:1033`) and the
  `init_new_package` signature (`main.py:922`) exactly as `backend` is.
- **Template constant**: add `_FRONTEND_TEMPLATE_DIR` alongside
  `_BACKEND_TEMPLATE_DIR` (`main.py:544-546`); add `"frontend_template/**"` to
  hatch `include` (`pyproject.toml:50-51`).
- **Strip list**: append `'frontend_template'` to `_SCAFFOLDING_PATHS_TO_DELETE`
  with the same comment style (`main.py:512-518`).
- **Injection helper**: model `_add_frontend` on `_add_backend`
  (`main.py:898-911`) — `copytree(dirs_exist_ok=True)` + Justfile append; degrade
  gracefully on `FileNotFoundError` (stderr notice, no raise, `main.py:843-850`).
- **Recipe append**: reuse `_append_backend_recipes` style for a
  `_FRONTEND_RECIPES` string (`main.py:861-874`); keep the "NOT in check chain"
  comment convention (`main.py:561-563`).
- **Staging**: reuse the existing `_stage_injected_files` call — no new staging
  code needed (`main.py:969-971`).
- **Dry-run**: add one guarded line in `_format_dry_run_plan` (`main.py:681-682`).
- **Tests**: mirror the backend test patterns — flag parsing assertions
  (`test_main.py:1542-1557`), `_add_frontend` injection against `_seed_clone`
  (`test_main.py:1606-1635`), dry-run substring (`test_main.py:1560-1584`),
  subprocess call-count ordering (`test_main.py:1646-1671`).

**Do NOT follow**: the `docs/reactjs_frontend.md` `just check` mapping
(`:404-417`) that chains npm gates into `check`. The generated package's
`just check` runs in CI without Node; chaining Node steps would break gate (4).

## Design Decisions

1. **`--fullstack` is a superset, not a third independent feature**: it injects
   backend **and** frontend. Internally, `init_new_package` treats
   `if backend or fullstack:` for the backend block and `if fullstack:` for the
   frontend block — the frontend's API client requires the backend's OpenAPI
   schema, so frontend-without-backend is disallowed. If both `--backend` and
   `--fullstack` are passed, fullstack wins (backend is a subset, no conflict).
2. **Separate dest `fullstack`**: keep `--backend` untouched; add a new
   `store_true` flag `--fullstack`/`--reactjs` (`dest=fullstack`). Cleaner than
   overloading `backend` and keeps the no-flag/backend-only paths byte-identical.
3. **Frontend lives in a `frontend/` subdirectory**: `_add_frontend` copies into
   `package_path / 'frontend'`, isolating the Node project from the Python
   package root (avoids polluting `pyproject.toml` discovery, ruff/mypy/pytest
   collection, and the coverage gate). The Python side gains **zero** new deps.
4. **Frontend gates are NOT in `just check`**: append `frontend-install`,
   `frontend-build`, `frontend-test`, `frontend-lint`, `generate-client`, and a
   `frontend-check` aggregate recipe, but leave the root `check` chain alone —
   consistent with the backend-recipes precedent (`main.py:561-563`). This keeps
   gate (4) green without Node installed.
5. **API client is committed + regenerable, not scaffold-time-generated**: the
   template ships a pre-generated `src/client` plus a captured `openapi.json`
   snapshot. `generate-client` (per `reactjs_frontend.md:151-156`) regenerates
   from the live dev server (`http://localhost:8000/openapi.json`); a drift gate
   recipe runs `generate-client` + `git diff --exit-code src/client`
   (`:162-169`). Running Node/backend at scaffold time is out of scope.
6. **Token-rename participation**: set the frontend `package.json` `name` and any
   doc strings to the literal `modernpackage` token so `just init`'s sed rename
   rewrites them; the generated TS `src/client` contains no token and is
   untouched. `_stage_injected_files` already covers staging.
7. **Scaffolder self-gate exclusions**: add `frontend_template` to the
   scaffolder's own ruff/pytest excludes (mirroring `norecursedirs`,
   `pyproject.toml:41`) so the repo's `just check` ignores Node files. A
   `check-frontend-template` repo recipe is out of scope (no Node in repo CI).
8. **Tooling versions**: pin to the doc's recommendations — Vite 8 / React 19 /
   `@vitejs/plugin-react` v6, Vitest 4.1, RTL 16.3, `@hey-api/openapi-ts`
   (`reactjs_frontend.md:15-17,197-241,133-158`).

## What We're NOT Doing

- Not running `npm install`, `vite build`, `vitest`, or `generate-client` during
  scaffolding, and not adding Node steps to `just check`.
- Not adding a standalone frontend-only flag (frontend always implies backend).
- Not shipping frontend container/compose/build assets (no equivalent to the
  backend `Containerfile`/`compose.yml`).
- Not adding frontend dependency entries to the Python `pyproject.toml`.
- Not enforcing the frontend coverage threshold inside the scaffolder's gate.

## Open Risks

- **Stale committed client**: the shipped `src/client` can drift from the backend
  schema until `generate-client` is run. Mitigated by the drift recipe; document
  it in the generated README.
- **Template size / wheel weight**: `frontend_template/` must exclude
  `node_modules/` and `dist/` from the hatch `include` glob so the wheel stays
  small and `copytree` is fast.
- **Token-rename over-reach**: `just init`'s global sed rewrites every
  `modernpackage` occurrence; verify it does not corrupt JSON/TS that
  legitimately needs the token elsewhere (seed-clone rename invariant test,
  `test_main.py:1623-1635`).
- **Subprocess call-count tests**: fullstack still produces 4 Popen calls (clone,
  `git add -A`, just init, just check) like backend — confirm `_add_frontend`
  adds no extra subprocess call (it must not run npm).
