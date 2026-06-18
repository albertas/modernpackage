# Structure Outline

## Approach

Add a single Python function, `_strip_scaffolding(package_path)`, to
`modernpackage/main.py`. It mutates the **clone** (deletes the self-replicating
CLI, its e2e test, docs, `BACKLOG.md`; replaces `tests/test_main.py` with a
one-test stub and `README.md` with a generic stub; drops `[project.scripts]`
from the cloned `pyproject.toml`). It runs in `init_new_package` **between**
`_write_package_metadata` and the `just init` Popen, so the rename `sed` and the
lone `git commit` capture an already-clean tree. The template repo's own files
are untouched, so it stays a working scaffolder and its `just check` stays green.

Stub files are written with the literal `modernpackage` token so the existing
`git grep -l 'modernpackage' | xargs sed` rename (`Justfile:61-66`) rewrites
their imports to `<module>`. Logic is factored into constant-driven helpers to
stay under mccabe `max-complexity = 8` (`pyproject.toml:78-79`).

---

## Phase 1: `_strip_scaffolding` core + unit tests

Implement the strip function and its helpers; cover behavior directly with
`tmp_path` tests that seed a fake clone tree. Delivers the full strip logic as a
standalone, independently testable unit (no clone/subprocess needed).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...]` — new constant; relative paths
  to remove (`'modernpackage/main.py'`, `'tests/test_e2e.py'`, `'docs'`,
  `'BACKLOG.md'`). Looped over, mirroring `_METADATA_FIELDS`.
- `_TEST_MAIN_STUB: str` — new constant; stub body importing the package and
  asserting `__version__ == '0.0.1'`, written with the `modernpackage` token.
- `_README_STUB: str` — new constant; minimal generic README (satisfies
  `pyproject.toml:7` `readme`).
- `_strip_scaffolding(package_path: Path) -> None` — new; orchestrates deletes +
  stub writes + `[project.scripts]` removal. Tolerates absent paths
  (`missing_ok` / `ignore_errors`).
- `_remove_project_scripts(pyproject_path: Path) -> None` — new helper; removes
  only the `[project.scripts]` table (header + its lines) from the cloned
  `pyproject.toml`, leaving `e2e` marker, `vupi` dep, `[tool.deadcode]` intact.

**Verify**: `just test` passes. New `tmp_path` tests assert, after
`_strip_scaffolding(tree)`: `tree/modernpackage/main.py`, `tree/tests/test_e2e.py`,
`tree/docs`, `tree/BACKLOG.md` are absent; `tree/tests/test_main.py` exists,
contains `modernpackage` and `0.0.1`; `tree/README.md` exists; cloned
`pyproject.toml` no longer contains `[project.scripts]` but still contains
`e2e`. Agent check: `python -m pytest tests/test_main.py -k strip_scaffolding -q`
exits 0.

---

## Phase 2: Wire into `init_new_package` + orchestration tests

Call `_strip_scaffolding` from `init_new_package` between the metadata write and
the `just init` Popen, and update the happy-path orchestration tests to patch the
new seam. Delivers a scaffolder that produces a stripped package.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `init_new_package(...)` — insert `_strip_scaffolding(new_package_path)` after
  `_write_package_metadata(...)` (`main.py:755-762`) and before the `just init`
  Popen (`main.py:764-766`). Signature unchanged.
- `tests/test_main.py` — existing `init_new_package` happy-path tests
  (`:288-373`) mock `Popen` with no real clone dir; patch `_strip_scaffolding` on
  `modernpackage.main` (e.g. `patch.object(main, '_strip_scaffolding')`) and
  assert it is called once with `new_package_path`, ordered after metadata write
  and before the `just init` Popen call.

**Verify**: `just check` passes on the template repo (ruff/mypy/complexity/cov ≥
95% / audit). Agent checks: `python -m pytest tests/test_main.py -k init_new_package -q`
exits 0; `rg -n '_strip_scaffolding\(new_package_path\)' modernpackage/main.py`
shows the call between `_write_package_metadata` and the `['just', 'init'`
Popen (confirm line ordering).

---

## Phase 3: Extend e2e test to assert a clean generated package

Extend the e2e flow to call `_strip_scaffolding` between metadata write and
`just init`, then add assertions that the generated package is scaffolding-free
and still passes `just check`. Delivers full end-to-end proof.

**Files**: `tests/test_e2e.py`

**Key changes**:
- `test_scaffolded_package_passes_check(tmp_path)` — after
  `main._write_package_metadata(destination, ...)` (`test_e2e.py:66-73`), add
  `main._strip_scaffolding(destination)`. Add assertions after the existing
  `just check` (`:92-93`):
  - `source_dir / 'main.py'` does not exist (CLI removed).
  - `destination / 'tests' / 'test_e2e.py'` does not exist.
  - `destination / 'docs'` does not exist; `destination / 'BACKLOG.md'` absent.
  - `'[project.scripts]' not in pyproject` (no dangling entry point).
  - `(source_dir / '__init__.py').read_text()` contains `'0.0.1'` (already
    asserted at `:88-90`; keep).
  - `just check` returncode 0 (existing `:92-93`).

**Verify**: `just test-e2e` exits 0 (runs `pytest -m e2e --no-cov`). Note: this
test clones, runs an inner `uv sync` + networked `pip-audit` and a full inner
`just check` — minutes-long and offline-failing (`test_e2e.py:7-15`). Agent
check in an online environment: `just test-e2e` returncode 0; the in-test
asserts above are the file-inspection checks.

---

## Testing Checkpoints

- **After Phase 1**: `_strip_scaffolding` exists and is correct in isolation.
  `python -m pytest tests/test_main.py -k strip_scaffolding -q` is green; a seeded
  `tmp_path` tree is stripped to the desired end state. `just check` stays green
  (function is ruff-clean, mypy-strict, mccabe ≤ 8, covered).
- **After Phase 2**: `init_new_package` invokes the strip at the correct point.
  `just check` green; `python -m pytest tests/test_main.py -q` green. The
  scaffolder still works (template files untouched; `[project.scripts]` removed
  only from the clone at runtime).
- **After Phase 3**: A really-scaffolded package contains no `main.py`, no
  `test_e2e.py`, no `docs/`, no `BACKLOG.md`, no `[project.scripts]`; `__init__.py`
  is `0.0.1`; inner `just check` returns 0. `just test-e2e` green (online).

## Notes / Deviations

- No static edit to the template's own `pyproject.toml`: `[project.scripts]` is
  removed from the **clone** at runtime by `_remove_project_scripts`, so the
  template keeps its working `modernpackage`/`mp` console scripts (design
  decisions 3 & 9). If a reviewer expects a static diff there, flag it.
- Per design "What We're NOT Doing": the generated `Justfile` retains inert
  scaffolding recipes (`init`, `test-e2e`, `vision`, `lifecycle`) — `just init`
  cannot cleanly delete itself mid-run. Out of scope; follow-up.
- Ordering risk (design "Open Risks"): deletions are deleted-but-tracked until
  `just init`'s `git add .` stages them; `git grep` skips them, and stub writes
  retaining the `modernpackage` token are renamed correctly. Phase 2 keeps the
  strip strictly before `just init`.
