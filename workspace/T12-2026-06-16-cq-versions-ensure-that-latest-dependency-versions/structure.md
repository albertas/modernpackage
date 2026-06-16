# Structure Outline

## Approach
Drive every version movement through tooling, never hand-edited pins: encode a
`uv lock --upgrade` step alongside the existing `uv pip compile -U` flow so
`uv.lock`, `requirements.txt`, and `requirements-dev.txt` bump together; raise
the lone `vupi` declaration floor; regenerate all artifacts; then reconcile any
upgrade-introduced lint/type/audit/deadcode breakage against the binding
`make check` gate.

> **Note on slicing.** This task has no DB/service/API/UI layers to cross. The
> meaningful "layers" are: recipes (Makefile + Justfile), declarations
> (`pyproject.toml`), and generated artifacts (`requirements*.txt`, `uv.lock`).
> Each phase below is the smallest increment that is independently runnable and
> verifiable; "vertical" here means "a complete, checkable step," and Phases 1–2
> stay valuable even if Phase 4 surfaces breakage.

---

## Phase 1: Encode lock regeneration in both build systems
Add `uv lock --upgrade` to the upgrade-and-freeze flow so the lock is bumped in
lockstep with the requirements files. Makefile already has `compile`; the
Justfile has none, so add one mirroring it.

**Files**: `Makefile`, `Justfile`
**Key changes**:
- `Makefile` `compile` target — append a third line:
  `uv lock --upgrade` (alongside the two existing `uv pip compile -U` lines, `Makefile:53-55`).
- `Justfile` — new recipe:
  ```
  compile:
    uv pip compile -U -q pyproject.toml -o requirements.txt
    uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
    uv lock --upgrade
  ```

**Verify**: `make compile` exits 0 and `just compile` exits 0; after each,
`git status --porcelain` shows only `requirements.txt`, `requirements-dev.txt`,
`uv.lock` as modified (no other files touched). Run
`grep -c 'uv lock --upgrade' Makefile` returns 1 and same for `Justfile`.

---

## Phase 2: Bump the `vupi` declaration floor
Raise the only constrained declaration (`vupi>=0.0.6`) to the current latest
stable minor, keeping all other `test`-extra entries intentionally unpinned.

**Files**: `pyproject.toml`
**Key changes**:
- `pyproject.toml:37` — `"vupi>=0.0.6"` → `"vupi>=<latest-stable>"` (resolve the
  latest version the GitLab index serves; e.g. the `0.0.7` already in the lock or
  newer).

**Verify**: `grep 'vupi>=' pyproject.toml` shows the new floor.
`uv pip compile -q --all-extras pyproject.toml -o -` resolves without error and
the resulting `vupi==` pin is `>=` the new floor. If resolution or later tests
fail, revert to `>=0.0.6` per design Decision 3 and record the revert.

---

## Phase 3: Regenerate all artifacts to latest pins
Run the Phase-1 recipe to recompile both requirements files and re-lock
`uv.lock` to the latest versions the private index serves, then prove
consistency and idempotence.

**Files**: `requirements.txt` (header-only, expected unchanged),
`requirements-dev.txt`, `uv.lock`
**Key changes**: regenerated pins only — no source edits.

**Verify**:
- `make compile` then re-run `make compile`; second run leaves
  `git status --porcelain` empty for the three artifacts (idempotent).
- `requirements-dev.txt` diff shows version bumps (e.g. `ruff==`, `mypy==`).
- Cross-file agreement script: for each `name==ver` in `requirements-dev.txt`,
  assert `uv.lock` lists the same `version` for that package. Concretely, a
  scripted check that parses both and exits non-zero on any shared-package
  version mismatch (design End State #3).

---

## Phase 4: Reconcile breakage and pass the binding gate
Run both check gates; fix any lint/format/type/audit/deadcode issues introduced
by upgraded `ruff`/`mypy`/`pip-audit`. `make check` is the acceptance gate (it
adds `audit`+`deadcode` and is what CI runs); `just check` is run for parity.

**Files**: potentially `modernpackage/`, `tests/` (only minimal fixes for
upgrade-introduced lint/type errors or reformatting); no recipe/scope changes.
**Key changes**: surgical fixes only — each traceable to a tool error message
from a newer tool version.

**Verify**:
- `just check` exits 0 (format, lint, complexity, typecheck, test).
- `make check` exits 0 (adds `audit`, `deadcode`) — binding gate.
- If `pip-audit` flags a freshly-upgraded transitive package, reconcile (bump
  past the advisory or document) until `make audit` exits 0.
- Final `git diff --stat` is limited to the three artifacts plus `pyproject.toml`,
  the two recipe files, and any minimal source fixes.

---

## Testing Checkpoints
- **After Phase 1**: `make compile` and `just compile` both run; only the three
  dependency artifacts change; `uv lock --upgrade` present in both build files.
- **After Phase 2**: `vupi` floor raised; extra still resolves.
- **After Phase 3**: requirements + lock regenerated, idempotent on re-run, and
  agree on every shared package version.
- **After Phase 4**: `just check` and `make check` both green; audit clean; diff
  scoped to intended files. This is the task's done state (design End State #1–4).
