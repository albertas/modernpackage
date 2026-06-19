# Structure Outline

## Approach

Mirror the existing `--backend`/`--fastapi` injection feature to add a
`--fullstack`/`--reactjs` flag that injects the backend **and** a new
`frontend_template/` (Vite + React + TS, Vitest, `@hey-api/openapi-ts` client).
`--fullstack` is a superset: the backend block runs on `backend or fullstack`,
the frontend block only on `fullstack`. Slices go: (1) wire the flag end-to-end
with backend-only behavior + dry-run, (2) ship and package the template tree,
(3) inject the template into generated packages, (4) lock behavior with the
test suite. Each slice is independently testable; if (3) fails, (1)–(2) still
deliver a working `--fullstack`-implies-backend flag and a packaged template.

---

## Phase 1: Flag, threading, dry-run, fullstack⇒backend

Add the `--fullstack`/`--reactjs` flag, thread `fullstack` through `main()` and
`init_new_package`, make the backend injection run on `backend or fullstack`,
collapse to a single staging call, and add the frontend dry-run plan line. No
template injection yet — `--fullstack` produces a backend-only scaffold.

**Files**: `modernpackage/main.py`

**Key changes**:
- `parser.add_argument('--fullstack', '--reactjs', action='store_true', default=False)` — new (`dest=fullstack`), modeled on `main.py:363-369`.
- `init_new_package(..., backend: bool = False, fullstack: bool = False) -> int` — new kwarg (`main.py:913-923`).
- `main()` reads `parsed_args.fullstack`, passes `fullstack=...` into both `init_new_package` and `_print_dry_run_plan` (`main.py:1033`).
- `_format_dry_run_plan(..., fullstack: bool = False)` — appends `'  add React frontend (Vite, Vitest, generated API client, recipes)'` guarded `if fullstack:` (`main.py:681-683`).
- Injection block restructured (`main.py:969-971`):
  ```python
  if backend or fullstack:
      _add_backend(new_package_path)
  # _add_frontend call added in Phase 3
  if backend or fullstack:
      _stage_injected_files(new_package_path)
  ```

**Verify**: `just check` passes.
`uv run pytest tests/test_main.py -k "fullstack or reactjs"` — add quick assertions that `parse_args(['--fullstack','x']).fullstack is True`, same for `--reactjs`, and `--backend` leaves `fullstack False`.
`uv run python -c "from modernpackage.main import _format_dry_run_plan as f; assert 'React frontend' in f('x', __import__('pathlib').Path('x'), fullstack=True); assert 'React frontend' not in f('x', __import__('pathlib').Path('x'))"` exits 0.

---

## Phase 2: Ship + package `frontend_template/`

Create the `frontend_template/` tree at repo root, ship it in wheels/sdists, add
the `_FRONTEND_TEMPLATE_DIR` constant, strip it from the default clone, and
exclude it from the scaffolder's own ruff/pytest gates. Independently valuable:
the template exists and is packaged even before injection wiring lands.

**Files**: `frontend_template/**` (new), `modernpackage/main.py`, `pyproject.toml`

**Key changes**:
- New tree: `frontend_template/package.json` (`"name": "modernpackage"`), `vite.config.ts`, `tsconfig.json` + `tsconfig.app.json` + `tsconfig.node.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/App.test.tsx` (Vitest + RTL), `src/setupTests.ts`, `src/client/**` (pre-generated `@hey-api/openapi-ts` output), `openapi.json` snapshot. Pin Vite 8 / React 19 / `@vitejs/plugin-react` v6 / Vitest 4.1 / RTL 16.3 per `reactjs_frontend.md`.
- `_FRONTEND_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / 'frontend_template'` — new (`main.py:544-546`).
- `_SCAFFOLDING_PATHS_TO_DELETE += ('frontend_template',)` with the same comment style (`main.py:512-518`).
- `pyproject.toml`: `[tool.hatch.build] include` gains `"frontend_template/**"` excluding `node_modules`/`dist` (`pyproject.toml:50-51`); `[tool.pytest.ini_options] norecursedirs` and ruff/per-file ignores gain `frontend_template` (`pyproject.toml:41`).

**Verify**: `just check` passes (scaffolder gate ignores the Node files).
`test -f frontend_template/package.json && test -f frontend_template/vite.config.ts && test -f frontend_template/src/App.test.tsx && test -d frontend_template/src/client` exits 0.
`uv build --sdist && tar tzf dist/*.tar.gz | grep -q frontend_template/package.json && ! tar tzf dist/*.tar.gz | grep -q node_modules` exits 0.
`uv run python -c "from modernpackage.main import _SCAFFOLDING_PATHS_TO_DELETE as d; assert 'frontend_template' in d"` exits 0.

---

## Phase 3: `_add_frontend` injection + recipes + wiring

Add the injection helper that copies the template into `package_path/frontend`
and appends the frontend recipes, plus the `if fullstack:` call. After this,
`--fullstack` produces a real `frontend/` directory in the generated package.

**Files**: `modernpackage/main.py`

**Key changes**:
- `_FRONTEND_RECIPES: str` — multi-line Justfile block: `frontend-install`, `frontend-build`, `frontend-test`, `frontend-lint`, `generate-client`, and a `frontend-check` aggregate. Carries the "NOT in the `check` chain (needs Node)" comment (`main.py:561-563`).
- `_append_frontend_recipes(justfile_path: Path) -> None` — reads + appends `_FRONTEND_RECIPES`; `FileNotFoundError` → stderr notice, no raise (`main.py:861-874`).
- `_add_frontend(package_path: Path) -> None` — `shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True)` then `_append_frontend_recipes(package_path / 'Justfile')`. Adds **no** subprocess call and **no** Python deps (`main.py:898-911`).
- `init_new_package`: insert `if fullstack: _add_frontend(new_package_path)` between the backend block and the single `_stage_injected_files` call (Phase 1 scaffold).

**Verify**: `just check` passes.
`uv run pytest tests/test_main.py -k "add_frontend"` — using `_seed_clone(tmp_path)`, assert `_add_frontend` creates `frontend/package.json` + `frontend/src/client`, that the Justfile gains `generate-client`/`frontend-check` (substring), and that the seeded `pyproject.toml` is byte-identical (no Python deps added).
`uv run python -c "import inspect,modernpackage.main as m; assert 'npm' not in inspect.getsource(m._add_frontend) and 'Popen' not in inspect.getsource(m._add_frontend)"` exits 0 (no scaffold-time Node/subprocess).

---

## Phase 4: Test suite + integration lock

Mirror the backend test patterns and add the cross-cutting invariants from the
design's verify list (byte-identical no-flag scaffold, 4-Popen ordering,
token-rename safety).

**Files**: `tests/test_main.py`

**Key changes**:
- Flag-parsing tests (`--fullstack`/`--reactjs` → `fullstack True`) mirroring `test_main.py:1542-1557`.
- `_add_frontend` injection test vs `_seed_clone` mirroring `test_main.py:1606-1635`; token-rename invariant (replace `modernpackage`→`newpkg`, assert no leftover token in `frontend/`, and that `src/client` TS contains no token).
- Dry-run substring test mirroring `test_main.py:1560-1584`.
- Subprocess call-count/order test: `--fullstack` run yields exactly 4 Popen calls (clone, `git add -A`, just init, just check), 2nd is `['git','add','-A']` — mirroring `test_main.py:1646-1671`; confirms `_add_frontend` adds no Popen call.
- Orchestration test: `if backend or fullstack`/`if fullstack` sequencing via patched `_add_backend`/`_add_frontend`/`_strip_scaffolding` (mirroring `test_main.py:342-365,1587-1598`).

**Verify**: `just check` passes (includes the new tests + 95% coverage gate).
`uv run pytest tests/test_main.py -k "fullstack or reactjs or frontend"` all pass.
Node-present gate (optional, agent-runs only if Node available): `command -v npm && (cd frontend_template && npm ci && npm run generate-client && git diff --exit-code src/client)` — verifies the committed client is not stale; skipped cleanly when Node is absent.

---

## Testing Checkpoints

After each phase the following should hold (useful for resuming after a context reset):

- **After P1**: `parse_args` accepts `--fullstack`/`--reactjs`; `--fullstack` scaffolds a backend-only package; dry-run prints both backend and frontend plan lines; `just check` green.
- **After P2**: `frontend_template/` exists with `package.json`/`vite.config.ts`/Vitest test/`src/client`; it is in the sdist (no `node_modules`/`dist`); it is stripped from the default clone and excluded from the scaffolder's gate; a no-flag scaffold is byte-for-byte unchanged.
- **After P3**: `--fullstack` produces `frontend/` with injected files and frontend Justfile recipes; Python `pyproject.toml` gains zero deps; no scaffold-time Node/subprocess; generated `just check` still passes (no Node invoked).
- **After P4**: full design verify-list (items 1–7) is covered by automated tests under `just check`; 4-Popen ordering and token-rename invariants asserted.

**Note**: Verify-list item 5 (`generate-client`/`frontend-check` actually run Node gates) cannot be exercised inside the scaffolder's Node-free CI by design; P4 verifies the recipes exist and ship correct content, and gates live Node execution behind a `command -v npm` guard.
