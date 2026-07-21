# Design Discussion

## Current State

- The live version is a single string in `modernpackage/__init__.py:3`:
  `__version__ = '0.0.9'`. This is the one source of truth (research Q1).
- The build backend is Hatchling with a **dynamic** version sourced from that
  file: `pyproject.toml:24` (`dynamic = ["version"]`) and `pyproject.toml:54-55`
  (`[tool.hatch.version] path = "modernpackage/__init__.py"`). There is no
  `version = ` key under `[project]` (research Q1).
- The `publish` recipe (`Justfile:56-60`) does, in order: `git push` →
  `rm -fr dist/*` → `uv build` → `uv publish`. It has **no** `sync` dependency
  and **no** version bump — it ships whatever `__version__` currently is
  (research Q2). The inline comment on `git push` (`Justfile:57`) notes that
  modernpackage clones code from GitLab, so the updated code must be on GitLab
  *and* PyPI for a release.
- The only existing version-mutation mechanism is a raw `sed` in the `init`
  recipe (`Justfile:70`) that resets any `N.N.N` to `0.0.1`. This runs GNU-sed
  style (`sed -i -e ...`) and is **not** uname-branched, unlike the rename seds
  above it (`Justfile:64-69`) — so line 70 is effectively Linux-only today.
- `uv version --bump patch` exists but **fails** on this project: dynamic
  versions cannot be read/set by `uv version` (research Q5:
  `error: We cannot get or set dynamic project versions`).
- Python code does **not** rewrite the version file; `main.py:649`
  `_RESET_VERSION = '0.0.1'` is display-only and manually kept in sync with
  `Justfile:70` by comment convention (research Q3).
- Tests reference the version: unit tests import the live `__version__`
  (`tests/test_main.py:10,52`) and assert the reset literal `'0.0.1'` in
  scaffolding paths; e2e asserts `'0.0.1'` after real `just init`
  (`tests/test_e2e.py:188`) (research Q6).

## Desired End State

- A new Justfile recipe (`bump`) increments the **patch** component of
  `__version__` in `modernpackage/__init__.py` in place (e.g. `0.0.9` → `0.0.10`).
- The `publish` recipe runs `bump` **before** building and publishing, so every
  publish ships a new version with no manual edit.
- Because GitLab must carry the released code (`Justfile:57`), the bumped
  `__init__.py` is committed and pushed as part of `publish` so the pushed tree
  contains the new version.

**Verification:**
- `just bump` on `0.0.9` yields `__version__ = '0.0.10'` and nothing else in the
  file changes.
- Running `bump` twice yields `0.0.11` (patch keeps incrementing; major/minor
  untouched).
- `just check` still passes (no lint/format/type regressions — bump is shell,
  not Python).
- An e2e test runs `just bump` in a scaffolded copy and asserts the patch
  incremented, mirroring `tests/test_e2e.py:188`.

## Patterns to Follow

- **Edit `__init__.py` directly via sed**, exactly as the reset already does
  (`Justfile:70`). This is the single source of truth Hatchling reads; do not
  target `pyproject.toml`.
- **Chain recipes as dependencies** — `check: ...` (`Justfile:54`),
  `fix: format fix-lint` (`Justfile:52`), `e: test-e2e` (`Justfile:17`). Wire
  `publish` to depend on `bump`.
- **`@`-prefix to silence** mechanical shell lines (`Justfile:63-70`).
- **`git` lives in Justfile recipes** already (`publish` git push `Justfile:57`;
  `init` git init/add/commit `Justfile:73-75`) — committing the bump fits the
  existing style.
- **No `sync` dependency for git/build recipes** — `publish` and `init` omit it
  (research Q4). `bump` needs no venv, so it also omits `sync`.

**Patterns to NOT follow / watch:**
- Do **not** use `uv version` — it errors on dynamic versions (research Q5).
- The reset sed (`Justfile:70`) is GNU-only (no Darwin branch). Do not silently
  copy the bug; see Design Decision 4.
- Do **not** couple to `_RESET_VERSION` (`main.py:649`) — that is the
  scaffold-reset path, unrelated to release bumping.

## Design Decisions

1. **Target `__init__.py`, not `pyproject.toml`** — the version is dynamic and
   sourced from `__init__.py` (`pyproject.toml:54-55`); it is the single source
   of truth and what `sed` already edits (`Justfile:70`). Switching to a static
   `[project] version` would be a larger, out-of-scope change.

2. **Bump in pure POSIX shell + sed, not Python** — no Python API rewrites the
   version today (research Q3), and a shell recipe needs no venv/`sync`
   (consistent with `publish`). Extract current version, compute
   `patch + 1` via shell arithmetic, substitute back:
   `current=$(sed -n "s/^__version__ = '\(.*\)'/\1/p" ...)`,
   `new="${current%.*}.$(( ${current##*.} + 1 ))"`,
   then a `sed -i` substitution of the whole line.

3. **`publish: bump` runs the bump first, then commits + pushes the new version**
   — the task requires bump before build/publish, and `Justfile:57` requires the
   released code (including the new version) to be on GitLab. So the new
   `publish` order is: `bump` (dependency) → `git commit` the version file →
   `git push` → `rm -fr dist/*` → `uv build` → `uv publish`. Commit only
   `modernpackage/__init__.py` to avoid sweeping in unrelated working changes.

4. **Match the existing GNU-sed style of `Justfile:70` (no uname branch)** for
   consistency and simplicity, accepting the same Linux-targeted limitation the
   repo already has. Portability is noted under Open Risks rather than fixed
   here, to keep the change surgical (CLAUDE.md §3).

5. **Recipe name `bump`** — short, matches the terse recipe vocabulary
   (`sync`, `lock`, `fix`, `check`). Increments patch only; no arguments.

6. **Add one e2e test, no new unit test** — the logic is shell, best exercised
   by running `just bump` end-to-end (mirroring `tests/test_e2e.py:188`).
   `main.py` gains no code, so no unit-level surface changes.

## What We're NOT Doing

- Not bumping major or minor, and not adding a `major`/`minor`/`--part` option.
- Not switching to a static `[project] version` or adopting `uv version`/`hatch
  version`.
- Not creating git tags, GitHub/GitLab releases, or changelog entries.
- Not touching the scaffolding reset path (`Justfile:70`, `main.py:649`,
  `_RESET_VERSION`, the `0.0.1` stubs/tests).
- Not adding uname/Darwin branching beyond what the repo already does (unless
  Open Risk forces it).
- Not adding a `sync` dependency to `bump` or `publish`.

## Open Risks

- **sed portability**: the chosen GNU-sed form won't work as-is on macOS
  (`sed -i` needs `-i ''`). This matches the pre-existing `Justfile:70` behavior,
  so it introduces no new inconsistency — but if publishing is expected on macOS,
  a uname branch (like `Justfile:64-69`) would be needed.
- **Commit noise / dirty tree**: committing `__init__.py` inside `publish`
  assumes the file is the intended change to release. If the working tree has
  the version file staged/modified for another reason, the auto-commit could be
  surprising. Scoping the commit to just that one path mitigates this.
- **Non-`N.N.N` versions**: if `__version__` ever carries a suffix (e.g.
  `1.2.3rc1`), the `${current##*.}` arithmetic would fail. Current usage is
  always plain `N.N.N` (`__init__.py:3`), so this is acceptable but worth a
  guard if it ever changes.
- **Double-bump risk**: because `publish` depends on `bump`, invoking `bump`
  manually and then `publish` in the same session bumps twice. Documented
  behavior; acceptable for a release recipe.
