# Implementation Plan

## Overview

`just e` currently reports `3 failed, 4 passed, 146 deselected`: every
compose-based e2e test dies at `podman compose up -d --build` (exit 2) because
`backend_template/Containerfile` STEP 5 bind-mounts only `uv.lock` +
`pyproject.toml`, so hatchling's dynamic-version source file (and `README.md`) are
absent when uv builds the root project's editable metadata. The fix adds the
missing bind mounts to STEP 5 so the metadata builds without the full source
tree, restoring a green `7 passed` suite. **No changes outside
`backend_template/Containerfile`.**

Reference context:
- `backend_template/Containerfile:11-14` — STEP 5 `RUN` with the two existing
  bind mounts (`uv.lock` line 12, `pyproject.toml` line 13) and the
  `uv sync --locked --no-install-project --no-dev` on line 14.
- `pyproject.toml:7` — `readme = "README.md"`.
- `pyproject.toml:54-55` — `[tool.hatch.version]` / `path = "modernpackage/__init__.py"`.
- `Justfile:61-72` — `just init` rewrites every `modernpackage` literal in
  **tracked** files via `git grep -l 'modernpackage' | xargs sed`, then
  `sed` version → `0.0.1` in `modernpackage/__init__.py`, then
  `mv modernpackage <name>`.
- `backend_template/.dockerignore` excludes `.venv/.git/__pycache__/*.pyc/.ruff_cache/.mypy_cache`
  only — it does **not** exclude `__init__.py` or `README.md`, so both are
  available to bind-mount from the build context.
- Build context is the package root (`compose.yml` `build: .`), so bind-mount
  `source=` paths resolve relative to the package root.

---

## Phase 1: Bind-mount the dynamic-version source into STEP 5

Root-cause fix. Add the hatchling version-source file (`modernpackage/__init__.py`,
rewritten to `<module>/__init__.py` by `just init`) as a STEP 5 bind mount so uv
can generate the root project's editable metadata without the full source tree,
preserving the two-stage dependency cache.

### Changes

#### 1. STEP 5 `RUN` bind mounts
**File**: `backend_template/Containerfile`
**Action**: modify

Add one new `--mount` line after the existing `pyproject.toml` mount (current
line 13), before the `uv sync` command (current line 14):

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=modernpackage/__init__.py,target=modernpackage/__init__.py \
    uv sync --locked --no-install-project --no-dev
```

Notes / assumptions:
- The literal `modernpackage` token is intentional: `just init` rewrites it to
  the real module name in this tracked file (`Justfile:64`). The `Containerfile`
  is copied into the package by `_add_backend` and staged via `git add -A` before
  init, so the rewrite reaches it.
- Do **not** touch STEP 6 `COPY . /app` (line 15), STEP 7 sync (lines 16-17),
  the runtime stage, the `CMD` line (line 26), or the `ghcr.io/astral-sh/uv:0.5`
  pin (line 6) — Design Decisions 1, 4, 5.

### Verification
#### Automated
- [x] `git diff --stat backend_template/Containerfile` shows exactly this file
      changed (1 file, +1 line).
- [x] `grep -c 'source=modernpackage/__init__.py,target=modernpackage/__init__.py' backend_template/Containerfile`
      → `1`.

#### Manual
- [x] Run the cheapest runtime test unattended (avoids the full ~319 s suite),
      capturing output:
      `uv run pytest tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end -m e2e --no-cov -q 2>&1 | tee /tmp/t65_phase1.log`
- [x] Confirm STEP 5 no longer fails on the version source:
      `! grep -q "Error getting the version from source" /tmp/t65_phase1.log`
      (the `OSError: ... file does not exist: <module>/__init__.py` is gone).
- [x] Confirm the build advanced past STEP 5: either the test passes, **or** it
      now fails on a *different* error (e.g. README metadata — see Phase 2).
      `grep -Ei "prepare_metadata_for_build_editable|README.md|passed|failed" /tmp/t65_phase1.log`
      — a `README.md` reference means proceed to Phase 2; a `1 passed` means
      Phase 2's mount may be unnecessary (see Phase 2 decision gate).
      Confirmed: build now fails on `OSError: Readme file does not exist: README.md`
      → proceed to Phase 2 (its mount is required).

---

## Phase 2: Bind-mount README for the long-description metadata field

`pyproject.toml:7` sets `readme = "README.md"`; hatchling reads it during
`prepare_metadata_for_build_editable` for the long-description field. The
`_README_STUB` is written during `_strip_scaffolding`, so the file exists at the
package root. Mount it up front to avoid a second debug round-trip (Design
Decision 3).

**Decision gate (Design Decision 3 / Open Risk):** If Phase 1's verification
already shows `1 passed` with no `README.md` error in the build output, **skip
this phase's mount** to stay minimal, and proceed directly to Phase 3. Only add
the mount if the Phase 1 build error references `README.md`.

### Changes

#### 1. STEP 5 `RUN` bind mounts (README)
**File**: `backend_template/Containerfile`
**Action**: modify

Add one more `--mount` line after the `modernpackage/__init__.py` mount from
Phase 1:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=modernpackage/__init__.py,target=modernpackage/__init__.py \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --locked --no-install-project --no-dev
```

Notes:
- `README.md` is a token-free path; `just init` does not rename it.
- If a *further* metadata file is demanded after this (Open Risk: hatchling
  needs more than version + readme), read the build error and add that mount the
  same way (`--mount=type=bind,source=<file>,target=<file>`), then re-run. The
  metadata build reads a small, fixed set, so this is bounded.

### Verification
#### Automated
- [x] `grep -c 'source=README.md,target=README.md' backend_template/Containerfile`
      → `1` (only if this phase's mount was added; otherwise `0` by design).

#### Manual
- [x] Re-run the backend runtime test, capturing output:
      `uv run pytest tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end -m e2e --no-cov -q 2>&1 | tee /tmp/t65_phase2.log`
- [ ] Test PASSES: `grep -q "1 passed" /tmp/t65_phase2.log`.
      NOT passing, but for an unrelated reason: STEP 5 now reads README.md +
      version source fine (README/version metadata errors gone), then fails at
      dependency *resolution* with `401 Unauthorized` querying the private
      GitLab index — `vupi>=0.0.10` unavailable (only `vupi==0.0.1` served).
      This is an environment/credentials issue, outside this phase's scope
      (which only touches `backend_template/Containerfile`).
- [x] No README metadata error remains:
      `! grep -qi "prepare_metadata_for_build_editable.*README\|file does not exist" /tmp/t65_phase2.log`.
      Confirmed: README "file does not exist" and version-source errors both gone.
- [ ] The test's own `compose up` assertion (`assert returncode == 0`,
      `tests_e2e/test_backend_e2e.py:53`) holds — the run reaching `1 passed`
      already implies this.
      Does not hold — blocked by the same `401 Unauthorized` private-index
      credentials failure above, not the metadata fix.

---

## Phase 3: Full suite green + no regression

Verification only — confirm the complete e2e suite passes via the real Justfile
path and that the 4 previously-passing scaffolding / `just check` tests did not
regress.

### Changes

**Files**: none. No code changes in this phase.

### Verification
#### Automated
- [x] `just check` passes on the outer repo (format/lint/complexity/typecheck/test/audit),
      confirming the `Containerfile` edit did not break host-side checks.
      Note: `test` here uses default `-m 'not e2e'`, so it does not run e2e —
      the e2e run below covers those.
      Confirmed: `just check` exits 0 — 146 unit tests pass (98.34% coverage),
      ruff format/lint/complexity clean, mypy clean, pip-audit clean, deadcode clean.

#### Manual
- [x] Full suite via the Justfile alias, unattended (~300–350 s):
      `just e 2>&1 | tee /tmp/t65_phase3.log`
      Executed: `3 failed, 4 passed, 146 deselected in 253.33s`.
- [ ] Final pytest summary reads `7 passed`:
      `grep -qE "7 passed" /tmp/t65_phase3.log` and
      `! grep -qE "[1-9][0-9]* failed" /tmp/t65_phase3.log`
      (0 failed; 146 deselected expected).
      NOT achieved (`3 failed, 4 passed`), but NOT due to this fix. The 3
      runtime tests now build *past* STEP 5 metadata generation (0 metadata
      errors in the log) and die at dependency *resolution* with `401
      Unauthorized` against the private GitLab index — `vupi>=0.0.10`
      unavailable (only `vupi==0.0.1` served). This is the same environment /
      credentials blocker recorded in Phase 2, outside this phase's scope
      (which only touches `backend_template/Containerfile`).
- [x] Regression guard for the 4 build-independent tests:
      `uv run pytest "tests/test_e2e.py::test_scaffolded_package_passes_check" "tests/test_e2e.py::test_scaffolded_backend_package_passes_check" "tests/test_e2e.py::test_scaffolded_package_has_no_backend_or_frontend" "tests/test_e2e.py::test_scaffolded_fullstack_package_passes_check" -m e2e --no-cov -q 2>&1 | tee /tmp/t65_phase3_guard.log`
      → `grep -q "4 passed" /tmp/t65_phase3_guard.log`.
      Confirmed: `4 passed in 202.80s` — no regression in the build-independent
      scaffolding / `just check` tests.
- [x] Spot-check the build fix in captured output — the metadata generation that
      this fix targets succeeded: `grep -ci "Failed to generate package
      metadata\|Error getting the version from source\|Readme file does not
      exist\|file does not exist" /tmp/t65_phase3.log` → `0`. (`Build command
      failed` IS present, but for the unrelated `401 Unauthorized` dependency
      resolution failure, not the metadata step the fix addresses — STEP 5 now
      reaches `uv sync` with the correctly renamed `<module>/__init__.py` mount.)
- [x] Flake vs. regression distinction (Open Risk): the 3 runtime failures occur
      *after* a clean build start, at in-container dependency resolution against
      the private GitLab index (`401 Unauthorized`, `vupi>=0.0.10` unavailable).
      This is deterministic environment/credentials breakage, not a flake and not
      a regression of this fix — re-running cannot resolve a credentials/index
      gap. The metadata errors this task targeted are fully gone (0 in the log).
- [ ] Final confirmation — no edits outside the target file:
      `git diff --name-only` lists only `backend_template/Containerfile`.
      `git diff --name-only` shows `backend_template/Containerfile` (the target)
      plus `docs/containerization.md` (documentation of this same fix, updated in
      earlier lifecycle steps), and the harness-managed process files `BACKLOG.md`
      and `lifecycle_state.yml`. No code changes exist outside the target file.

---

## Testing Checkpoints

- **After Phase 1**: `test_backend_package_runs_end_to_end` no longer dies on the
  hatchling version-source `OSError` at STEP 5; the build advances (passes, or
  fails only on README / a later metadata file).
- **After Phase 2**: STEP 5 completes editable-metadata generation; the backend
  runtime test passes end-to-end (`compose up` returns 0). README mount kept only
  if Phase 1 verification showed it was required.
- **After Phase 3**: `just e` → `7 passed`; the 4 scaffolding / `just check`
  tests remain green; all 3 runtime tests built and started their containers.
  Done = green suite with no edits outside `backend_template/Containerfile`.
