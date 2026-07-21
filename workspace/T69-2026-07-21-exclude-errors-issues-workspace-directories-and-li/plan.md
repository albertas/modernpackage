# Plan

## Phase 1: Strip errors/issues/workspace dirs and lifecycle_state.yml/metrics.yml during instantiation

### Context

Scaffolding strips the scaffolder's own files from a cloned template in one
place: the `_SCAFFOLDING_PATHS_TO_DELETE` tuple (`modernpackage/main.py`),
consumed by `_strip_scaffolding()` (same file, ~line 626), which is called from
the main scaffold flow (~line 959). `_strip_scaffolding` already handles both
directories (`shutil.rmtree(..., ignore_errors=True)`) and files
(`Path.unlink(missing_ok=True)`), and tolerates absent paths — so no logic
changes are needed, only new entries. Tests live in `tests/test_main.py` under
the "Phase 1: _strip_scaffolding" section, seeded by the `_seed_clone` helper
(~line 1096).

### Implementation

1. In `modernpackage/main.py`, extend `_SCAFFOLDING_PATHS_TO_DELETE` with the
   five new clone-relative paths:
   - `'errors'`
   - `'issues'`
   - `'workspace'`
   - `'lifecycle_state.yml'`
   - `'metrics.yml'`

   Place them alongside the existing entries. Update the tuple's explanatory
   comment (currently focused on `backend_template`/`frontend_template`) so it
   notes these are scaffolder operational/process artifacts removed from every
   generated package.
   → verify: the three directory names and two `.yml` filenames appear in the
   tuple.

2. In `tests/test_main.py`, extend the `_seed_clone` helper to create the new
   artifacts in the fake clone tree:
   - `errors/`, `issues/`, `workspace/` directories (each with a placeholder
     file so the dir materializes)
   - `lifecycle_state.yml` and `metrics.yml` files with placeholder content
   → verify: `_seed_clone` produces these paths.

3. In `tests/test_main.py`, add a test (mirroring
   `test_strip_scaffolding_removes_cli_tests_docs`) asserting that after
   `_strip_scaffolding(_seed_clone(tmp_path))` the five new paths no longer
   exist:
   - `not (tmp_path / 'errors').exists()`
   - `not (tmp_path / 'issues').exists()`
   - `not (tmp_path / 'workspace').exists()`
   - `not (tmp_path / 'lifecycle_state.yml').exists()`
   - `not (tmp_path / 'metrics.yml').exists()`
   → verify: new test passes.

### Verification

- `just test` (or `just check`) passes, including the existing
  `_strip_scaffolding` tests and the newly added one.
- The existing `test_strip_scaffolding_tolerates_absent_paths` still passes,
  confirming the new entries degrade gracefully when absent.
