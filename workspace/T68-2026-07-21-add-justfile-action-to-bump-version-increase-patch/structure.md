# Structure Outline

## Approach

Add a `bump` Justfile recipe that increments the patch component of
`__version__` in `modernpackage/__init__.py` in place using POSIX shell + `sed`
(the single source of truth Hatchling reads), then wire `publish` to depend on
`bump` and commit/push the bumped file. Cover the behavior with one e2e test.
No Python code changes; `uv version` is unusable (dynamic version). See
`design.md` Decisions 1–6.

This is a small, shell-only task. "Vertical slice" here means: each phase
delivers a self-contained, independently runnable capability (a working recipe,
a passing test, a wired release flow) rather than an internal layer.

---

## Phase 1: `bump` recipe increments patch

Add a new `bump` recipe to the `Justfile` that reads the current `N.N.N`
version, computes `patch + 1`, and rewrites the `__version__` line in place.
No `sync` dependency (needs no venv). GNU-sed style, matching existing
`Justfile:70` (Decision 4).

**Files**: `Justfile`

**Key changes**:
- New recipe `bump:` (no parameters, no deps) with body:
  - `current=$(sed -n "s/^__version__ = '\(.*\)'/\1/p" modernpackage/__init__.py)`
  - `new="${current%.*}.$(( ${current##*.} + 1 ))"`
  - `sed -i "s/^__version__ = .*/__version__ = '${new}'/" modernpackage/__init__.py`
  - `@`-prefix mechanical lines to silence echo.

**Verify**:
- `git stash` any pending version change, then:
  `just bump && grep -q "__version__ = '0.0.10'" modernpackage/__init__.py`
  → exits 0 (0.0.9 → 0.0.10). Restore with `git checkout modernpackage/__init__.py`.
- Idempotency of increment: run on a scratch copy —
  `printf "__version__ = '1.2.3'\n" > /tmp/v.py` is not the target, so instead
  assert double-bump on the real file: `just bump && just bump &&
  grep -q "__version__ = '0.0.11'" modernpackage/__init__.py`, then
  `git checkout modernpackage/__init__.py`.
- Only the version line changes: `just bump &&
  git diff --numstat modernpackage/__init__.py` shows `1 1` (one line added,
  one removed); `git checkout modernpackage/__init__.py` after.
- `just check` still passes (bump is shell, no lint/type surface — Design
  "Verification").

---

## Phase 2: e2e test locks bump behavior

Add an e2e test that runs `just bump` against a scaffolded/cloned copy and
asserts the patch incremented, mirroring `tests/test_e2e.py:188`. This gives
Phase 1 an automated regression guard (Decision 6).

**Files**: `tests/test_e2e.py`

**Key changes**:
- New `@pytest.mark.e2e def test_just_bump_increments_patch(tmp_path: Path) -> None:`
  - Skip guard on `REQUIRED_TOOLS` (`git`, `just`, `uv`) as sibling tests do.
  - Clone `REPO_ROOT` into `tmp_path` (reusing the `_run` helper, no `just init`
    needed — bump operates on `modernpackage/__init__.py` directly).
  - Read starting version from `modernpackage/__init__.py`, run
    `_run(['just', 'bump'], cwd=destination)`, assert `returncode == 0`.
  - Parse post-bump `__version__` and assert patch == start_patch + 1, and
    major/minor unchanged.

**Key type signatures**:
- `test_just_bump_increments_patch(tmp_path: Path) -> None` — new test.
- Reuse existing `_run(command: list[str], cwd: Path, env=None) ->
  subprocess.CompletedProcess[str]`.

**Verify**:
- `just test-e2e -k test_just_bump_increments_patch` passes (exit 0).
- Regression check: temporarily break the `bump` recipe (e.g. change `+ 1` to
  `+ 2`) and confirm the test fails; revert.

---

## Phase 3: `publish` bumps, commits, and pushes the new version

Wire `publish` to depend on `bump`, then commit only
`modernpackage/__init__.py` and push so GitLab carries the released version
(Decision 3, `Justfile:57` requirement). Preserve existing publish steps.

**Files**: `Justfile`

**Key changes**:
- Change `publish:` → `publish: bump`.
- Prepend to the recipe body, before `git push`:
  - `git commit -m "Bump version" modernpackage/__init__.py` (scoped to the one
    path to avoid sweeping unrelated working changes — Decision 3 / Open Risk).
- Keep existing order after commit: `git push` → `rm -fr dist/*` →
  `uv build` → `uv publish`.

**Verify** (must avoid a real publish — do not run `uv publish` unattended):
- Recipe wiring: `just --show publish` output lists `bump` as a dependency and
  the body contains `git commit` scoped to `modernpackage/__init__.py`.
- Dry-run of the mutating prefix in a throwaway clone:
  clone `REPO_ROOT` into a temp dir, run only the bump+commit prefix
  (`just bump` then `git commit -m x modernpackage/__init__.py`), and assert
  `git log -1 --name-only` shows exactly `modernpackage/__init__.py` and the
  committed version is incremented. (Full `just publish` is not run because it
  pushes and uploads to PyPI.)
- `just check` still passes.

---

## Testing Checkpoints

- **After Phase 1**: `just bump` increments only the patch of `__version__` in
  `modernpackage/__init__.py`; double-bump keeps incrementing; `just check`
  green. (Revert file after each manual bump.)
- **After Phase 2**: `just test-e2e -k test_just_bump_increments_patch` passes;
  breaking the recipe makes it fail. Phase 1 is now regression-guarded.
- **After Phase 3**: `publish` depends on `bump` and commits the scoped version
  file before pushing; verified without a real publish via a throwaway-clone
  prefix run. Phases 1–2 remain independently valuable if Phase 3 is deferred.

## Notes / Deviations

- **Not vertically sliceable in the classic multi-layer sense**: there is no
  DB/service/API/UI stack here — the deliverable is Justfile recipes plus one
  test. Phases are sliced by independent runnable capability instead, per design
  guidance.
- **macOS `sed -i` portability** (Open Risk): Phase 1 intentionally matches the
  existing GNU-sed form at `Justfile:70` and does not add a Darwin branch.
- **Non-`N.N.N` versions** and **double-bump** are accepted risks per `design.md`
  Open Risks; not handled in these phases.
