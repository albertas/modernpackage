# Plan

## Phase 1: Verify and complete mypy type-checking

### Context

- The package code lives in `modernpackage/` (`main.py`, `__init__.py`); tests
  live in `tests/` (`test_main.py`). The task references `app/`, but this
  project's package is `modernpackage/` — the `check-typecheck` recipe already
  targets the correct paths.
- `just check-typecheck` runs `uv run mypy modernpackage tests`.
- mypy is configured in `pyproject.toml` `[tool.mypy]` with `strict = true`,
  `python_version = "3.14"`, `warn_return_any`, and `warn_unused_configs`.
- Current state: all public functions already carry parameter and return type
  annotations (`check_alpha_numeric`, `parse_args`, `init_new_package`, `main`),
  and `mypy modernpackage tests` already reports
  `Success: no issues found in 4 source files`.

### Implementation

1. Run `just check-typecheck` and read the output.
   - **Verify:** the command exits 0 and prints `Success: no issues found`.
2. If (and only if) mypy reports any errors, add the missing or corrected type
   hints at the exact locations mypy flags, preferring full annotations over
   `# type: ignore`. Keep changes surgical — touch only lines mypy complains
   about. Re-run `just check-typecheck` after each change until it is clean.
   - **Verify:** `just check-typecheck` reports no issues.
3. Confirm no regressions in the broader check suite that the change could have
   affected.
   - **Verify:** `just check` passes (format, lint, complexity, typecheck,
     tests).

### Notes / expected outcome

- Because strict mypy already passes, this task is expected to be primarily an
  audit confirmation. The acceptance criterion is `just check-typecheck`
  reporting success with no code changes required, or with the minimal
  annotations needed should any gap surface.
