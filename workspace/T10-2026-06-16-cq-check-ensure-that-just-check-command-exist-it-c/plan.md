# Plan

## Phase 1: Verify and confirm the combined `check` target

### Current state (already verified)

The `Justfile` already defines:

```
check: check-format check-lint check-complexity check-typecheck test
```

This combines every check recipe present in the `Justfile`:

- `check-format`  → `ruff format --check modernpackage tests`
- `check-lint`    → `ruff check modernpackage tests`
- `check-complexity` → `ruff check --select C901 modernpackage tests`
- `check-typecheck` → `mypy modernpackage tests`
- `test`          → `pytest -n "$(nproc --ignore=1)"`

Running `just check` currently exits `0`:

- format: 4 files already formatted
- lint: all checks passed
- complexity (C901): all checks passed
- typecheck: no issues in 4 source files
- tests: 8 passed, 100% coverage (>= 95% required)

### Implementation

No code change is required — the target exists, aggregates all `Justfile`
checks, and passes. Scope of work is verification only:

1. Run `just check` from the repo root.
   - [x] verify: command exists (just does not report "unknown recipe") and exits `0`.
2. Confirm the `check` recipe lists every `check-*` recipe plus `test`.
   - [x] verify: read the final `check:` line in `Justfile` and cross-check against
     the set of `check-*` recipes defined above it; no check recipe is omitted.

### Notes / scope boundary

- `pip-audit` and `deadcode` are installed as dev dependencies but have no
  recipes in the `Justfile`; "all the checks from `Justfile`" refers to recipes
  that exist in the file, so they are out of scope for T10. Adding new check
  tools is tracked separately (e.g. `[cq:versions]`, audit tasks) and should not
  be introduced here per the surgical-change guideline.
- If `just check` ever fails, fix the underlying check (format/lint/types/tests)
  rather than weakening the `check` target.
