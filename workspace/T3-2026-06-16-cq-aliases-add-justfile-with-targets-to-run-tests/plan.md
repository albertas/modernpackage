# Plan

## Phase 1: Add code-quality targets to the Justfile

### Context (already verified)
- The repo already has a `Justfile` containing only a `lifecycle` target, which
  syncs the env with `uv pip sync requirements-dev.txt` + `uv pip install -e .[test]`.
- The `Makefile` already defines the equivalent recipes to mirror: `test`,
  `lint` (`ruff check`), `format` (`ruff format`), `mypy`, and a combined
  `check`. Source/test dirs are `modernpackage` and `tests`.
- All needed dev tools are **already** declared:
  - `pyproject.toml` `[project.optional-dependencies].test`: `ruff`, `mypy`,
    `pytest`, `pytest-cov`, `deadcode`, `pip-audit`, `hatch`.
  - `requirements-dev.txt` pins them (`ruff==0.15.17`, `mypy==2.1.0`,
    `pytest==9.1.0`, etc.).
  - => No new dependency is expected to be required; confirm during
    implementation and only add one if a target needs a tool that is missing.
- Complexity check uses ruff's McCabe rule `C901` (`ruff check --select C901`).
- `just 1.45.0` is installed; recipes use `uv run <tool>`.

### Steps
1. Add a `sync` helper recipe to the `Justfile` consistent with the existing
   `lifecycle` target's env setup (`uv pip sync requirements-dev.txt` +
   `uv pip install -e .[test]`), so quality targets can depend on it.
   → verify: `just sync` completes without error. ✓ DONE
2. Add the following recipes, each depending on `sync`, targeting
   `modernpackage tests` (match the Makefile's scope) and invoking tools via
   `uv run`:
   - `test *args` → `uv run pytest {{args}}`
   - `format` → `uv run ruff format modernpackage tests`
   - `lint` → `uv run ruff check modernpackage tests`
   - `typecheck` → `uv run mypy modernpackage tests`
   - `check-format` → `uv run ruff format --check modernpackage tests`
   - `check-lint` → `uv run ruff check modernpackage tests`
   - `check-complexity` → `uv run ruff check --select C901 modernpackage tests`
   - `check-typecheck` → `uv run mypy modernpackage tests`
   - `check` → depends on `check-format check-lint check-complexity check-typecheck test`
   → verify: `just --list` shows all targets; `just check` runs end-to-end. ✓ DONE
3. Confirm dev dependencies: verify every tool the targets call already resolves
   in the synced env. If any is missing, add it to the `test` extra in
   `pyproject.toml` and re-pin `requirements-dev.txt`; otherwise leave deps
   unchanged and note in the implementation that they were already present.
   → verify: each individual target runs the tool successfully. ✓ DONE — all tools
     (ruff, mypy, pytest) already present in synced env; no dep changes needed.
4. Run `just check` to confirm the full combined pipeline passes (or surfaces
   only pre-existing project issues, not Justfile errors).
   → verify: targets execute; no "recipe/command not found" errors. ✓ DONE —
     `check-format` reports a pre-existing formatting issue in `modernpackage/main.py`
     (would reformat); all other targets pass. No Justfile errors.

### Notes / decisions
- Keep the existing `lifecycle` target untouched (surgical change).
- Mirror the `Makefile`'s `modernpackage tests` path scope rather than the
  generic `app/` in the ticket's illustrative example, since this repo's source
  package is `modernpackage`.
