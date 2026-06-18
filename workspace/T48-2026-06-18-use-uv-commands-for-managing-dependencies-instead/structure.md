# Structure Outline

## Approach

Collapse the dual pin mechanism (`uv pip compile` requirements files **and**
`uv.lock`) into native uv: move the `test` extra to a PEP 735
`[dependency-groups].dev` table, make `sync` a single `uv sync`, delete both
`requirements*.txt`, rename `compile`→`lock`, and realign tests + docs to the new
reality. Each phase keeps `just check` green so partial progress stays shippable.

The "layers" for this template repo are: `pyproject.toml` declaration, `Justfile`
recipes, the lockfile/requirements artifacts, unit/e2e tests, docs/README, and CI
(which delegates to the Justfile and needs no edits). Each phase below crosses the
layers it touches and ends with `just check` passing.

---

## Phase 1: Native dev group + `uv sync` install path

Move the `test` extra to `[dependency-groups].dev`, switch every install site
(`sync`, `lifecycle`) to `uv sync`, regenerate `uv.lock`, and retarget the
scaffolding-strip tests that assert the old extra survives. After this the entire
install/check path runs on native uv; `requirements*.txt` still exist but are
unused (cleaned up in Phase 2).

**Files**: `pyproject.toml`, `Justfile`, `tests/test_main.py`, `uv.lock`

**Key changes**:
- `pyproject.toml`: remove `[project.optional-dependencies].test` (lines 27-37);
  add `[dependency-groups]` with `dev = ["ruff", "mypy", "pip-audit", "deadcode",
  "pytest", "pytest-cov", "pytest-xdist", "vupi>=0.0.7"]`. Members carry over
  verbatim. `dependencies = []` unchanged.
- `Justfile` `sync` (lines 9-11): two `uv pip` lines → single `@uv sync`.
- `Justfile` `lifecycle` (lines 1-3): replace the two `uv pip` lines with `@uv sync`.
- `tests/test_main.py` `test_strip_scaffolding_removes_project_scripts`
  (lines 1327-1328): `'[project.optional-dependencies]'` → `'[dependency-groups]'`;
  keep the `'vupi'` and `tomllib.loads(...)` assertions. `_seed_clone`
  (lines 1281-1295) copies the real `pyproject.toml`, so it needs no edit once the
  source file changes — confirm it still produces valid TOML.
- `uv.lock`: regenerate via `uv lock` to reflect the `dev` group.

**Verify**: `cd /home/niekas/tools/modernpackage && rm -rf .venv && just sync`
exits 0 and `uv run ruff --version` + `uv run pytest --version` both succeed
(dev toolchain present, project editable); `just check` passes; `just test`
green; `uv run python -c "import tomllib,pathlib;
tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` exits 0.

---

## Phase 2: Remove dual mechanism — delete requirements files, `compile`→`lock`

Delete `requirements.txt` and `requirements-dev.txt` and replace the `compile`
recipe (three commands) with a `lock` recipe whose body is the single
`uv lock --upgrade`. This eliminates the now-orphaned second pin mechanism. The
private `gitlab` uv index and `uv build`/`uv publish` are untouched.

**Files**: `requirements.txt` (delete), `requirements-dev.txt` (delete), `Justfile`

**Key changes**:
- Delete `requirements.txt`, `requirements-dev.txt`.
- `Justfile` `compile` (lines 75-78): rename recipe to `lock`; body becomes the
  single line `uv lock --upgrade` (drop both `uv pip compile` lines).

**Verify**: `just lock` exits 0 and `git status --porcelain` shows only `uv.lock`
changed (no requirements files regenerated); `test ! -e requirements.txt && test
! -e requirements-dev.txt` exits 0; `just check` still passes; `grep -rn --
exclude-dir=.venv --exclude-dir=.git -e 'uv pip' -e 'requirements\.txt' -e
'requirements-dev' -e 'just compile' .` returns no hits in code/recipes (doc hits,
if any, are cleared in Phase 3).

---

## Phase 3: Doc + drift realignment

Rewrite the dependency-workflow prose to the single-lockfile / `uv sync` /
`uv lock` story, fix the stale `vupi>=0.0.6`→`>=0.0.7`, and correct the e2e
docstring/test wording that already said "uv sync" (now literally true). Scope
limited to the dependency-workflow sections the research cites.

**Files**: `README.md` (lines ~272-273, ~290-300), `docs/overview.md` (36, 51, 67),
`docs/architecture.md` (1214-1222, 1261-1262, 1275), `docs/specification.md`
(89-92, 137-138), `docs/invocation.md` (388-392), `tests/test_e2e.py`
(module docstring lines 13-15)

**Key changes**:
- README: `just compile` description → `just lock` ("refresh `uv.lock`");
  `just sync` description → "create venv + install locked dev group + editable
  project via `uv sync`".
- docs: replace lockstep-of-three-artifacts framing with single `uv.lock`;
  `uv pip compile` → `uv lock --upgrade`; requirements-file references removed.
- `docs/specification.md:89`: `vupi>=0.0.6` → `vupi>=0.0.7`; `test` group →
  `[dependency-groups].dev`.
- `tests/test_e2e.py` docstring: keep "uv sync" wording (now accurate); no
  behavioral test change. Confirm e2e assertions at lines 97-117 still hold
  (they assert `[project.scripts]` removal + license edits, not the extra).

**Verify**: `grep -rn --exclude-dir=.venv --exclude-dir=.git -e 'uv pip compile'
-e 'requirements-dev' -e 'vupi>=0.0.6' -e 'optional-dependencies' .` returns no
hits; `just check` passes; `just test-e2e` green (network-dependent — see Risks).

---

## Testing Checkpoints

- **After Phase 1**: `[dependency-groups].dev` is the only dev-dep table; a clean
  `rm -rf .venv && just sync` installs the toolchain + editable project; `just
  check` and `just test` pass; `pyproject.toml` is valid TOML. `requirements*.txt`
  may still exist but are unreferenced by recipes.
- **After Phase 2**: no `requirements*.txt` on disk; `just lock` regenerates only
  `uv.lock`; no `uv pip` / requirements references remain in `Justfile` or code;
  `just check` passes.
- **After Phase 3**: docs/README/e2e-docstring describe `uv sync`/`uv lock` and a
  single lockfile; no stale `vupi>=0.0.6` or `uv pip compile`/`optional-
  dependencies` references; `just check` passes; `just test-e2e` green when network
  to the GitLab index is available.

## Notes / Risks

- **e2e network**: `just test-e2e` runs a real `uv sync` against the private
  GitLab index; offline runners fail at sync (behavior unchanged). Verify wording,
  not green status, when offline.
- **`pip-audit --skip-editable`**: the `audit` recipe is unchanged; confirm it
  still resolves the dev tools against the env `uv sync` produces.
- **CI**: `.gitlab-ci.yml` and the GitHub workflow call `just sync`/`just check`
  only — no edits needed; they validate Phase 1-2 automatically on push.
- This task has one unavoidably non-vertical phase (Phase 3, docs): the dependency
  prose mixes both mechanisms across five files, so it is cleanest to sweep once
  after the mechanical changes land rather than touch each file twice.
