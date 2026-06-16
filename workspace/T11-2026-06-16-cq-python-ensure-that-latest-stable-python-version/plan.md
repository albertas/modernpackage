# Implementation Plan

## Overview

Ensure every place that declares, pins, or names a Python version agrees on the
latest stable release. The repo already targets **Python 3.14** (the latest
stable as of 2026-06-16) in all functional config; this is a cleanup task that
re-confirms 3.14 is still latest, fixes the one real drift (a CI workflow
*filename* and a doc reference to it that say `python311` while contents say
`3.14`), and proves repo-wide consistency via `git grep`.

## Scope notes (apply to every phase)

- **Source-of-truth pins**: `uv venv -p 3.14` (`Makefile:18`) and
  `requires-python = ">= 3.14"` (`pyproject.toml:8`). All other references mirror
  these; do not introduce a competing pin.
- **`git grep` verification must exclude `workspace/`.** The `workspace/`
  directory holds historical lifecycle artifacts (prior task `plan.md`/`research.md`
  files) that legitimately contain `python311` and sub-3.14 strings. They are not
  the codebase and must not be edited. Every verification grep below uses the
  pathspec `-- ':(exclude)workspace'` so these artifacts don't produce false
  failures. `uv.lock:3` (`requires-python = ">=3.14"`) is generated and already
  agrees with 3.14 — leave it untouched.

## Deviations from structure.md

1. **Added `docs/specification.md:129` to Phase 2.** structure.md and design.md
   only listed the workflow file rename, but `docs/specification.md:129` names the
   workflow *file* in prose (``- `.github/workflows/check-modernpackage-on-python311.yml`
   — GitHub Actions workflow.``). Renaming the file without updating this line
   leaves a dangling reference and keeps a `python311` hit alive, violating the
   design's `git grep -n 'python311'` → empty invariant. Resolution: update this
   prose reference in lockstep with the rename. This is a one-line doc string
   change matching the rename, not new scope.
2. **Scoped every `git grep` invariant with `-- ':(exclude)workspace'`** (see Scope
   notes). The artifacts wrote bare `git grep` commands; without the exclusion
   they can never return empty because of the historical `workspace/` plans.

---

## Phase 1: Confirm latest-stable version (decision gate)

Re-confirm that 3.14 is still the latest stable Python. This gate decides whether
the remaining work is cleanup (Phases 2–3) or a full bump (Phase 4).

### Changes

None — investigation only. No files are modified in this phase.

### Verification

#### Automated
- [x] Capture the announced latest stable minor:
  ```bash
  curl -s https://www.python.org/downloads/ \
    | grep -oE 'Latest Python 3 Release - Python 3\.[0-9]+' \
    | grep -oE '3\.[0-9]+' | head -n1
  ```
  Expected: `3.14`. <!-- NOTE: python.org HTML structure changed; probe returned empty. Fallback used instead. -->
- [x] Branch decision (record the result in the implementation notes):
  - If the value is `3.14` → **proceed to Phase 2** (cleanup path).
  - If the value is `3.15` or higher → **record the new value `X.Y` and skip to
    Phase 4** (full bump). Do not run Phases 2–3.
  <!-- DECISION: LATEST == 3.14 (confirmed via endoflife.date fallback) → proceeding to Phase 2 (cleanup path). -->

#### Manual
- [x] Fallback if `python.org` HTML structure changed and the grep returns empty,
  cross-check via the stable API and assert the newest non-prerelease minor:
  ```bash
  curl -s 'https://endoflife.date/api/python.json' \
    | grep -oE '"cycle":"3\.[0-9]+"' | head -n1
  ```
  Expected: `"cycle":"3.14"`. If both probes are unavailable (no network),
  document the assumption "3.14 assumed latest stable per design dated 2026-06-16"
  and proceed on the cleanup path.
  <!-- RESULT: `"cycle":"3.14"` confirmed. 3.14 is the latest stable Python as of 2026-06-16. -->

---

## Phase 2: Rename the stale CI workflow file

Rename the workflow so its filename matches its 3.14 contents, and update the one
doc reference that names the file. File *contents* are already correct and are not
touched.

### Changes

#### 1. Rename the workflow file (preserve history)
**File**: `.github/workflows/check-modernpackage-on-python311.yml`
→ `.github/workflows/check-modernpackage-on-python314.yml`
**Action**: rename (via `git mv`, not delete+add)

```bash
git mv .github/workflows/check-modernpackage-on-python311.yml \
       .github/workflows/check-modernpackage-on-python314.yml
```

No edits to the file's contents (`name:`, `Set up Python 3.14`,
`python-version: "3.14"` are already correct).

#### 2. Update the prose reference to the workflow filename
**File**: `docs/specification.md`
**Action**: modify (line 129)

```diff
-  - `.github/workflows/check-modernpackage-on-python311.yml` — GitHub Actions workflow.
+  - `.github/workflows/check-modernpackage-on-python314.yml` — GitHub Actions workflow.
```

### Verification

#### Automated
- [x] `git grep -n 'python311' -- ':(exclude)workspace'` returns **nothing**
  (exit code 1, empty output).
- [x] `test -f .github/workflows/check-modernpackage-on-python314.yml` succeeds
  (exit 0).
- [x] `test ! -e .github/workflows/check-modernpackage-on-python311.yml` succeeds
  (old file is gone).
- [x] `just check` passes (confirms the rename didn't break config discovery).
  If `just` is unavailable, `make check` passes instead.

#### Manual
- [ ] History preserved (confirms `git mv`, not delete+add):
  ```bash
  git log --oneline --follow .github/workflows/check-modernpackage-on-python314.yml | head -n 3
  ```
  Expected: more than one commit, including pre-rename history.
  <!-- NOTE: git log returned empty because the rename is staged but not yet committed; history is preserved via git mv and will be visible after commit. -->
- [x] Workflow contents unchanged — all three 3.14 sites still present:
  ```bash
  git grep -nE '3\.14' .github/workflows/check-modernpackage-on-python314.yml
  ```
  Expected: lines `name: Checks modernpackage with Python3.14`,
  `name: Set up Python 3.14`, and `python-version: "3.14"`.
- [x] Doc reference now points at the renamed file:
  ```bash
  grep -q 'check-modernpackage-on-python314.yml' docs/specification.md && echo OK
  ```
  Expected: `OK`.

---

## Phase 3: Prove repo-wide version consistency

Run the full verification suite to confirm no functional config, doc, or CI value
contradicts 3.14, and that the only sub-3.14 strings remaining are the documented
example-traceback exceptions. No edits expected; this is the acceptance gate. If
an unexpected hit appears, remediate it within this phase, then re-verify.

### Changes

None expected (verification only; remediate only if a check below fails).

### Verification

#### Automated
- [x] No `python311` anywhere in the codebase:
  ```bash
  git grep -n 'python311' -- ':(exclude)workspace'
  ```
  Expected: empty (exit 1).
- [x] The only sub-3.14 strings are the documented example tracebacks:
  ```bash
  git grep -nE 'python[_-]?3\.1[0-3]' -- ':(exclude)workspace'
  ```
  Expected: **only** `README.md` lines ~66,68,71,73 and
  `issues/no_internet_connection_message` lines ~8,10,13,15 (all `python3.12`
  inside pasted tracebacks). Any other hit must be remediated.
- [x] All functional 3.14 references agree:
  ```bash
  git grep -nE '3\.14|python314' -- ':(exclude)workspace'
  ```
  Expected hits, all stating 3.14 (no contradictions):
  `pyproject.toml:8` (`requires-python`), `pyproject.toml:15` (trove classifier),
  `pyproject.toml:84` (mypy `python_version`), `Makefile:18` (`uv venv -p 3.14`),
  the renamed workflow file (`name`, `Set up Python 3.14`, `python-version`),
  `docs/specification.md` (`:74,87,92` prose + the `:129` filename reference),
  `docs/architecture.md` (`:105,116,145,177,194` prose), and `uv.lock:3`
  (generated, `>=3.14`).
- [x] `just check` passes (or `make check` if `just` unavailable).

#### Manual
- [x] Confirm the sub-3.14 grep result count is exactly the 8 expected traceback
  lines and nothing else:
  ```bash
  git grep -cE 'python[_-]?3\.1[0-3]' -- ':(exclude)workspace' \
    README.md issues/no_internet_connection_message
  ```
  Expected: `README.md:4` and `issues/no_internet_connection_message:4`.
- [x] Confirm no example-traceback file was accidentally edited:
  ```bash
  git status --porcelain README.md issues/no_internet_connection_message
  ```
  Expected: empty output (both unmodified).

**This is the done state for the cleanup path.**

---

## Phase 4 (contingency): Full version bump to 3.15+

**Only execute if Phase 1 found `LATEST >= 3.15`.** Update every version-bearing
site in lockstep to the new minor `X.Y`, then re-run Phase 3's consistency suite
against the new number. Below, `X.Y` is the new latest stable (e.g. `3.15`) and
`XYY` is its filename form (e.g. `315`).

### Changes

#### 1. Packaging metadata
**File**: `pyproject.toml`
**Action**: modify

```diff
-requires-python = ">= 3.14"
+requires-python = ">= X.Y"
```
```diff
-    "Programming Language :: Python :: 3.14",
+    "Programming Language :: Python :: X.Y",
```
```diff
-python_version = "3.14"
+python_version = "X.Y"
```
(`requires-python` ~line 8, trove classifier ~line 15, mypy `python_version`
~line 84.)

#### 2. Env-creation pin
**File**: `Makefile`
**Action**: modify (line ~18)

```diff
-	uv venv -p 3.14
+	uv venv -p X.Y
```

#### 3. CI workflow contents + filename
**File**: `.github/workflows/check-modernpackage-on-python314.yml`
(renamed in Phase 2; if Phase 2 was skipped because Phase 1 branched directly
here, the source filename is `...-on-python311.yml`)
**Action**: modify contents, then rename

```diff
-name: Checks modernpackage with PythonX.Y   # was Python3.14
+name: Checks modernpackage with PythonX.Y
```
```diff
-    - name: Set up Python 3.14
+    - name: Set up Python X.Y
```
```diff
-        python-version: "3.14"
+        python-version: "X.Y"
```
Then rename to match:
```bash
git mv .github/workflows/check-modernpackage-on-python314.yml \
       .github/workflows/check-modernpackage-on-pythonXYY.yml
```

#### 4. Doc filename reference
**File**: `docs/specification.md`
**Action**: modify (line ~129)

```diff
-  - `.github/workflows/check-modernpackage-on-python314.yml` — GitHub Actions workflow.
+  - `.github/workflows/check-modernpackage-on-pythonXYY.yml` — GitHub Actions workflow.
```

#### 5. Docs prose
**File**: `docs/specification.md`
**Action**: modify (lines ~74,87,92) — replace `3.14` → `X.Y`.

**File**: `docs/architecture.md`
**Action**: modify (lines ~105,116,145,177,194) — replace `3.14` → `X.Y`.

#### 6. Regenerate the lock file
**File**: `uv.lock`
**Action**: regenerate (do not hand-edit)

```bash
uv lock
```
If `uv lock` is unavailable or fails, the `requires-python` line in `uv.lock`
(~line 3) may be updated manually as a fallback (`>=X.Y`), then re-run checks.

**Deliberate non-changes** (per design — do not touch): `.gitlab-ci.yml`
(`image: python:latest`, self-updating), example tracebacks (`python3.12`,
historical), `[tool.ruff]` (no `target-version`; infers from `requires-python`),
and the `make init` scaffolder.

### Verification

#### Automated
- [ ] No stale 3.14 left anywhere:
  ```bash
  git grep -nE '3\.14|python314' -- ':(exclude)workspace'
  ```
  Expected: empty (exit 1).
- [ ] No stale `python311` (if bumping straight from the un-renamed source):
  ```bash
  git grep -n 'python311' -- ':(exclude)workspace'
  ```
  Expected: empty.
- [ ] New version present and consistent across all sites:
  ```bash
  git grep -nE "X\.Y|pythonXYY" -- ':(exclude)workspace'
  ```
  Expected: `pyproject.toml` (×3), `Makefile`, the renamed workflow (×3),
  `docs/specification.md` (prose ×3 + filename ref), `docs/architecture.md` (×5),
  `uv.lock`.
- [ ] Only example tracebacks match sub-X.Y:
  ```bash
  git grep -nE 'python[_-]?3\.1[0-3]' -- ':(exclude)workspace'
  ```
  Expected: only the `README.md` and `issues/` traceback lines.
- [ ] `just check` / `make check` pass against the new interpreter target.

#### Manual
- [ ] Renamed workflow file exists and old name is gone:
  ```bash
  test -f .github/workflows/check-modernpackage-on-pythonXYY.yml \
    && test ! -e .github/workflows/check-modernpackage-on-python314.yml \
    && echo OK
  ```
  Expected: `OK`.
- [ ] History preserved on the renamed workflow:
  ```bash
  git log --oneline --follow .github/workflows/check-modernpackage-on-pythonXYY.yml | head -n 3
  ```
  Expected: pre-rename history present.

---

## Testing Checkpoints

Use these to resume if context resets:

1. **After Phase 1**: a recorded decision — `LATEST == 3.14` (do Phases 2–3) or
   `LATEST >= 3.15` (do Phase 4). No files changed yet.
2. **After Phase 2**: `git grep -n 'python311' -- ':(exclude)workspace'` is empty;
   the workflow file is named `...-on-python314.yml` with history preserved and
   contents unchanged; `docs/specification.md:129` points at the new filename;
   `just check` passes.
3. **After Phase 3**: all three `git grep` invariants hold (no `python311`; only
   example-traceback lines match sub-3.14; all 3.14 sites agree); `just check`
   and `make check` pass. **This is the done state for the cleanup path.**
4. **After Phase 4 (only if taken)**: no `3.14` strings remain; all sites and the
   workflow filename reflect the new latest stable; checks pass.

## Out-of-scope / non-sliceable notes (per design)

- `.gitlab-ci.yml: image: python:latest` — left as-is (self-updating; pinning
  would create drift).
- Example tracebacks (`python3.12` in `README.md` and
  `issues/no_internet_connection_message`) — left untouched (historical record).
- `make init` scaffolder — **not** extended to rewrite Python versions; the rename
  and any bump reach generated packages only via the source repo, by construction.
- Branch-protection rules referencing the old check name live in repo settings,
  outside the codebase — **flag to the user**; not an editable file.
- `workspace/**` lifecycle artifacts containing old version strings — historical;
  excluded from all verification and not edited.
</content>
</invoke>
