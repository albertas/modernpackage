# ToDo
- [ ] Ensure code quality [cq:ensure]
  - [x] [T2] [cq:spec] Write a codebase specification under `docs/` describing the package goals, architecture and key code parts.
  - [x] [T3] [cq:aliases] Add Justfile with targets to run tests, ruff format, ruff lint, typecheck, code complexity check and all these checks combined via `check` target. Also, add dev dependencies needed for these targets. Use a Justfile consistent with this project's, e.g.:
    ```
    test *args: sync
      uv run pytest -n "$(nproc --ignore=1)" {{args}}
    format: sync
      uv run ruff format app/
    lint: sync
      uv run ruff check app/
    typecheck: sync
      uv run mypy app/
    check-format: sync
      uv run ruff format --check app/
    check-lint: sync
      uv run ruff check app/
    check-typecheck: sync
      uv run mypy app/
    check-complexity: sync
      uv run ruff check --select C901 app/ tests/
    check: check-format check-lint check-complexity check-typecheck test
    ```
  - [x] [T4] [cq:coverage] Add test-coverage measurement and reach >= 95% coverage.
  - [x] [T5] [cq:reliabletests] Ensure that tests are deterministic and fast. Use pytest-xdist to run them (with max - 1 cores available). Tests should be mocked and not rely on external API endpoints (to save time on latency), unless these tests are end-to-end.
  - [x] [T6] [cq:ruff-format] Audit `ruff format` is clean across the codebase. Run `just check-format`.
  - [ ] [cq:ruff-lint] Audit `ruff check` is clean across the codebase. Enable most of ruff linting checks. Run `just check-lint`.
  - [ ] [cq:typecheck] Audit `mypy app/` passes. Add type hints in the code where possible. Run `just check-typecheck`.
  - [ ] [cq:complexity] Audit cyclomatic complexity stays <= 8 across `app/` and `tests/`. Run `just check-complexity`.
  - [ ] [cq:check] Ensure that just check command exist, it combines all the checks from Justfile and this `check` target passes.
  - [ ] [cq:python] Ensure that latest stable python version is used.
  - [ ] [cq:versions] Ensure that latest dependency versions are used.
- [ ] Use uv for publishing package instead of hatch
- [ ] Merge Makefile and Justfiles: move Makefile capabilities to Justfile and remove Makefile.

# Done
