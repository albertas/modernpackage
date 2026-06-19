# Structure Outline

## Approach

The no-flag strip already guarantees zero backend/frontend leakage (`_strip_scaffolding`
unconditionally deletes the template trees; source `pyproject.toml`/`Justfile` carry no
backend/frontend deps or recipes). The work is **verification only**: add a fast mocked
unit guard plus a comprehensive e2e absence test, both deriving forbidden markers from the
existing `main.py` injection constants. No behavior change unless a test surfaces a real
bug — fix minimally if so. Each phase is an independent test slice that passes on its own.

---

## Phase 1: Mocked no-flag injector guard (fast, no clone)

Pin the gate at `main.py:1065-1066` with a cheap unit test: a no-flag
`init_new_package` must invoke neither `_add_backend` nor `_add_frontend`. Complements the
existing positive guards (`test_main.py:1592-1603`, `1808-1820`). Fast regression signal
that runs under default `pytest` (no `e2e` marker).

**Files**: `tests/test_main.py`

**Key changes**:
- `def test_init_new_package_no_flags_injects_nothing() -> None` — new test.
  Patches `Popen` (per `test_main.py:296-307` style) plus
  `patch.object(main, "_add_backend")` and `patch.object(main, "_add_frontend")`;
  calls `main.init_new_package("mypackage")` with `backend=False, fullstack=False`
  (match the real signature at `main.py:1007`); asserts
  `_add_backend.assert_not_called()` and `_add_frontend.assert_not_called()`, and the
  exact 3 `Popen` calls (clone, `just init`, `just check`).

**Verify**: `just test` passes (the new test is collected — no `e2e` marker, so it runs
under the default `-m 'not e2e'` selection). Spot-check it actually exercises the guard:
`just test -- -k test_init_new_package_no_flags_injects_nothing` exits 0 and reports
1 passed.

---

## Phase 2: E2E no-flag absence test (full scaffold pipeline)

Add the primary deliverable: scaffold a no-flag package through the real strip + `just init`
flow and assert the **absence** of every backend/frontend marker — directories, files,
dependency strings, recipe names, and import/source tokens. Mirrors
`test_scaffolded_package_passes_check` (`test_e2e.py:53-117`); leaves that test unchanged.

**Files**: `tests/test_e2e.py`

**Key changes**:
- `@pytest.mark.e2e` `def test_scaffolded_package_has_no_backend_or_frontend(tmp_path) -> None`
  — new test. Reuses the existing no-flag setup: clone local repo →
  `_write_package_metadata` → `_strip_scaffolding` → `just init`. Resolves the renamed
  module dir from the destination (per `test_e2e.py:97-117`), NOT a hardcoded
  `modernpackage/` path.
- Forbidden-marker sets derived from constants where practical:
  - `dependency_tokens` from `main._BACKEND_DEPENDENCIES` + `main._BACKEND_DEV_DEPENDENCIES`
    (`main.py:565-574`).
  - `recipe_tokens` from `main._BACKEND_RECIPES` + `main._FRONTEND_RECIPES`
    (`main.py:579-614`) — assert recipe names (`migrate`, `makemigration`,
    `migration-check`, `frontend-*`, `generate-client`) absent from `Justfile`.
  - `import_tokens` — small explicit list (`import fastapi`, `sqlalchemy`, `asyncpg`,
    React/Vite markers) scanned only within the renamed package source dir.

**Assertions** (per design §2):
- Dirs absent: `backend_template`, `frontend_template`, `frontend`, `migrations`.
- Files absent: `alembic.ini`, `compose.yml`, `Containerfile`, `.dockerignore`.
- `pyproject.toml` still contains `dependencies = []` and none of the `dependency_tokens`.
- `Justfile` contains none of the `recipe_tokens`.
- Package source dir contains none of the `import_tokens` (scoped scan, avoids
  false-positives per design "Open Risks").

**Verify**: `just test-e2e` passes (new test carries the `e2e` marker, so default `just check`
is unchanged). Confirm the test runs and is not silently skipped:
`just test-e2e -- -k test_scaffolded_package_has_no_backend_or_frontend` exits 0 and reports
1 passed (not 0 selected / skipped).

---

## Phase 3: Full-suite + coverage gate confirmation

No new code — a verification checkpoint that the additions keep all gates green and don't
regress coverage below `--cov-fail-under=95.0` (`pyproject.toml:40`).

**Files**: none.

**Verify**: `just check` exits 0 (lint, format, typecheck, default test selection with
coverage gate). `just test-e2e` exits 0. If coverage dropped below 95.0, the negative tests
executed too little real code — confirm via the `just check` coverage report and, only if
needed, adjust the test to exercise the strip path rather than lowering the gate.

---

## Testing Checkpoints

- **After Phase 1**: `just test` green; a no-flag `init_new_package` provably calls neither
  injector and makes exactly 3 subprocess calls. Fast guard in place.
- **After Phase 2**: `just test-e2e` green; a real no-flag scaffold provably has zero
  backend/frontend dirs, files, deps, recipes, and import tokens. Primary guarantee locked.
- **After Phase 3**: `just check` and `just test-e2e` both green; coverage ≥ 95.0. Safe to
  hand off — a future change reintroducing leakage now fails CI.

**Note**: every phase is a self-contained test slice. If Phase 2 or 3 fails, Phase 1 remains
independently valuable (cheap regression guard). No phase depends on another's code, only on
the shared, unchanged scaffolder.
