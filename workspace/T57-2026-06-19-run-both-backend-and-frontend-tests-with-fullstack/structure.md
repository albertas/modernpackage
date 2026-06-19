# Structure Outline

## Approach

Add one new e2e test, `test_scaffolded_fullstack_package_passes_check`, to
`tests/test_e2e.py`. It scaffolds a fullstack package from the local committed
checkout via the production injection path (`_inject_templates(fullstack=True)`),
runs the generated `just check` (backend pytest), then installs and runs the
frontend Vitest suite directly, and asserts structural/token-rename expectations.
No production code, `Justfile`, or template changes (design decision 7).

**Slicing note**: this is a test-only task — there is no DB/service/API/UI stack
to cross. The "vertical slices" below are incremental layers of the *single* new
test function: each phase leaves the file importable and the test runnable (via
`just test-e2e`) with strictly more coverage than the previous phase. If a later
phase fails, earlier phases remain independently valuable and green.

---

## Phase 1: Backend-passing fullstack scaffold

Establishes the scaffold → inject → init → `just check` skeleton for a fullstack
package, proving the **backend pytest suite** passes inside the generated `check`
chain. Mirrors `test_scaffolded_backend_package_passes_check` but injects via the
production fullstack entry point (no manual `git add -A` — `_inject_templates`
already stages).

**Files**: `tests/test_e2e.py` (new function only)

**Key changes**:
- `test_scaffolded_fullstack_package_passes_check(tmp_path: Path) -> None` — new
  `@pytest.mark.e2e` test.
- Local guard tuple `required_tools = (*REQUIRED_TOOLS, 'npm')` then the existing
  `shutil.which(tool) → pytest.skip(...)` loop (module-level `REQUIRED_TOOLS`
  unchanged — design decision 2).
- Flow: `git clone REPO_ROOT → destination`; `main._write_package_metadata(...)`;
  `main._strip_scaffolding(destination)`; `main._inject_templates(destination,
  fullstack=True)` (production path, stages internally — design decision 1);
  `just init <module_name>` with `env=os.environ | _GIT_IDENTITY_ENV`; `just check`.
- Reuse existing `_run(...)` helper for every subprocess call.

**Verify**: `just test-e2e` runs the new test green (Node present locally) —
`just check` returns 0, proving backend tests pass. On a box without `npm`,
`just test-e2e -k fullstack` reports the test **skipped**, not failed. Concrete:
`just test-e2e -k fullstack` exits 0 and its output contains either `1 passed`
or `1 skipped`.

---

## Phase 2: Frontend Vitest suite executes

Adds the frontend half: install Node deps then run Vitest, asserting each returns
0. This is the slice that delivers the task's headline ("run both backend and
frontend tests with fullstack").

**Files**: `tests/test_e2e.py` (extend the Phase 1 function)

**Key changes** (appended after the `just check` assertion):
- `install = _run(['just', 'frontend-install'], cwd=destination)` →
  `assert install.returncode == 0, ...` (runs `npm ci`; must precede test —
  `frontend-test` does not depend on it, design decision 3).
- `frontend_test = _run(['just', 'frontend-test'], cwd=destination)` →
  `assert frontend_test.returncode == 0, ...` (runs `vitest run`). Run
  `frontend-test` directly, **not** `frontend-check` (no lint/format/typecheck —
  design "Do NOT follow").
- Comment noting `npm ci` hits the network and Node version requirement (open risks).

**Verify**: `just test-e2e -k fullstack` exits 0 with `1 passed` where Node is
available. To confirm Vitest actually ran (not silently skipped), assert in the
test that `frontend_test.stdout`/`stderr` contains a Vitest marker, e.g.
`'Test Files'` or `'vitest'`; the test failing if the suite did not execute.

---

## Phase 3: Structural & token-rename assertions

Locks in the scaffold's shape: `frontend/` exists, backend files present,
frontend recipes in the generated `Justfile`, and the `modernpackage` token was
renamed inside `frontend/` (proves `_stage_injected_files` + `just init` sed
reached staged frontend files — design decision 5).

**Files**: `tests/test_e2e.py` (extend the same function)

**Key changes** (assertions):
- `source_dir = destination / module_name`; `assert (source_dir / 'app.py').exists()`
  and `(source_dir / 'health.py').exists()` (backend present).
- `frontend_dir = destination / 'frontend'`; `assert frontend_dir.is_dir()`.
- Token rename: read `frontend/package.json` and `frontend/src/App.test.tsx`;
  `assert 'modernpackage' not in <text>` for each.
- Recipes: `generated_justfile = (destination / 'Justfile').read_text()`; assert
  `'frontend-install'`, `'frontend-test'`, `'frontend-check'` each `in`
  `generated_justfile`.
- Optional cross-check: `'frontend-' not in` the generated `check`-chain line
  (recipes present but excluded from `check` — design "What We're NOT Doing").

**Verify**: `just test-e2e -k fullstack` exits 0, `1 passed`. Manual scripted
check independent of pytest:
`grep -L modernpackage <dest>/frontend/package.json` is non-empty (token absent)
and `grep -c frontend-test <dest>/Justfile` ≥ 1.

---

## Phase 4: Quality gate

Confirms the addition meets repo conventions and does not regress siblings.

**Files**: none (verification only)

**Verify**: `just check` (root) passes — `ruff` format/lint/complexity, mypy,
and the **non-e2e** suite all green, proving the new test is well-formed and
imports cleanly without running the slow e2e path. Then `just test-e2e` runs all
four e2e tests green/skip locally. Concrete: `just check` exits 0; `just test-e2e`
output shows `4 passed` (or `4 skipped` on a no-Node box, `3 passed 1 skipped`
when only `npm` is missing).

---

## Testing Checkpoints

- **After Phase 1**: new e2e test exists and passes locally; backend suite runs
  inside generated `just check`; test skips cleanly when `npm` absent. Earlier
  three e2e tests untouched.
- **After Phase 2**: frontend Vitest suite installs and runs; both backend and
  frontend test suites assert `returncode == 0` — the core task is satisfied.
- **After Phase 3**: structural shape and frontend token rename are pinned;
  regressions in `frontend/` staging/rename or recipe injection now fail the test.
- **After Phase 4**: `just check` green (well-formed, conventions met), full
  `just test-e2e` green/skip. Done.
