# Design Discussion

## Current State

The project tracks dependencies across four artifacts that must stay mutually
consistent:

- **Declarations** — `pyproject.toml`. Runtime `dependencies = []`
  (`pyproject.toml:18`). A single `test` optional group lists 9 packages
  (`pyproject.toml:27-38`); only `vupi>=0.0.6` carries a constraint
  (`pyproject.toml:37`) — everything else (`hatch`, `ruff`, `mypy`,
  `pip-audit`, `deadcode`, `pytest`, `pytest-cov`, `pytest-xdist`) is unpinned.
  Build-system `requires = ["hatchling"]` is unpinned (`pyproject.toml:47`).
- **`requirements.txt`** — compiled from runtime deps; effectively empty because
  `dependencies = []` (header only, `requirements.txt:1-2`).
- **`requirements-dev.txt`** — the fully-pinned transitive closure of the `test`
  extra (~278 lines, e.g. `ruff==0.15.17`, `mypy==2.1.0`, `vupi==0.0.7`).
- **`uv.lock`** — uv-native lock, `version = 1` / `revision = 3`, 102 packages
  (`uv.lock:1-2`).

Generation paths:

- `make compile` regenerates the two requirements files with `uv pip compile -U`
  (upgrade-to-latest) — runtime to `requirements.txt`, `--all-extras` to
  `requirements-dev.txt` (`Makefile:53-55`).
- **`uv.lock` has no regeneration recipe.** Neither `Makefile` nor `Justfile`
  runs `uv lock`. `Makefile:7` runs `uv sync --group dev`, but no `dev` group is
  declared (only the `test` extra) — a latent mismatch (research "Open Areas").
- Sync installs from `requirements-dev.txt` + editable extras
  (`Justfile:6-8`, `Makefile:49-51`). CI builds `make .venv` then `make check`
  (`.gitlab-ci.yml:13-18`).

Resolution constraints:

- `requires-python = ">= 3.14"` (`pyproject.toml:8`); mypy/`uv venv` pinned to
  3.14 (`pyproject.toml:84`, `Makefile:18`). `uv.lock` splits resolution markers
  on the 3.15 boundary (`uv.lock:3-7`). Python version is owned by T11 (done).
- All locked packages resolve from a single private GitLab uv index
  (`pyproject.toml:98-100`); wheel download URLs still point at PyPI.

Two divergent check gates: Makefile `check` = `test lint mypy audit deadcode`
(`Makefile:10`); Justfile `check` = `check-format check-lint check-complexity
check-typecheck test` (`Justfile:37`) — the Justfile omits `audit`/`deadcode`.

## Desired End State

All four artifacts resolve to the latest stable upstream releases and remain
mutually consistent:

- `requirements.txt` / `requirements-dev.txt` recompiled to latest pins.
- `uv.lock` re-locked to the same latest versions.
- `pyproject.toml` declarations reflect "latest" where a constraint exists
  (the `vupi` floor).

Verification:

1. `just check` passes (format, lint, complexity, typecheck, test).
2. `make check` passes (adds `audit` + `deadcode`) — this is what CI runs, so it
   is the binding gate (`.gitlab-ci.yml:18`).
3. `git diff` on `requirements-dev.txt` and `uv.lock` shows version bumps and the
   two files agree on every shared package version.
4. `uv pip compile`/`uv lock` re-run produces no further changes (idempotent).

## Patterns to Follow

- **Upgrade via `uv pip compile -U`** — the existing `compile` recipe already
  encodes the bump-and-freeze flow (`Makefile:53-55`); reuse it rather than
  hand-editing pins.
- **Re-lock via `uv lock --upgrade`** — uv's native command for `uv.lock`,
  mirroring how `compile` upgrades the requirements files. (No recipe exists
  yet; see Design Decisions.)
- **Unpinned declarations, frozen pins downstream** — the project's pinning
  philosophy keeps `pyproject.toml` constraint-light and freezes concrete
  versions into `requirements-dev.txt` / `uv.lock` (research "Cross-Cutting
  Observations"). Preserve this.
- **Configuration-as-code** — tool settings live in `pyproject.toml`; recipes
  delegate via `uv run` (`docs/overview.md:57`). Any recipe change stays in this
  style.
- **Pattern to NOT follow blindly**: the Justfile `check` omits `audit`/`deadcode`
  (`Justfile:37`). Do not treat a green `just check` as sufficient — also run
  `make check` so upgrade-introduced vulnerabilities/dead code are caught
  (CI uses the Makefile path).
- **Do NOT add a `dev` group** to fix the `Makefile:7` mismatch here — that is
  out of scope (see What We're NOT Doing).

## Design Decisions

1. **Update mechanism — `make compile` + `uv lock --upgrade`**: regenerate the
   requirements files with the existing `compile` recipe and re-lock `uv.lock`
   with `uv lock --upgrade`. Driving updates through tooling (not manual pin
   edits) guarantees a consistent transitive closure.
2. **Encode the lock regeneration in a recipe**: add a `uv lock --upgrade` step
   so `uv.lock`, `requirements.txt`, and `requirements-dev.txt` are bumped
   together. Chosen because the task explicitly requires the three files stay
   "mutually consistent" and research found no recipe keeps the lock current.
   Add it to the `compile` recipe in **both** `Makefile` and `Justfile` (Justfile
   currently has no `compile` recipe — add one) to match the dual-system layout.
   Judgment call: this is a minimal, additive change directly serving the
   consistency requirement, not speculative refactoring.
3. **Bump the `vupi` floor to the latest stable minor**: `vupi` is the only
   declaration with a constraint (`pyproject.toml:37`); raising `>=0.0.6` to the
   current latest release keeps the *declaration* "latest" per the task wording,
   while all other declarations remain intentionally unpinned. Judgment call —
   if the bump causes resolution/test failures, revert to `>=0.0.6` and rely on
   the compiled pin alone.
4. **Leave runtime `dependencies = []` and build `requires` unpinned**: no
   runtime deps exist; hatchling stays unpinned per the established philosophy.
   The compiled closure and lock capture the concrete hatchling version.
5. **Binding verification = `make check`**: because CI runs `make check`
   (`.gitlab-ci.yml:18`) and it includes `audit`/`deadcode`, treat it as the
   acceptance gate; run `just check` too for parity but rely on `make check` to
   surface vulnerabilities in newly-upgraded packages.
6. **Python floor unchanged**: keep `>= 3.14` and the 3.15 resolution markers as
   T11 established; this task only moves dependency versions, not the interpreter.

## What We're NOT Doing

- Not merging `Makefile` and `Justfile` (separate backlog item,
  `docs/overview.md:66`).
- Not adding a `dev` dependency group or otherwise resolving the
  `uv sync --group dev` mismatch (`Makefile:7`) beyond what's needed to re-lock.
- Not changing the Python version, resolution markers, or the private GitLab
  index configuration.
- Not adding, removing, or re-scoping any dependency (only version movement).
- Not changing the pinning philosophy (declarations stay unpinned except `vupi`).
- Not changing `just check` to add `audit`/`deadcode` (Justfile/Makefile parity
  is the merge backlog item, not this task).

## Open Risks

- **Private index lag**: all packages resolve through the GitLab uv index
  (`pyproject.toml:98-100`). If it does not mirror the newest PyPI releases,
  "latest" will be capped at what the index serves — the result may be newer than
  today but not absolute-latest. Document the resolved versions if this happens.
- **Upgrade breakage**: bumping `ruff`/`mypy` can introduce new lint/type errors
  or formatting changes that fail `just check`. May require small in-repo fixes
  (or, per CLAUDE.md, surfacing the tradeoff). A major `ruff`/`mypy` bump is the
  most likely source of churn.
- **Audit findings**: `pip-audit` (run only in the Makefile gate) may flag a
  freshly-upgraded transitive package — must be reconciled before CI passes.
- **Lock/requirements divergence**: `make compile` and `uv lock` are separate
  resolvers; confirm they agree on shared versions after both run (idempotence
  check in Desired End State).
- **`vupi` floor bump** (Decision 3) could cascade through the lock; revert if it
  destabilizes resolution.
```

