# Design Discussion

## Current State

The repository already targets **Python 3.14** in every functional location.
Research confirmed there is no scattered set of contradictory versions to
reconcile — the codebase is internally consistent on 3.14. The divergences are
cosmetic, not functional:

- **Packaging metadata** (`pyproject.toml`): `requires-python = ">= 3.14"`
  (`pyproject.toml:8`), trove classifier `Programming Language :: Python :: 3.14`
  (`pyproject.toml:15`), and `[tool.mypy] python_version = "3.14"`
  (`pyproject.toml:84`). Ruff has no `target-version` and infers from
  `requires-python` (`pyproject.toml:57-58`); hatchling has no pin
  (`pyproject.toml:46-48`).
- **Env creation**: the single explicit interpreter pin is `uv venv -p 3.14`
  (`Makefile:18`). The `Justfile` has no explicit version; `uv run`/`uv pip`
  resolve from `requires-python` (`Justfile:6-37`).
- **CI**: one GitHub Actions workflow whose *contents* target 3.14
  (`python-version: "3.14"`, name "Checks modernpackage with Python3.14") but
  whose *filename* is stale: `.github/workflows/check-modernpackage-on-python311.yml`.
  GitLab CI uses `image: python:latest` (`.gitlab-ci.yml:1`), overridden in
  practice by `make .venv` → `uv venv -p 3.14`.
- **Docs**: `docs/specification.md` and `docs/architecture.md` document 3.14 in
  prose (`specification.md:74,87,92`; `architecture.md:105,116,145,177,194`).
- **Incidental non-3.14 strings**: `python3.12` appears only inside pasted
  example tracebacks (`README.md:66,68,71,73`;
  `issues/no_internet_connection_message:8-15`).
- **Scaffolder**: `make init` (`Makefile:60-75`) rewrites only the
  `modernpackage` name and the semantic version in `__init__.py`; it never
  touches Python-version strings, so all 3.14 values (and the stale `python311`
  filename) propagate verbatim into generated packages.

**Latest stable Python as of 2026-06-16 is 3.14** (3.15 is not released until
~October 2026). Therefore the repo's declared target already equals the latest
stable release — no numeric bump is required today.

## Desired End State

Every place that declares, pins, or names a Python version agrees on the latest
stable release (3.14), with no stale or contradictory references — including
file *names*, not just file contents. Concretely:

1. The GitHub Actions workflow filename matches its contents (no `python311`).
2. No functional config, doc, or CI value contradicts 3.14.
3. Example tracebacks remain untouched (they are historical illustrations, not
   version declarations).

**Verification**:
- `git grep -n 'python311'` returns nothing.
- `git grep -nE 'python[_-]?3\.1[0-3]'` returns only the example-traceback lines
  in `README.md` and `issues/` (documented exceptions), and nothing else.
- `git grep -nE '3\.14|python314'` shows all functional version references and
  the renamed workflow file agree.
- `just check` (or `make check`) still passes on the renamed workflow / config.

## Patterns to Follow

- **Single explicit interpreter pin lives in `Makefile:18`** (`uv venv -p 3.14`).
  Treat this plus `requires-python` (`pyproject.toml:8`) as the source of truth
  that all other references mirror. Match this pattern; do not introduce a second
  competing pin.
- **Declarative metadata mirrors the pin** — `requires-python`, the trove
  classifier (`pyproject.toml:15`), and mypy `python_version` (`pyproject.toml:84`)
  all state 3.14 explicitly. Keep them explicit and in lockstep.
- **Docs state the version in prose** (`docs/architecture.md:116,145`); any
  version change must update these in lockstep. They currently agree — leave as is.
- **Scaffolder rewrite mechanism** is clone-then-`sed` on `modernpackage` +
  `__init__.py` version only (`Makefile:62-68`). This is the established pattern;
  do not extend it to rewrite Python versions (see What We're NOT Doing).

**Pattern to NOT follow / the flaw to fix**: the CI workflow filename encodes a
version (`python311`) that drifted from its contents (3.14). Encoding a version
in a filename is fragile because `make init`'s `sed` rewrites never touch it.
Fix the current mismatch by renaming; do not add new version-bearing filenames.

## Design Decisions

1. **No numeric version bump** — Latest stable is 3.14, which the repo already
   targets. The task is "ensure latest stable consistently," and consistency on
   the current latest is already 3.14. Treat this as a cleanup task, not a bump.
2. **Rename the stale workflow file** to
   `.github/workflows/check-modernpackage-on-python314.yml` — its contents
   already say 3.14; the `311` in the name is pure drift and the most visible
   inconsistency. Use `git mv` to preserve history.
3. **Leave example tracebacks (`python3.12`) untouched** — they are pasted output
   illustrating a past bug report, not a declaration of the project's target.
   Rewriting them would falsify the historical record and is out of scope.
4. **Leave `.gitlab-ci.yml: image: python:latest` as is** — it is functionally
   overridden by `uv venv -p 3.14` in `make .venv`, and `python:latest` tracks
   the newest release by design, so it cannot become stale. Pinning it to a
   number would *create* a second maintenance point that drifts. Documented as a
   deliberate non-change.
5. **Do not add `target-version` to ruff** — ruff already infers from
   `requires-python` (`pyproject.toml:57-58`). Adding an explicit pin introduces
   another value to keep in sync for no behavioral gain.
6. **Decisions 1-5 are judgment calls** made without asking, per task
   instructions. The riskiest is #1, gated on the Open Risk below.

## What We're NOT Doing

- Not bumping to 3.15 or any pre-release — it is not stable as of 2026-06-16.
- Not rewriting the `python3.12` example-traceback strings.
- Not pinning `.gitlab-ci.yml` to a numeric Python version.
- Not adding `[tool.ruff] target-version`, nor any new tool-level version pin.
- Not adding a single-source-of-truth abstraction or templating layer to
  deduplicate version strings (over-engineering for ~5 well-known sites).
- Not changing the `make init` scaffolder to rewrite Python versions.
- Not touching docs prose (already consistent at 3.14).

## Open Risks

- **Latest-stable verification**: This design assumes 3.14 is the latest stable
  Python on the implementation date. Re-confirm at implementation time (e.g.
  python.org downloads). If 3.15+ has shipped, Decision #1 flips to a full bump:
  update `pyproject.toml:8,15,84`, `Makefile:18`, the workflow `python-version`
  and name, the new workflow filename, and docs prose
  (`specification.md`/`architecture.md`) in lockstep — the same sites enumerated
  in Current State become the edit list.
- **Workflow rename and branch protection**: renaming a CI workflow file changes
  the check name GitHub reports; if a required-status-check rule references the
  old name, it may need updating in repo settings (outside the codebase).
- **Generated-package inheritance**: because the scaffolder copies verbatim, the
  renamed filename and any future bump only reach new packages — already-correct
  by construction once the source repo is fixed; no per-package migration in scope.
