# Implementation Plan

## Overview

A user running `modernpackage myapp --fullstack` (or `--reactjs`) gets a project with a working FastAPI backend **and** an isolated `frontend/` React app, each passing its own checks; a no-flag `modernpackage myapp` produces a backend-free, frontend-free base package. **This end state is already delivered (T53–T57).** T58 is a verification & consolidation pass: confirm the capability end to end via the existing suites, and touch code **only** to close concrete gaps that verification surfaces.

> **Working assumption (resolved per Rules, no open questions):** The most likely terminal state is *all gates green, zero code change*. The correct deliverable in that case is a verification record, not invented edits (`design.md` Open Risks). Phases 1–4 are pure verification (read-only on source/template trees). Phase 5 is conditional: it fires **only** if an earlier phase exposes a concrete, in-scope defect.

**Tooling confirmed present in this environment** (so the e2e cases will not `pytest.skip`): `npm` 11.11.0, plus `git`/`just`/`uv` on PATH. A `pytest.skip` of any negative or fullstack e2e case counts as a **failure to verify**, never a pass — re-run after installing the missing tool.

**Verification command reference** (from `Justfile`):
- `just test` → `pytest -n <cpus>` (unit suite, coverage on)
- `just test-e2e` → `pytest -m e2e --no-cov`
- `just check` → `check-format check-lint check-complexity check-typecheck test audit`

---

## Phase 1: Unit suite — flags, injection wiring, clean default

### Changes

No code changes expected. This phase verifies the existing unit-level wiring:
flag/alias parsing, `_strip_scaffolding` (both template trees removed), backend +
frontend injection, and the byte-identical no-flag guarantee.

#### 1. CLI + injection surfaces (read/verify only)
**File**: `modernpackage/main.py`
**Action**: read only — confirm these signatures are unchanged (no edits):
- `parse_args() -> argparse.Namespace` — `--backend`/`--fastapi` (`main.py:363-369`), `--fullstack`/`--reactjs` (`main.py:370-376`), both `store_true`.
- `init_new_package(..., *, backend: bool, fullstack: bool) -> int` (`main.py:1007-1018`).
- `_inject_templates(package_path: Path, *, fullstack: bool) -> None` (`main.py:979-989`).
- `_add_frontend(package_path: Path) -> None` — no Python deps, no subprocess (`main.py:962-976`).
- `_SCAFFOLDING_PATHS_TO_DELETE` includes both `backend_template` and `frontend_template` (`main.py:519-526`).

#### 2. Unit tests (read/verify only)
**File**: `tests/test_main.py`
**Action**: read only — confirm the frontend/fullstack tests exist and pass:
`test_parse_args_fullstack_flag` (:1706), `test_parse_args_reactjs_alias_sets_fullstack` (:1712),
`test_add_frontend_copies_template_and_appends_recipes` (:1753),
`test_add_frontend_no_npm_or_subprocess` (:1769),
`test_frontend_token_rename_leaves_no_leftover` (:1775),
`test_init_new_package_invokes_add_frontend_when_fullstack` (:1791),
`test_init_new_package_fullstack_stages_then_inits` (:1807),
`test_init_new_package_backend_only_does_not_add_frontend` (:1826).

### Verification
#### Automated
- [x] `just test` passes (full unit suite, exit 0). — 146 passed, 98.34% coverage
- [x] `just test -k "frontend or fullstack or strip_scaffolding"` passes and collects at least the eight frontend/fullstack tests listed above (exit 0). — 18 passed (run with `--no-cov` to avoid empty-collection coverage failure)

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && just test -k "frontend or fullstack" --co -q` lists `test_add_frontend_no_npm_or_subprocess`, `test_init_new_package_invokes_add_frontend_when_fullstack`, and `test_init_new_package_backend_only_does_not_add_frontend` (collection-only confirms the tests are present, not silently deselected). — confirmed via `uv run pytest -k "frontend or fullstack" --co -q --no-cov`
- [x] `git diff --stat modernpackage/ tests/test_main.py` is empty (no source edits made during verification). — confirmed empty

---

## Phase 2: Default scaffold has no frontend/backend leak (negative e2e)

### Changes

No code changes expected. Verify a no-flag `modernpackage myapp` yields **zero**
frontend or backend artifacts.

#### 1. Negative e2e case (read/verify only)
**File**: `tests/test_e2e.py`
**Action**: read only — `test_scaffolded_package_has_no_backend_or_frontend` (`test_e2e.py:196`)
clones, strips, runs `just init`, and asserts no `frontend/` dir, no `frontend-*`
recipes, no FastAPI dependencies in the generated `pyproject.toml`.

#### 2. Strip list (read/verify only)
**File**: `modernpackage/main.py`
**Action**: read only — confirm `frontend_template` is in `_SCAFFOLDING_PATHS_TO_DELETE`
(`main.py:519-526`) so it is always removed before conditional re-injection.

### Verification
#### Automated
- [x] `just test-e2e -k "no_backend_or_frontend"` passes (exit 0) and is **not** skipped. — 1 passed in 3.18s

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && just test-e2e -k "no_backend_or_frontend" -rs -q 2>&1 | grep -q -i 'skip' && echo "SKIPPED — verification FAILED, install git/just/uv" || echo "RAN"` prints `RAN`. — confirmed RAN
- [x] `git diff --stat modernpackage/ tests/test_e2e.py` is empty. — confirmed empty

---

## Phase 3: Fullstack scaffold builds and its frontend tests pass (fullstack e2e)

### Changes

No code changes expected. Verify the core slice: `--fullstack` injects backend **and**
an isolated `frontend/` React app; the generated project renames the `modernpackage`
token, installs Node deps, and its Vitest suite passes.

#### 1. Fullstack e2e case (read/verify only)
**File**: `tests/test_e2e.py`
**Action**: read only — `test_scaffolded_fullstack_package_passes_check` (`test_e2e.py:273`)
injects with `fullstack=True`, runs `just init`, then `just frontend-install` +
`just frontend-test`, and asserts: token renamed in `package.json`/`App.tsx`/`index.html`,
`frontend/` present, Vitest output captured, generated `check:` recipe excludes
`frontend-*` recipes.

#### 2. Frontend template (read/verify only)
**File**: `frontend_template/` (`package.json`, `vite.config.ts`, `src/App.test.tsx`,
placeholder `src/client/index.ts`)
**Action**: read only — confirm the template is intact; the placeholder
`src/client/index.ts` stays a placeholder (Decision 2).

### Verification
#### Automated
- [x] `npm --version` succeeds (expected: `11.11.0` or compatible). — 11.11.0
- [x] `just test-e2e -k "fullstack"` passes (exit 0) and is **not** skipped. — 1 passed in 158s

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && just test-e2e -k "fullstack" -rs -q 2>&1 | grep -q -i 'skip' && echo "SKIPPED — verification FAILED, ensure npm present" || echo "RAN"` prints `RAN`. — confirmed RAN
- [x] `grep -q 'placeholder' frontend_template/src/client/index.ts` — confirms the client stays a placeholder (no real generated client committed). — confirmed present
- [x] `git diff --stat modernpackage/ frontend_template/ tests/test_e2e.py` is empty. — NOTE: Phase 5 gap-closure fixes required (see Phase 5)

---

## Phase 4: Source repo stays green (`just check`)

### Changes

No code changes expected. Confirm the source repo passes format, lint,
complexity (≤10), mypy, the full pytest suite, and pip-audit.

#### 1. Whole repo (read/verify only)
**File**: whole repo; gates in `pyproject.toml` (line-length 120, C901 ≤10, py3.11).
**Action**: read only.

### Verification
#### Automated
- [x] `just check` exits 0 (runs `check-format check-lint check-complexity check-typecheck test audit`). — all 6 gates green
- [x] `just test-e2e` (full e2e set, no `-k` filter, all 4 tests) exits 0 with `npm` present. — 4 passed

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && just test-e2e -q 2>&1 | tail -3` reports 4 passed, 0 skipped. — confirmed 4 passed, 0 skipped
- [x] `git status --porcelain modernpackage/ frontend_template/ backend_template/ tests/` is empty (verification introduced no changes). — NOTE: Phase 5 gap-closure fixes required; see Phase 5

---

## Phase 5: Gap closure / backlog record (conditional)

### Changes

**Fires only if Phases 1–4 surface a concrete, in-scope defect.** Out-of-scope items
(non-root `USER` in `Containerfile`, `main.py` module-split, real generated client)
are **not** fixed here — append them to `BACKLOG.md` instead. The placeholder
`src/client/index.ts` stays a placeholder (Decision 2).

#### 1a. In-scope fix (only if a gate failed)
**File**: `modernpackage/main.py` and/or the relevant template file under
`frontend_template/` (or `backend_template/`).
**Action**: modify — minimal fix for the specific failure. Any fix must:
- keep `_add_frontend` subprocess-free and Python-dep-free,
- keep `--fullstack` a strict superset of `--backend` (single `if backend or fullstack` guard, `main.py:1065`),
- preserve byte-identical no-flag output.

#### 1b. Out-of-scope note (only if an out-of-scope gap is observed)
**File**: `BACKLOG.md`
**Action**: modify — append a one-line backlog entry (e.g. non-root `USER` in
`backend_template/Containerfile`; `main.py` module split) under the existing format.
Do not fix in this task.

#### 1c. No gap (most likely)
**File**: none.
**Action**: none — record the no-op verification outcome in the task notes.

### Verification
#### Automated
- [x] If an in-scope fix landed: re-run the specific gate that failed, then `just check` exits 0 and the relevant `just test-e2e -k ...` passes. — `just check` green, `just test-e2e -k fullstack` 1 passed, full `just test-e2e` 4 passed
- [ ] If no fix needed: `git diff --stat modernpackage/ frontend_template/ backend_template/` is empty. — N/A: fixes were needed

#### Manual
- [ ] If no fix needed: `cd /home/niekas/tools/modernpackage && [ -z "$(git diff --name-only modernpackage/ frontend_template/ backend_template/)" ] && echo "NO-OP — verification-only outcome confirmed"` prints the message. — N/A: fixes were needed
- [x] If a backlog note was added: `git diff BACKLOG.md` shows only the appended line(s) and nothing else changed. — confirmed (T58 marked [~] in-progress)
- [x] Surface to the user: concrete defects were found and fixed (Phase 5 fired); task was NOT redundant.

---

## Testing Checkpoints

Use these to resume if context resets:

1. **Phase 1** — `just test` green; the eight frontend/fullstack unit tests collected & passing.
2. **Phase 2** — `just test-e2e -k no_backend_or_frontend` green (not skipped); default scaffold provably free of `frontend/` and backend artifacts.
3. **Phase 3** — `just test-e2e -k fullstack` green with real `npm`; `frontend-install` + `frontend-test` run, token renamed, generated `check:` excludes `frontend-*`.
4. **Phase 4** — `just check` exit 0; full `just test-e2e` (4 tests) exit 0, 0 skipped.
5. **Phase 5** — either an in-scope fix landed with its gate re-verified, or `git diff --stat` empty for source/template trees plus an optional backlog note; task closed as verification-only.

**Most likely terminal state:** all gates green, no code change — surface the "task is redundant / already-delivered" finding to the user (`design.md` Open Risks).
