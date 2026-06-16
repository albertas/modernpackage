# Plan

## Phase 1: Enforce McCabe complexity threshold of 8

### Background
- `just check-complexity` already exists and runs
  `uv run ruff check --select C901 modernpackage tests`.
- Ruff's `C901` rule reports a function only when its cyclomatic complexity
  *exceeds* `tool.ruff.lint.mccabe.max-complexity`.
- `pyproject.toml` currently has **no** `[tool.ruff.lint.mccabe]` section, so
  the threshold is Ruff's default of 10 — meaning "<= 8" is not enforced.
- The current code (`modernpackage/main.py`, `tests/test_main.py`) is well
  below complexity 8, so no source refactoring is expected.

### Implementation
1. Add the following section to `pyproject.toml` (placed with the other
   `[tool.ruff.lint.*]` sections):
   ```toml
   [tool.ruff.lint.mccabe]
   max-complexity = 8
   ```
   This makes `C901` fail on any function with cyclomatic complexity > 8, i.e.
   it enforces "stays <= 8".

### Verification
- [x] Run `just check-complexity` → must print `All checks passed!` and exit 0.
- [x] Run `just check` to confirm the new config does not break the combined
  format/lint/complexity/typecheck/test gate.
- [x] (Confidence check, already validated) Temporarily verifying with
  `max-complexity = 8` set shows all C901 checks pass on the current codebase.

### Notes
- The ticket text says `app/` and `tests/`, but this project's package
  directory is `modernpackage/` (the existing Justfile recipes from earlier
  tasks already target `modernpackage tests`). No path change is needed; the
  `app/` wording is generic boilerplate carried over from the backlog template.
