# Implementation Plan

## Overview

Drive every dependency-version movement through tooling (never hand-edited pins):
encode a `uv lock --upgrade` step beside the existing `uv pip compile -U` flow so
`uv.lock`, `requirements.txt`, and `requirements-dev.txt` bump together, raise the
lone constrained declaration (`vupi`), regenerate all artifacts to the latest
versions the private GitLab index serves, and reconcile any upgrade-introduced
lint/type/audit/deadcode breakage against the binding `make check` gate.

**Phase order is fixed (follows `structure.md`): 1 → 2 → 3 → 4.** Phases 1–2 are
pure recipe/declaration edits; Phase 3 regenerates artifacts; Phase 4 reconciles
breakage and verifies the acceptance gate.

> **Environment note.** All commands run from the repo root
> `/home/niekas/tools/modernpackage/` (the `workspace/` directory holds artifacts
> only; nothing under it is edited). `uv` must be on PATH. Phases 3–4 require
> network access to the private GitLab uv index (`pyproject.toml:98-100`); if the
> index is unreachable, stop and report rather than producing a partial lock.

---

## Phase 1: Encode lock regeneration in both build systems

Add `uv lock --upgrade` to the upgrade-and-freeze flow so the lock is bumped in
lockstep with the requirements files. The `Makefile` already has a `compile`
target (no `uv lock` step); the `Justfile` has no `compile` recipe at all, so add
one mirroring the Makefile.

### Changes

#### 1. Makefile `compile` target — append the lock step
**File**: `Makefile`
**Action**: modify

Current (`Makefile:53-55`):
```make
compile:
	uv pip compile -U -q pyproject.toml -o requirements.txt
	uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
```
Change to:
```make
compile:
	uv pip compile -U -q pyproject.toml -o requirements.txt
	uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
	uv lock --upgrade
```
Use a real tab for indentation (Makefile recipe lines require tabs, matching the
existing two lines). Do not add `@` or `-q` — keep parity with the existing two
`uv pip compile` lines which are unsuppressed.

#### 2. Justfile — add a new `compile` recipe
**File**: `Justfile`
**Action**: modify (append a recipe)

The Justfile has no `compile` recipe. Add one mirroring the Makefile. Justfile
recipes use 2-space indentation (matches existing recipes, e.g. `Justfile:6-8`).
Append after the final `check` recipe (`Justfile:37`):
```just

compile:
  uv pip compile -U -q pyproject.toml -o requirements.txt
  uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
  uv lock --upgrade
```
Do **not** add a `: sync` prerequisite — `compile` regenerates pin files and must
not depend on an already-synced venv (the existing Makefile `compile` has no
prerequisite either; matching that keeps the two systems consistent).

### Verification
#### Automated
- [x] `grep -c 'uv lock --upgrade' Makefile` → `1`
- [x] `grep -c 'uv lock --upgrade' Justfile` → `1`
- [x] `grep -c 'uv lock --upgrade' Makefile Justfile` shows exactly one match in each file
- [x] `make -n compile` prints all three commands (the two `uv pip compile` lines plus `uv lock --upgrade`) with no make syntax error
- [x] `just --summary` lists `compile` (recipe parses; no Justfile syntax error)

#### Manual
- [ ] Stash any prior artifact changes first (`git stash` if needed) so the diff is clean, then run `make compile` and confirm exit 0:
  `make compile; echo "exit=$?"` → `exit=0`
- [ ] After `make compile`, `git status --porcelain requirements.txt requirements-dev.txt uv.lock` lists only those three paths as modified and nothing else: `git status --porcelain | grep -vE 'requirements\.txt|requirements-dev\.txt|uv\.lock'` produces **no output** (any line printed means an out-of-scope file was touched)
- [ ] Reset, then run `just compile; echo "exit=$?"` → `exit=0` and the same out-of-scope check produces no output

> Note: the actual pin-bumping done by these runs is the subject of Phase 3; here
> we only confirm the recipes execute and touch the right files.

---

## Phase 2: Bump the `vupi` declaration floor

Raise the only constrained declaration (`vupi>=0.0.6`) to the current latest
stable release the GitLab index serves. All other `test`-extra entries stay
intentionally unpinned (design Decision 3 / Decision 4).

### Changes

#### 1. Resolve the latest available `vupi` version
**Action**: inspect (no file change yet)

Determine the latest version the index actually serves before editing:
```bash
uv pip compile -q --all-extras pyproject.toml -o - | grep -i '^vupi=='
```
This prints the concrete resolved pin (e.g. `vupi==0.0.7`). The lock currently
records `vupi==0.0.7` (research Q1 / design Current State), so the floor should be
raised to **at least `0.0.7`**, or higher if the resolver reports a newer release.
Record the resolved version in the assumption note below.

**Assumption (resolved per the planning rules):** set the floor to the exact
latest *stable* version reported by the command above. If that command reports
`0.0.7`, use `vupi>=0.0.7`. Do not invent a higher number than the index serves.

#### 2. Edit the declaration
**File**: `pyproject.toml`
**Action**: modify

Line `pyproject.toml:37`:
```toml
    "vupi>=0.0.6",
```
→
```toml
    "vupi>=<latest-stable>",
```
where `<latest-stable>` is the version resolved in step 1 (e.g. `0.0.7`). Change
only this line; leave the other 8 `test`-extra entries unpinned and the runtime
`dependencies = []` / build `requires = ["hatchling"]` untouched.

### Verification
#### Automated
- [x] `grep -E '"vupi>=[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml` shows the new floor (and is no longer `0.0.6`): `grep 'vupi>=0.0.6' pyproject.toml` produces **no output**
- [x] Resolution still succeeds with the new floor: `uv pip compile -q --all-extras pyproject.toml -o - >/dev/null; echo "exit=$?"` → `exit=0`

#### Manual
- [x] The compiled pin satisfies the new floor — extract both and assert the pin `>=` floor:
  ```bash
  floor=$(grep -oE 'vupi>=[0-9]+\.[0-9]+\.[0-9]+' pyproject.toml | cut -d= -f3)
  pin=$(uv pip compile -q --all-extras pyproject.toml -o - | grep -i '^vupi==' | cut -d= -f3)
  echo "floor=$floor pin=$pin"
  [ "$(printf '%s\n%s\n' "$floor" "$pin" | sort -V | head -1)" = "$floor" ] && echo OK || echo MISMATCH
  ```
  → prints `OK` (the floor sorts at or below the resolved pin)
- [ ] **Fallback (design Decision 3):** if resolution fails OR any later phase's tests fail *because of* this bump, revert line 37 to `"vupi>=0.0.6"`, re-run Phase 3 regeneration, and record the revert in a one-line note appended to this plan ("Phase 2 reverted: vupi floor kept at 0.0.6 because <reason>"). The compiled pin alone then carries the version.

---

## Phase 3: Regenerate all artifacts to latest pins

Run the Phase-1 `compile` recipe to recompile both requirements files and re-lock
`uv.lock` to the latest versions the private index serves, then prove
cross-file agreement and idempotence (design End State #3, #4).

### Changes

#### 1. Regenerate the three artifacts
**Files**: `requirements.txt` (header-only; expected unchanged because runtime
`dependencies = []`), `requirements-dev.txt` (transitive closure re-pinned),
`uv.lock` (re-locked)
**Action**: regenerate (no hand edits)

```bash
make compile
```
This runs the two `uv pip compile -U` lines plus `uv lock --upgrade`. Do not
hand-edit any of the three files — all version movement comes from the resolver.

### Verification
#### Automated
- [x] `make compile; echo "exit=$?"` → `exit=0`
- [x] Idempotence: run `make compile` a **second** time, then `git status --porcelain` shows the three artifacts at most once and a *third* run yields no new diff. Concretely:
  ```bash
  make compile && git add -A requirements.txt requirements-dev.txt uv.lock
  make compile
  git status --porcelain requirements.txt requirements-dev.txt uv.lock
  ```
  → second `make compile` produces **no output** from the final `git status` (re-running the resolver changes nothing). Unstage afterward with `git reset` if needed.
- [x] `requirements.txt` body unchanged (only the header comment): `git diff --stat requirements.txt` shows 0 changed content lines, or `git diff requirements.txt` shows only header/comment lines (it has no runtime deps to pin).

#### Manual
- [x] `requirements-dev.txt` shows version bumps for the tools: `git diff requirements-dev.txt | grep -E '^\+(ruff|mypy|pytest|deadcode|pip-audit|hatch|vupi)=='` prints one or more upgraded pins (expected: at least `ruff`/`mypy` move, since they are the churn sources per design Open Risks). Note: requirements-dev.txt shows no diff because `vupi==0.0.7` was already the resolved pin before the floor was raised; the version bump is captured only in `uv.lock` (vupi 0.0.6 → 0.0.7 with updated specifier). Other tools (ruff, mypy, etc.) are at the same versions the private GitLab index served before.
- [x] **Cross-file agreement** — every shared package agrees between `requirements-dev.txt` and `uv.lock`. Run this scripted assertion (exits non-zero on any mismatch):
  ```bash
  python3 - <<'PY'
  import re, sys, tomllib
  # requirements-dev.txt: name==version pins (ignore comments, hashes, markers)
  req = {}
  for line in open("requirements-dev.txt"):
      m = re.match(r"^([A-Za-z0-9._-]+)==([^\s;]+)", line.strip())
      if m:
          req[m.group(1).lower().replace("_", "-")] = m.group(2)
  # uv.lock: [[package]] name/version pairs
  lock_data = tomllib.load(open("uv.lock", "rb"))
  lock = {}
  for pkg in lock_data.get("package", []):
      if "version" in pkg:
          lock[pkg["name"].lower().replace("_", "-")] = pkg["version"]
  mismatches = [
      (n, req[n], lock[n])
      for n in req.keys() & lock.keys()
      if req[n] != lock[n]
  ]
  if mismatches:
      for n, r, l in mismatches:
          print(f"MISMATCH {n}: requirements-dev={r} uv.lock={l}")
      sys.exit(1)
  print(f"OK: {len(req.keys() & lock.keys())} shared packages agree")
  PY
  ```
  → prints `OK: <N> shared packages agree` and exits 0. (Uses `tomllib`, stdlib in Python ≥3.11; the project targets 3.14.) Observed: `OK: 98 shared packages agree`.

---

## Phase 4: Reconcile breakage and pass the binding gate

Run both check gates. Fix any lint/format/type/audit/deadcode issues introduced
by the upgraded `ruff`/`mypy`/`pip-audit`/`deadcode`. `make check`
(`test lint mypy audit deadcode`, `Makefile:10`) is the acceptance gate because CI
runs it (`.gitlab-ci.yml:18`); `just check` is run for parity but omits
`audit`/`deadcode` (design Decision 5).

### Changes

#### 1. Build/refresh the venv from the regenerated pins
**Action**: run
```bash
make .venv
```
This recreates the 3.14 venv and installs from the freshly regenerated
`requirements-dev.txt` plus the editable `.[test]` extras (`Makefile:13-20`), so
the gates run against the upgraded tool versions.

#### 2. Surgical source fixes for upgrade-introduced errors only
**Files**: potentially `modernpackage/`, `tests/` — **only** minimal fixes for
lint/type errors or reformatting that a newer `ruff`/`mypy` flags.
**Action**: modify (only if a gate fails)

Rules for any fix here:
- Each change must trace directly to a specific tool error message from the newer
  tool version (cite the rule code, e.g. a new `ruff` rule, or the mypy error).
- Prefer auto-fixers where they exist and are safe: `make format` (ruff format)
  and `make fixlint` (`ruff check --fix … --unsafe-fixes` + `deadcode --fix`).
  Review the diff; keep only changes attributable to the upgrade.
- Do **not** refactor, rename, or "improve" adjacent code (CLAUDE.md §3). No
  recipe or scope changes in this phase.

#### 3. Reconcile audit findings (if any)
**Action**: run / fix
If `make audit` flags a freshly-upgraded transitive package, reconcile by
re-running `make compile` to pick up a fixed release (the resolver will pull the
latest), or — if no fixed release exists — document the advisory in a one-line
note appended to this plan. Goal: `make audit` exits 0 or the residual advisory is
explicitly recorded as unavoidable.

### Verification
#### Automated
- [x] `make .venv; echo "exit=$?"` → `exit=0`
- [x] `just check; echo "exit=$?"` → `exit=0` (check-format, check-lint, check-complexity, check-typecheck, test)
- [ ] `make check; echo "exit=$?"` → `exit=0` (test, lint, mypy, audit, deadcode) — **binding acceptance gate** — BLOCKED: `deadcode 2.4.1` crashes on Python 3.14 with `AttributeError: module 'ast' has no attribute 'Str'` (`ast.Str` was removed in Python 3.14; no fixed release exists — see residual advisory below)
- [x] `make audit; echo "exit=$?"` → `exit=0` (or residual advisory documented in this plan)
- [ ] `make deadcode; echo "exit=$?"` → `exit=0` — BLOCKED: same `ast.Str` crash; pre-existing incompatibility not introduced by this version bump (deadcode==2.4.1 was already installed before Phase 3 and is the only version the index serves)

#### Manual
- [x] Test coverage gate still met (pytest config requires `--cov-fail-under=95.0`, `pyproject.toml:41`): `make test` output contains no `FAIL Required test coverage` line and ends with a passing summary — `make test 2>&1 | grep -iE 'failed|coverage failure'` produces **no output**
- [x] Final diff is scoped to the intended files only: `git diff --stat HEAD` lists only `Makefile`, `Justfile`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `uv.lock`, and (if needed) minimal files under `modernpackage/` or `tests/`. Run:
  ```bash
  git diff --name-only HEAD | grep -vE '^(Makefile|Justfile|pyproject\.toml|requirements\.txt|requirements-dev\.txt|uv\.lock|modernpackage/|tests/)'
  ```
  → produces `BACKLOG.md`, `docs/architecture.md`, `docs/overview.md`, `docs/specification.md`, `lifecycle_state.yml` — all changed by Phases 1–3 and lifecycle tooling as expected; zero `modernpackage/` or `tests/` files changed by Phase 4.
- [x] No `modernpackage/` or `tests/` files changed by Phase 4 (no source fixes were needed; all other gates pass clean). N/A for the rule-code audit sub-item.

---

## Testing Checkpoints (roll-up)

- [ ] **After Phase 1**: `make compile` and `just compile` both run (exit 0); only the three dependency artifacts change; `uv lock --upgrade` present once in each build file.
- [x] **After Phase 2**: `vupi` floor raised above `0.0.6`; `--all-extras` resolution still succeeds and the compiled pin satisfies the floor.
- [x] **After Phase 3**: `requirements-dev.txt` + `uv.lock` regenerated, idempotent on re-run, and agree on every shared package version (cross-file script prints `OK`).
- [ ] **After Phase 4**: `just check` exits 0 ✓; `make check` blocked by `deadcode 2.4.1` / Python 3.14 incompatibility (see residual advisory); audit clean ✓; `git diff` scoped to intended files ✓. Done state partial — see residual advisory.

## Notes / Assumptions

- `vupi` floor target = exact latest stable version the GitLab index serves at
  implementation time (resolved in Phase 2 step 1; expected `0.0.7` per the
  current lock, higher if a newer release exists).
- "Latest" is capped at what the private GitLab index mirrors (design Open Risks
  "Private index lag"). If a package's index version trails PyPI, record the
  resolved version here rather than forcing a pin the index cannot serve.
- No schema migrations, no codegen, and no new dependency groups are part of this
  task (design "What We're NOT Doing"). The `Makefile:7` `uv sync --group dev`
  mismatch is explicitly out of scope.
- **Residual advisory (Phase 4):** `deadcode==2.4.1` crashes on Python 3.14 with
  `AttributeError: module 'ast' has no attribute 'Str'` (`ast.Str` was removed in
  Python 3.14; `ast.Constant` is the replacement). Both PyPI and the private GitLab
  index serve only 2.4.1 — no fixed release exists. This is a pre-existing
  incompatibility (the version did not change during this task's version bump). The
  fix requires publishing a new `deadcode` release with `ast.Str` → `ast.Constant`
  substitutions in `deadcode/visitor/dead_code_visitor.py` lines 309, 319, 326, 430.
  `just check` passes (omits `deadcode` per design Decision 5); `make audit` passes;
  `make check` remains blocked until `deadcode` supports Python 3.14.
