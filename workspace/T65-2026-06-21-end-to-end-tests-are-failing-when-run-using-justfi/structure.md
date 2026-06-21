# Structure Outline

## Approach

Fix is isolated to `backend_template/Containerfile` builder **STEP 5**. The
`uv sync --locked --no-install-project --no-dev` layer bind-mounts only `uv.lock`
+ `pyproject.toml`, but hatchling's dynamic version source
(`modernpackage/__init__.py`, renamed by `just init`) and `readme` are not in the
build context at that layer, so editable-metadata generation fails (`assert 2 == 0`
at `podman compose up`). Add bind mounts for the version source file (and README)
to STEP 5 using the `modernpackage` token so `just init`'s sed rewrites them
automatically. No test/scaffold/Justfile changes.

> **Note — not vertically sliceable in the db/service/api/ui sense.** This is a
> single-file container-build fix; there are no layers to cross. Phases below are
> ordered by **root-cause-first, then widening verification surface**: each phase
> is independently valuable (Phase 1's edit stands alone; Phases 2–3 only add
> verification breadth). Each has an unattended verification command.

---

## Phase 1: Bind-mount the dynamic-version source into STEP 5

Add the hatchling version-source file as a STEP 5 bind mount so uv can build the
root project's editable metadata without the full source tree, preserving the
two-stage dependency cache. This is the root-cause fix.

**Files**: `backend_template/Containerfile`

**Key changes** (STEP 5 `RUN`, after the existing `pyproject.toml` mount):
- `--mount=type=bind,source=modernpackage/__init__.py,target=modernpackage/__init__.py` — new
  - `just init` rewrites `modernpackage` → `<module>` in this tracked file (`Justfile:55-72`); resolves relative to compose build context (package root, `compose.yml:5,16 build: .`).
- Do **not** touch STEP 6 `COPY . /app`, STEP 7 sync, runtime stage, or the uv `0.5` pin (Decisions 4, 5).

**Verify**: Run the cheapest runtime test unattended (no full 319 s suite):
`uv run pytest tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end -m e2e --no-cov -q`
→ assert it no longer fails at the `compose up` assertion (`:53`) with the
`OSError: Error getting the version from source 'regex': file does not exist:
<module>/__init__.py` / `Failed to generate package metadata` build error. Either
the test passes, or it advances past STEP 5 to a *different* error (e.g. README —
see Phase 2). Capture build output and grep for `STEP 5` success / absence of the
version-source `OSError`.

---

## Phase 2: Bind-mount README for the long-description metadata field

`pyproject.toml:7 readme = "README.md"`; hatchling reads it during
`prepare_metadata_for_build_editable`. The `_README_STUB` is written during strip
so the file exists. Mount it up front to avoid a second debug round-trip
(Decision 3). **Drop this phase's mount if Phase 1 verification already shows a
green build** (Decision 3 assumption: stay minimal).

**Files**: `backend_template/Containerfile`

**Key changes** (STEP 5 `RUN`):
- `--mount=type=bind,source=README.md,target=README.md` — new (token-free path; no rename needed)

**Verify**: Re-run
`uv run pytest tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end -m e2e --no-cov -q`
→ test PASSES; captured build output shows `uv sync --locked --no-install-project
--no-dev` completing (no `prepare_metadata_for_build_editable` error referencing
`README.md`), and the test's own `compose up` assertion (`assert returncode == 0`)
holds. If any further metadata file is demanded (Open Risk), read the build error
and add that mount the same way, then re-run.

---

## Phase 3: Full suite green + no regression

Confirm the complete e2e suite passes via the real Justfile path and that the 4
previously-passing scaffolding/`just check` tests did not regress.

**Files**: none (verification only)

**Key changes**: none

**Verify**:
- `just e` exits 0 and final pytest line reads `7 passed` (0 failed, 0 skipped;
  146 deselected). Run unattended; allow ~300–350 s.
- Regression guard for the 4 build-independent tests:
  `uv run pytest "tests/test_e2e.py::test_scaffolded_package_passes_check" "tests/test_e2e.py::test_scaffolded_backend_package_passes_check" "tests/test_e2e.py::test_scaffolded_package_has_no_backend_or_frontend" "tests/test_e2e.py::test_scaffolded_fullstack_package_passes_check" -m e2e --no-cov -q`
  → `4 passed`.
- Spot-check captured output: each of the 3 runtime tests logs `compose up`
  returning 0 (Desired End State item 1). Distinguish a build fix from runtime
  flake (Open Risk): if a runtime test fails *after* a clean build (e.g. `/readyz`
  poll timeout, Playwright), that is a flake, not a regression of this fix —
  re-run the single test before concluding.

---

## Testing Checkpoints

- **After Phase 1**: `test_backend_package_runs_end_to_end` no longer dies on the
  hatchling version-source `OSError` at STEP 5; build advances (passes, or fails
  only on README/later metadata).
- **After Phase 2**: STEP 5 completes editable-metadata generation; the backend
  runtime test passes end-to-end (`compose up` returns 0). README mount kept only
  if actually required.
- **After Phase 3**: `just e` → `7 passed`; the 4 scaffolding/`just check` tests
  remain green; all 3 runtime tests show `compose up` exit 0. Done = green suite
  with no edits outside `backend_template/Containerfile`.
