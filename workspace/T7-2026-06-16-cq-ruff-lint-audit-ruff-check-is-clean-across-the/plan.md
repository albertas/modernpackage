# Plan

## Phase 1: Clean ruff lint configuration and audit

### Current state
- `pyproject.toml` already enables most ruff lint rules via
  `[tool.ruff.lint] select = ["ALL"]`.
- `uv run ruff check modernpackage tests` reports `All checks passed!` for the
  source (`modernpackage/main.py`, `modernpackage/__init__.py`) and tests.
- However, ruff emits a warning:
  `The following rules have been removed and ignoring them has no effect: ANN101`.
  `ANN101` (annotate `self`) was removed in newer ruff versions, so leaving it
  in the `ignore` list produces noise on every `just check-lint` run.

### Changes
1. In `pyproject.toml` under `[tool.ruff.lint]`, remove the stale
   `"ANN101", # deprecated requirement to annotate self` entry from the
   `ignore` list. Leave the other intentional ignores untouched
   (`D203`, `D213`, `COM812`, `ISC001` — these are ruff-recommended
   formatter-conflict / opt-out rules, not removed rules).
   → verify: `grep ANN101 pyproject.toml` returns nothing. ✅

### Verification
- [x] Run `just check-lint`.
  → verify: output ends with `All checks passed!` and no longer contains the
    `rules have been removed` warning. ✅
- [x] Run `just check` to confirm the broader gate (format, lint, complexity,
  typecheck, tests) is unaffected.
  → verify: all sub-targets pass. ✅

### Notes
- The codebase is intentionally tiny (~136 lines across source + tests), so no
  per-file ignores beyond the existing `tests/*` allowance (`S101`, `D`) are
  needed. If any new lint error surfaces after the config change, fix the code
  rather than widening `ignore`, keeping with "enable most checks".
