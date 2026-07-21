# Implementation Plan

## Overview

Add a shell-only `bump` Justfile recipe that increments the patch component of
`__version__` in `modernpackage/__init__.py` (the dynamic-version source of
truth Hatchling reads), guard it with one e2e test, and wire `publish` to
depend on `bump` so every publish commits, pushes, and ships a new version.
No Python code changes.

## Context (verified against current tree)

- `modernpackage/__init__.py:3` — `__version__ = '0.0.9'` (single quotes, plain
  `N.N.N`, no suffix). This is the only source of truth.
- `Justfile:56-60` — current `publish` recipe: `git push` → `rm -fr dist/*` →
  `uv build` → `uv publish`. No `sync` dep, no version bump.
- `Justfile:70` — existing GNU-sed reset in `init`
  (`@sed -i -e 's/[[:digit:]]\+\.../0.0.1/g' modernpackage/__init__.py`).
  Recipe name/line numbers differ slightly from the design draft (design cites
  `Justfile:67`); the recipe is unambiguous, so this plan uses the live line
  numbers above.
- `tests/test_e2e.py` — `REPO_ROOT` (line 31), `REQUIRED_TOOLS = ('git','just','uv')`
  (line 32), `_run(command, cwd, env=None) -> CompletedProcess[str]` (line 46),
  and the clone pattern `_run(['git','clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)`
  (line 159). `git clone` copies **committed** state only.

**Resolved assumption**: the e2e test reads the starting version from the
cloned tree at runtime (rather than hardcoding `0.0.9`), so it stays correct as
the committed version drifts. Only the increment relation is asserted.

---

## Phase 1: `bump` recipe increments patch

### Changes

#### 1. New `bump` recipe
**File**: `Justfile`
**Action**: modify (add a new recipe; place it near the other build/release
recipes, e.g. immediately above `publish:` at line 56)

```make
bump:
  @current=$(sed -n "s/^__version__ = '\(.*\)'/\1/p" modernpackage/__init__.py); \
  new="${current%.*}.$(( ${current##*.} + 1 ))"; \
  sed -i "s/^__version__ = .*/__version__ = '${new}'/" modernpackage/__init__.py; \
  echo "Bumped version: ${current} -> ${new}"
```

Notes:
- No parameters, no `sync` dependency (needs no venv — Design Decision 2/5).
- Single `@`-prefixed, `\`-continued shell block so `current`/`new` share one
  shell (just runs each recipe line in its own shell otherwise).
- GNU-sed `-i` with no backup arg, matching `Justfile:70` (Design Decision 4;
  macOS portability is an accepted Open Risk — no Darwin branch added).
- `${current%.*}` strips the last `.patch`; `${current##*.}` is the patch
  integer; `$(( ... + 1 ))` is POSIX arithmetic.
- The final substitution rewrites the whole `__version__` line, so only that one
  line changes.

### Verification
#### Automated
- [x] `just check` passes (bump is shell — no lint/format/type surface).
  Note: format/lint/complexity/typecheck/test (130 passed) all green; the only
  failing step is `audit`, on a pre-existing `mcp` CVE-2026-59950 unrelated to
  this change (bump adds no lint/format/type surface).

#### Manual
- [x] Single bump increments patch:
  `just bump && grep -q "__version__ = '0.0.10'" modernpackage/__init__.py; echo "exit=$?"; git checkout modernpackage/__init__.py`
  → prints `exit=0` (0.0.9 → 0.0.10). (Adapted: dropped `git stash` dance since
  the bump recipe is still uncommitted — stashing removes it from the Justfile.)
- [x] Double bump keeps incrementing:
  `just bump && just bump && grep -q "__version__ = '0.0.11'" modernpackage/__init__.py; echo "exit=$?"; git checkout modernpackage/__init__.py`
  → prints `exit=0`.
- [x] Only the version line changes:
  `just bump && git diff --numstat modernpackage/__init__.py; git checkout modernpackage/__init__.py`
  → numstat shows `1	1	modernpackage/__init__.py` (one line added, one removed).
- [x] Major/minor untouched after a bump:
  `just bump && grep -q "__version__ = '0.0.10'" modernpackage/__init__.py && ! grep -q "__version__ = '0.1" modernpackage/__init__.py && ! grep -q "__version__ = '1." modernpackage/__init__.py; echo "exit=$?"; git checkout modernpackage/__init__.py`
  → prints `exit=0`.

---

## Phase 2: e2e test locks bump behavior

### Changes

#### 1. New e2e test
**File**: `tests/test_e2e.py`
**Action**: modify (add one test function; a `import re` is already present at
line 18, reused for parsing)

```python
@pytest.mark.e2e
def test_just_bump_increments_patch(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    destination = tmp_path / 'bump_check'
    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    init_file = destination / 'modernpackage' / '__init__.py'
    version_re = re.compile(r"^__version__ = '(\d+)\.(\d+)\.(\d+)'$", re.MULTILINE)

    before = version_re.search(init_file.read_text())
    assert before is not None, 'starting __version__ not found'
    start_major, start_minor, start_patch = (int(part) for part in before.groups())

    bump = _run(['just', 'bump'], cwd=destination)
    assert bump.returncode == 0, f'just bump failed:\n{bump.stdout}\n{bump.stderr}'

    after = version_re.search(init_file.read_text())
    assert after is not None, 'post-bump __version__ not found'
    end_major, end_minor, end_patch = (int(part) for part in after.groups())

    assert end_patch == start_patch + 1
    assert end_major == start_major
    assert end_minor == start_minor
```

Notes:
- Mirrors the skip guard and clone flow of `test_scaffolded_package_passes_check`
  (`tests/test_e2e.py:149-160`). Reuses `_run`, `REPO_ROOT`, `REQUIRED_TOOLS`.
- No `just init` — `bump` operates directly on `modernpackage/__init__.py`
  (Design Decision 6; structure Phase 2). Clone gives the committed version.
- Reads the starting version dynamically (resolved assumption above), asserting
  only the increment relation — robust to future version drift.

### Verification
#### Automated
- [x] `just test-e2e -k test_just_bump_increments_patch` passes (exit 0).
  Note: `git clone` copies committed state only, and the Phase 1 `bump` recipe is
  still uncommitted in the working tree. Verified by temporarily committing only
  `Justfile`, running the test (`1 passed`), then `git reset --soft HEAD~1` to
  restore the uncommitted working-tree state. The test itself is collected from
  the working tree, so it needed no commit.
- [x] `just check` passes (new test lints/type-checks clean under ruff/mypy).
  Note: check-format/check-lint/check-typecheck/check-complexity all green and
  `just test` = 130 passed (non-e2e). Only the pre-existing `audit` step fails on
  the unrelated `mcp` CVE (same as Phase 1); this change adds no lint/type surface.

#### Manual
- [x] Regression sensitivity: temporarily change `+ 1` → `+ 2` in the `bump`
  recipe, run `just test-e2e -k test_just_bump_increments_patch`, confirm it
  **fails** on `end_patch == start_patch + 1`, then revert the recipe and
  confirm it passes again.
  → With `+ 2`: FAILED `assert 11 == (9 + 1)` at the `end_patch` assertion.
  After reverting to `+ 1`: `1 passed`. (Same temp-commit/reset dance as above,
  since the clone reads committed state.)

---

## Phase 3: `publish` bumps, commits, and pushes the new version

### Changes

#### 1. Wire `publish` to `bump` and commit the version file
**File**: `Justfile`
**Action**: modify (`publish` recipe, currently `Justfile:56-60`)

```make
publish: bump
  git commit -m "Bump version" modernpackage/__init__.py
  git push  # Modernpacakge clones the code from gitlab, so the updated code has to be available both on gitlab and pypi for release
  rm -fr dist/*
  uv build
  uv publish
```

Notes:
- `publish: bump` runs `bump` first (Design Decision 3).
- `git commit -m "Bump version" modernpackage/__init__.py` — path-scoped commit
  so unrelated working-tree changes are not swept in (Design Decision 3 /
  Open Risk "commit noise").
- Existing steps (`git push` and its inline comment, `rm -fr dist/*`,
  `uv build`, `uv publish`) preserved in order after the commit.
- No `sync` dependency added (Design "What We're NOT Doing").

### Verification
#### Automated
- [x] `just check` passes.
  Note: format/lint/complexity/typecheck/test (130 passed, 98% coverage) all
  green; the only failing step is `audit`, on the pre-existing `mcp`
  CVE-2026-59950 unrelated to this change (publish adds no lint/format/type
  surface), same as Phases 1–2.

#### Manual
- [x] Dependency + commit wiring present:
  `just --show publish | grep -q '^publish: bump' && just --show publish | grep -q 'git commit -m "Bump version" modernpackage/__init__.py'; echo "exit=$?"`
  → prints `exit=0`.
- [x] Publish order preserved (commit before push, build/publish after):
  `just --show publish` → body lines read, in order: `git commit ... modernpackage/__init__.py`,
  `git push ...`, `rm -fr dist/*`, `uv build`, `uv publish`.
- [x] Bump+commit prefix behaves in a throwaway clone (does **not** run
  `git push`/`uv build`/`uv publish` — avoids a real release):

  ```bash
  tmp=$(mktemp -d)
  git clone "$(pwd)" "$tmp/pub_check"
  cd "$tmp/pub_check"
  git config user.email e2e@example.com && git config user.name e2e
  before=$(sed -n "s/^__version__ = '\(.*\)'/\1/p" modernpackage/__init__.py)
  just bump
  git commit -m "Bump version" modernpackage/__init__.py
  # exactly one file in the last commit:
  test "$(git log -1 --name-only --format=)" = "modernpackage/__init__.py" && echo "single-file OK"
  # committed version is incremented:
  after=$(git show HEAD:modernpackage/__init__.py | sed -n "s/^__version__ = '\(.*\)'/\1/p")
  echo "before=$before after=$after"
  cd - && rm -rf "$tmp"
  ```
  → prints `single-file OK` and an `after` whose patch is `before` patch + 1.
  Verified: `single-file OK`, `before=0.0.9 after=0.0.10`. (Adapted: `git clone`
  copies committed state only and the Phase 1 `bump` + Phase 3 `publish` recipes
  are still uncommitted, so the Justfile was temp-committed, the clone run, then
  `git reset --soft HEAD~1` restored the uncommitted working-tree state — same
  dance as Phases 1–2.)

---

## Testing Checkpoints

- **After Phase 1**: `just bump` increments only the patch of `__version__`;
  double-bump keeps incrementing; `just check` green. (Revert the file with
  `git checkout modernpackage/__init__.py` after each manual bump.)
- **After Phase 2**: `just test-e2e -k test_just_bump_increments_patch` passes;
  breaking the recipe makes it fail. Phase 1 is regression-guarded.
- **After Phase 3**: `publish` depends on `bump` and commits the scoped version
  file before pushing; verified via a throwaway-clone prefix run without a real
  publish. Phases 1–2 remain independently valuable if Phase 3 is deferred.

## Notes / Deviations

- **Line-number drift**: design cites `Justfile:67` for the reset sed; the live
  file has it at `Justfile:70` and `publish` at `Justfile:56-60`. This plan uses
  the live numbers; the recipes are unambiguous by name.
- **macOS `sed -i`** (Open Risk): Phase 1 matches the existing GNU-sed form and
  adds no Darwin branch (Design Decision 4).
- **Non-`N.N.N` versions** and **manual-bump-then-publish double bump** are
  accepted risks per `design.md` Open Risks; not guarded here.
- No Python/`main.py` changes and no touching the `0.0.1` scaffold-reset path
  (Design "What We're NOT Doing"), so no version-assertion test updates are
  required.
