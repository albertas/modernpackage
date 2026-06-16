# Structure Outline

## Approach

The repo is already internally consistent on **Python 3.14**, which is the latest
stable release as of 2026-06-16. So this is a cleanup task, not a version bump:
re-confirm 3.14 is still latest, fix the one real inconsistency (a CI workflow
*filename* that says `python311` while its contents say `3.14`), then prove
repo-wide consistency via `git grep`. There are no DB/service/API/UI layers here;
each "slice" is a config/CI/docs change that leaves the repo in a self-consistent,
independently verifiable state. A contingency slice covers the case where 3.15+
has shipped (full bump).

---

## Phase 1: Confirm latest-stable version (decision gate)

Re-confirm the assumption underpinning the whole task: that 3.14 is still the
latest stable Python. This gate decides whether the remaining work is a cleanup
(Phase 2–3) or a full bump (Phase 4).

**Files**: none changed — investigation only.
**Key changes**: none. Output is a single decision: `LATEST == 3.14` (proceed to
Phase 2) **or** `LATEST >= 3.15` (skip to Phase 4).

**Verify** (agent-executable, unattended):
- `curl -s https://www.python.org/downloads/ | grep -oE 'Latest Python 3 Release - Python 3\.[0-9]+'`
  — capture the announced latest stable minor version.
- Assert it equals `3.14`. If it returns `3.15` or higher, record the new value
  and branch to Phase 4 instead of Phase 2.

---

## Phase 2: Rename the stale CI workflow file

Rename `.github/workflows/check-modernpackage-on-python311.yml` →
`check-modernpackage-on-python314.yml` so the filename matches its 3.14 contents.
Use `git mv` to preserve history. File *contents* are already correct and are not
touched.

**Files**:
- `.github/workflows/check-modernpackage-on-python311.yml` → `.github/workflows/check-modernpackage-on-python314.yml` (rename only)

**Key changes**:
- No code/type signatures. One filesystem rename via
  `git mv .github/workflows/check-modernpackage-on-python311.yml .github/workflows/check-modernpackage-on-python314.yml`.

**Verify** (agent-executable, unattended):
- `git grep -n 'python311'` returns **nothing** (exit code 1, empty output).
- `test -f .github/workflows/check-modernpackage-on-python314.yml` succeeds.
- `git log --oneline --follow .github/workflows/check-modernpackage-on-python314.yml`
  shows pre-rename history (confirms `git mv`, not delete+add).
- Workflow contents unchanged:
  `git grep -nE '3\.14' .github/workflows/check-modernpackage-on-python314.yml`
  still shows `name: ...Python3.14`, `Set up Python 3.14`, and
  `python-version: "3.14"`.
- `just check` (or `make check`) still passes — confirms the rename didn't break
  config discovery.

---

## Phase 3: Prove repo-wide version consistency

Run the design's full verification suite to confirm no functional config, doc, or
CI value contradicts 3.14, and that the only sub-3.14 strings remaining are the
documented example-traceback exceptions. No edits expected; this phase is the
acceptance gate. If any unexpected hit appears, it becomes a follow-up edit
within this phase, then re-verify.

**Files**: none changed (verification only; remediation only if a check fails).

**Key changes**: none expected.

**Verify** (agent-executable, unattended — all must hold):
- `git grep -n 'python311'` → empty.
- `git grep -nE 'python[_-]?3\.1[0-3]'` → returns **only** the example-traceback
  lines in `README.md` (lines ~66,68,71,73) and
  `issues/no_internet_connection_message` (lines ~8–15). Any other hit is a
  failure to remediate.
- `git grep -nE '3\.14|python314'` → all hits agree (pyproject `requires-python`,
  trove classifier, mypy `python_version`, `Makefile` `uv venv -p 3.14`, CI
  `python-version`/name, renamed workflow filename, docs prose). No `3.14` site
  contradicts another.
- `just check` and/or `make check` pass.

---

## Phase 4 (contingency): Full version bump to 3.15+

Only execute if Phase 1 found `LATEST >= 3.15`. Update every version-bearing site
in lockstep to the new minor `X.Y`, then re-run Phase 3's consistency suite
against the new number.

**Files**:
- `pyproject.toml` — `requires-python` (`:8`), trove classifier (`:15`), mypy `python_version` (`:84`)
- `Makefile` — `uv venv -p 3.14` (`:18`)
- `.github/workflows/check-modernpackage-on-python314.yml` — `python-version`, `name`, `Set up Python` step, **and** the filename (`...-on-pythonXYY.yml`)
- `docs/specification.md` (`:74,87,92`) and `docs/architecture.md` (`:105,116,145,177,194`) — prose `>= X.Y` / "Python X.Y"

**Key changes**:
- Mechanical string replacement `3.14` → `3.<new>` (and `314` → `3<new>` in the
  filename) across the sites above. No new abstraction, no ruff `target-version`,
  no `.gitlab-ci.yml` numeric pin (those remain deliberate non-changes per design).

**Verify** (agent-executable, unattended):
- `git grep -nE '3\.14|python314'` → **empty** (no stale 3.14 left).
- `git grep -nE 'python[_-]?3\.1[0-3]'` → only the documented example tracebacks.
- `just check` / `make check` pass against the new interpreter target.

---

## Testing Checkpoints

Use these to resume if context resets:

1. **After Phase 1**: A recorded decision — `LATEST == 3.14` (do Phases 2–3) or
   `LATEST >= 3.15` (do Phase 4). No files changed yet.
2. **After Phase 2**: `git grep -n 'python311'` is empty; the workflow file is
   named `...-on-python314.yml` with history preserved and contents unchanged;
   `just check` passes.
3. **After Phase 3**: All three `git grep` invariants hold (no `python311`; only
   example-traceback lines match sub-3.14; all `3.14` sites agree); `just check`
   and `make check` pass. **This is the done state for the cleanup path.**
4. **After Phase 4 (only if taken)**: No `3.14` strings remain; all sites and the
   workflow filename reflect the new latest stable; checks pass.

**Explicit non-sliceable / out-of-scope notes** (per design):
- `.gitlab-ci.yml: image: python:latest` is left as-is (self-updating; pinning
  would create drift).
- Example tracebacks (`python3.12`) are left untouched (historical record).
- The `make init` scaffolder is **not** extended to rewrite Python versions; the
  rename and any bump reach generated packages only via the source repo, by
  construction. No per-package migration is in scope.
- Branch-protection rules referencing the old check name live in repo settings,
  outside the codebase — flag to the user; not an editable file.
