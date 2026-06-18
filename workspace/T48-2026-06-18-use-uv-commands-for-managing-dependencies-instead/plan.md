# Implementation Plan

## Overview

Collapse the dual dependency-pin mechanism (`uv pip compile` requirements files
**and** `uv.lock`) into native uv: move the `test` extra to a PEP 735
`[dependency-groups].dev` table, make `sync`/`lifecycle` a single `uv sync`,
delete both `requirements*.txt`, rename `compile`→`lock`, and realign tests +
docs to the single-lockfile reality. Each phase keeps `just check` green.

All paths are relative to the repo root `/home/niekas/tools/modernpackage`.

---

## Phase 1: Native dev group + `uv sync` install path

Move the `test` extra to `[dependency-groups].dev`, switch every install site
(`sync`, `lifecycle`) to `uv sync`, regenerate `uv.lock`, and retarget the
scaffolding-strip test that asserts the old extra survives. After this the entire
install/check path runs on native uv; `requirements*.txt` still exist but are
unused (removed in Phase 2).

### Changes

#### 1. `pyproject.toml` — replace the `test` extra with a `dev` dependency group
**File**: `pyproject.toml`
**Action**: modify

Remove the `[project.optional-dependencies]` table (lines 27-37) and replace it
with a PEP 735 `[dependency-groups]` table. Members carry over verbatim,
including `vupi>=0.0.7`. `dependencies = []` (line 18) stays unchanged.

Replace:

```toml
[project.optional-dependencies]
test = [
    "ruff",
    "mypy",
    "pip-audit",
    "deadcode",
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "vupi>=0.0.7",
]
```

with:

```toml
[dependency-groups]
dev = [
    "ruff",
    "mypy",
    "pip-audit",
    "deadcode",
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "vupi>=0.0.7",
]
```

> Rationale (design decision 1): `dev` is uv's default group, installed
> automatically by a bare `uv sync` with no `--group` flag, which keeps `sync`
> a single command.

#### 2. `Justfile` — `sync` recipe to a single `uv sync`
**File**: `Justfile`
**Action**: modify

Replace the `sync` recipe body (lines 9-11):

```makefile
sync:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]
```

with:

```makefile
sync:
  @uv sync
```

#### 3. `Justfile` — `lifecycle` recipe install step
**File**: `Justfile`
**Action**: modify

Replace the two `uv pip` lines in `lifecycle` (lines 1-4), keeping the loop line
unchanged:

```makefile
lifecycle:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]
  @count=0; while uv run lifecycle --max-tasks 1 --prior-tasks "$count"; do count=$((count + 1)); done
```

with:

```makefile
lifecycle:
  @uv sync
  @count=0; while uv run lifecycle --max-tasks 1 --prior-tasks "$count"; do count=$((count + 1)); done
```

#### 4. `tests/test_main.py` — retarget the scaffolding-strip assertions
**File**: `tests/test_main.py`
**Action**: modify

In `test_strip_scaffolding_removes_project_scripts` (lines 1322-1329), the
neighbour-intact assertion references the removed table header. Update line 1327:

```python
    assert '[dependency-groups]' in pyproject  # neighbour intact
```

Keep the `'vupi'` assertion (line 1328) and the `tomllib.loads(pyproject)`
assertion (line 1329) unchanged — the `dev` group still contains `vupi` and the
file is still valid TOML.

`_seed_clone` (lines 1281-1295) copies the real `pyproject.toml` verbatim
(line 1293-1294), so it needs no edit once the source file changes — it
automatically produces the new `[dependency-groups]` shape.

#### 5. `uv.lock` — regenerate against the new group
**File**: `uv.lock`
**Action**: modify (regenerate)

Run `uv lock` to rewrite the lockfile reflecting the renamed `dev` group. Do not
hand-edit; let uv regenerate it.

### Verification
#### Automated
- [x] `cd /home/niekas/tools/modernpackage && uv lock` exits 0 (lockfile regenerates)
- [x] `uv run python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` exits 0 (valid TOML)
- [x] `just check` passes (runs check-format, check-lint, check-complexity, check-typecheck, test, audit)
- [x] `just test` passes (unit suite, including the retargeted `test_strip_scaffolding_removes_project_scripts`)

#### Manual
- [x] `cd /home/niekas/tools/modernpackage && rm -rf .venv && just sync` exits 0 (clean native install)
- [x] `uv run ruff --version` exits 0 (dev toolchain present in the synced env)
- [x] `uv run pytest --version` exits 0 (test toolchain present)
- [x] `grep -q '^\[dependency-groups\]' pyproject.toml` exits 0 and `grep -q 'optional-dependencies' pyproject.toml` exits 1 (group replaced extra)
- [x] `uv run pip-audit --skip-editable` exits 0 (audit still resolves dev tools against the `uv sync` env — confirms Open Risk "pip-audit --skip-editable")

---

## Phase 2: Remove dual mechanism — delete requirements files, `compile`→`lock`

Delete `requirements.txt` and `requirements-dev.txt` and replace the three-command
`compile` recipe with a `lock` recipe whose body is the single `uv lock --upgrade`.
This eliminates the now-orphaned second pin mechanism. The private `gitlab` uv
index and `uv build`/`uv publish` are untouched.

### Changes

#### 1. Delete the requirements files
**Files**: `requirements.txt`, `requirements-dev.txt`
**Action**: delete

```bash
git rm requirements.txt requirements-dev.txt
```

(Use `git rm` so the deletion is staged; fall back to `rm` if not tracking yet.)

#### 2. `Justfile` — rename `compile` to `lock`
**File**: `Justfile`
**Action**: modify

Replace the `compile` recipe (lines 75-78):

```makefile
compile:
  uv pip compile -U -q pyproject.toml -o requirements.txt
  uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
  uv lock --upgrade
```

with:

```makefile
lock:
  uv lock --upgrade
```

### Verification
#### Automated
- [x] `cd /home/niekas/tools/modernpackage && just lock` exits 0 (recipe renamed, single command runs)
- [x] `just check` passes (install path unaffected by recipe rename)

#### Manual
- [x] `test ! -e requirements.txt && test ! -e requirements-dev.txt` exits 0 (both files gone)
- [x] After `just lock`, `git status --porcelain` lists only `uv.lock` as modified (no requirements files regenerated)
- [x] `grep -rn --exclude-dir=.venv --exclude-dir=.git -e 'uv pip' -e 'requirements-dev' -e 'just compile' Justfile` exits 1 (no stale references in recipes)
- [x] `grep -q '^lock:' Justfile` exits 0 and `grep -q '^compile:' Justfile` exits 1 (recipe renamed)

---

## Phase 3: Doc + drift realignment

Rewrite the dependency-workflow prose to the single-lockfile / `uv sync` /
`uv lock` story, fix the stale `vupi>=0.0.6`→`>=0.0.7`, and correct the e2e
docstring wording that already said "uv sync" (now literally true). Scope limited
to the dependency-workflow sections the research cites — no behavioral test or
adjacent-prose changes.

### Changes

#### 1. `README.md` — Development command list
**File**: `README.md`
**Action**: modify

Replace lines 272-273:

```markdown
- `just compile` - bump and freeze dependency versions in requirements*.txt files.
- `just sync` - upgrade installed dependencies in Virtual Environment (executed after `just compile`).
```

with:

```markdown
- `just lock` - refresh `uv.lock` to the latest resolvable dependency versions.
- `just sync` - create the virtual environment and install the locked dev group + editable project via `uv sync`.
```

> Note: the `README.md:290`/`294`/`300` "make" Feature-request lines are
> pre-existing stale text outside the dependency-workflow scope; leave them
> untouched (design: surgical changes).

#### 2. `docs/overview.md` — workflow + implementation-detail prose
**File**: `docs/overview.md`
**Action**: modify

Line 36 — replace:

```markdown
- **`just compile`** — regenerate and upgrade all dependency artifacts: `requirements.txt`, `requirements-dev.txt`, and `uv.lock` to the latest versions available.
```

with:

```markdown
- **`just lock`** — refresh `uv.lock` to the latest resolvable dependency versions via `uv lock --upgrade`.
```

Line 51 — replace:

```markdown
`Justfile` recipes depend on synced dependencies (dev and test extras) via the `just sync` prerequisite.
```

with:

```markdown
`Justfile` recipes depend on a synced environment (the locked `dev` group + editable project) via the `just sync` prerequisite, which runs `uv sync`.
```

Line 67 — replace:

```markdown
- **Dependency compilation workflow**: `just compile` regenerates all three dependency artifacts in lockstep (`requirements.txt`, `requirements-dev.txt`, `uv.lock`) to ensure they always agree on shared package versions and are upgraded to the latest versions available in the GitLab index.
```

with:

```markdown
- **Dependency locking workflow**: `just lock` runs `uv lock --upgrade` to refresh the single `uv.lock` source of truth to the latest versions available in the GitLab index; `uv sync` installs from it.
```

#### 3. `docs/architecture.md` — locking section + tooling prose
**File**: `docs/architecture.md`
**Action**: modify

Replace the "Dependency Compilation & Locking" block (lines 1210-1222) with a
single-lockfile description:

```markdown
### Dependency Locking

The project uses uv's native lockfile as the single source of truth for
dependency pins:

- **`uv.lock`**: generated via `uv lock --upgrade` to pin all transitive
  dependencies (runtime and the `dev` group).

The `Justfile` defines a `lock` recipe whose body is `uv lock --upgrade`.
`uv sync` installs the project and the `dev` group directly from `uv.lock`. The
lock recipe resolves against the private GitLab uv index configured in
`pyproject.toml`, which may lag behind PyPI; the resolved versions are capped by
what that index serves.
```

Line 1230 — replace `optional test dependencies` with `the `dev` dependency
group`:

```markdown
- **`[project]`**: package metadata, entry points (`modernpackage` and `mp`); the `dev` dependency group is declared under `[dependency-groups]`
```

Line 1261-1262 — replace the `sync`/`compile` bullets:

```markdown
- **`sync`**: installs the project and locked `dev` group from `uv.lock` via `uv sync` (required by most recipes as a prerequisite)
- **`lock`**: refreshes `uv.lock` to the latest resolvable versions via `uv lock --upgrade`
```

Line 1275 — replace:

```markdown
All tools read their configuration from `pyproject.toml`. The Justfile delegates to them via `uv run`, which manages the virtual environment and dependency versions (pinned in `uv.lock`).
```

#### 4. `docs/specification.md` — build/deps + repo-structure prose
**File**: `docs/specification.md`
**Action**: modify

Line 89 — replace (note stale `vupi>=0.0.6` → `vupi>=0.0.7` and group rename):

```markdown
- **Dev dependency group** (`[dependency-groups].dev`): ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi>=0.0.7.
```

Line 91 — replace:

```markdown
- **Dependency pinning**: `just lock` runs `uv lock --upgrade` to refresh `uv.lock`, the single lockfile (runtime deps are empty).
```

Lines 105 + 108 (Justfile command-hub bullets) — replace the `sync` description
and the `compile` reference:

```markdown
  - `sync`: installs the project + locked `dev` group from `uv.lock` via `uv sync` (prerequisite for recipes that need the editable install).
```

```markdown
  - Other targets: `publish`, `lock`, `init package_name="modernpackage"`.
```

(Also update line 108's `all depend on `sync` except `publish`, `compile`, and
`init`` to `... except `publish`, `lock`, and `init``.)

Lines 137-139 (Dependencies repo-structure list) — replace the three-artifact
list:

```markdown
- **Dependencies**:
  - `uv.lock` — single lockfile pinning runtime and `dev`-group dependencies.
```

#### 5. `docs/invocation.md` — e2e network note
**File**: `docs/invocation.md`
**Action**: modify

Lines 388-392 already say `uv sync` (now literally accurate). No change is
required for correctness, but confirm the wording still matches the real recipe.
Leave the prose as-is unless the grep verification below flags a stale term.

#### 6. `tests/test_e2e.py` — module docstring
**File**: `tests/test_e2e.py`
**Action**: no change (confirm only)

The module docstring (lines 13-15) already says the inner `just check` runs
"a full `uv sync`" — now literally true. No behavioral change. Confirm the e2e
assertions at lines 97-117 still hold: they assert `[project.scripts]` removal,
license edits, and the version stub — none reference the dependency table, so
they remain valid.

### Verification
#### Automated
- [x] `just check` passes (docs-only edits do not affect code gates)

#### Manual
- [x] `grep -rn --exclude-dir=.venv --exclude-dir=.git -e 'uv pip compile' -e 'requirements-dev' -e 'vupi>=0.0.6' -e 'optional-dependencies' .` exits 1 (no stale references anywhere)
- [x] `grep -rn --exclude-dir=.venv --exclude-dir=.git -e 'just compile' -e 'requirements\.txt' .` exits 1 (no stale `compile`/requirements references in docs or code)
- [x] `grep -q 'vupi>=0.0.7' docs/specification.md` exits 0 (stale version fixed)
- [x] `grep -q 'just lock' README.md` exits 0 and `grep -q 'just lock' docs/overview.md` exits 0 (recipe renamed in docs)
- [ ] `just test-e2e` is green when network to the GitLab index is available; when offline it fails at `uv sync` as before — verify the docstring wording, not green status (see Notes / Risks)

---

## Testing Checkpoints

- **After Phase 1**: `[dependency-groups].dev` is the only dev-dep table; a clean
  `rm -rf .venv && just sync` installs the toolchain + editable project; `just
  check` and `just test` pass; `pyproject.toml` is valid TOML. `requirements*.txt`
  may still exist but are unreferenced by recipes.
- **After Phase 2**: no `requirements*.txt` on disk; `just lock` regenerates only
  `uv.lock`; no `uv pip` / requirements references remain in `Justfile`;
  `just check` passes.
- **After Phase 3**: docs/README/e2e-docstring describe `uv sync`/`uv lock` and a
  single lockfile; no stale `vupi>=0.0.6` or `uv pip compile`/`optional-
  dependencies` references; `just check` passes; `just test-e2e` green when
  network to the GitLab index is available.

## Notes / Risks

- **e2e network**: `just test-e2e` runs a real `uv sync` against the private
  GitLab index; offline runners fail at sync (behavior unchanged). When offline,
  verify wording, not green status.
- **`pip-audit --skip-editable`**: the `audit` recipe is unchanged; Phase 1
  manual verification confirms it still resolves the dev tools against the env
  `uv sync` produces.
- **CI**: `.gitlab-ci.yml` and `.github/workflows/check-modernpackage-on-python314.yml`
  call `just sync`/`just check` only — no edits needed; they validate Phase 1-2
  automatically on push (design decision 5).
- **uv-version assumption**: `[dependency-groups]` requires a reasonably recent
  uv; CI installs uv latest via pip, so this is fine.
- **Non-vertical Phase 3**: the dependency prose mixes both mechanisms across
  README + four docs, so it is swept once after the mechanical changes land
  rather than touching each file twice (structure: Notes / Risks).
- **Resolved assumption — `docs/invocation.md` / `tests/test_e2e.py`**: both
  already say "uv sync"; no edit is required beyond confirming via grep that no
  stale term remains. Left as-is per surgical-change guidance.
