# ToDo

- [ ] [V5] Abort early with a specific remediation hint when any precondition fails
- [ ] [V6] Add a --dry-run flag that previews what would be created and renamed without touching disk
- [ ] [V6] Print a post-init summary with the created path, package name, and reset version
- [ ] [V6] Print the next commands to run (cd <name> && just check) after a successful run
- [ ] [V7] Bundle the template inside the published wheel
- [ ] [V7] Cache the last successful clone for reuse
- [ ] [V8] Add a --ref <tag> flag that pins scaffolding to a specific template ref
- [ ] [V8] Make modernpackage --version report the template and tooling versions it will produce
- [ ] [V8] Warn when the installed CLI is older than the latest published release
- [ ] Remove scaffolding/initialization related code programatically from the resulting project 

# Done
- [x] [T41] [V5] Print a concise preflight checklist of all environment checks
- [x] [T40] [V5] Check that the GitHub template remote is reachable before cloning
- [x] [T39] [V5] Refuse to proceed when the target directory already exists
- [x] [T38] [V5] Verify git, just, and uv are on PATH before scaffolding
- [x] [T37] [V4] Define a precedence order for metadata sources (CLI flags > env vars > git config > config file)
- [x] [T36] [V4] Populate pyproject.toml author, description, license, and repository URL during init
- [x] [T35] [V4] Support a per-user config file supplying default metadata values
- [x] [T34] [V4] Read author name and email from the user's git config (user.name / user.email)
- [x] [T33] [V4] Read author metadata defaults from environment variables
- [x] [T32] [V4] Add CLI flags for author name, email, description, license, and repository URL
- [x] [T31] [V3] Return a precise explanation of why a package name was refused
- [x] [T30] [V3] Reject names that collide with Python standard-library module names
- [x] [T29] [V3] Normalize an accepted distribution name into an import-safe module name
- [x] [T28] [V3] Relax name validation to accept valid PEP 508 / PyPI distribution names including hyphens and underscores
- [x] [T27] [V2] Add an e2e test that scaffolds a package and asserts just check passes
- [x] [T26] [V2] Exit non-zero when just check fails in the generated package
- [x] [T25] [V2] Report to the user whether the post-scaffold just check passed or failed
- [x] [T24] [V2] Run just check inside the freshly created package
- [x] [T21] [V1] Detect when just is not installed and print an actionable message
- [x] [T20] [V1] Map common git clone failures to human-readable, actionable messages (e.g. repository unreachable — check your network)
- [x] [T19] [V1] Exit with a non-zero status code whenever a scaffolding step fails
- [x] [T18] [V1] Surface the captured stderr to the user when a step fails
- [x] [T17] [V1] Capture stderr from each subprocess call instead of discarding it
- [x] [T16] [V1] Check the return code of the just init subprocess and treat a non-zero code as a failure
- [x] [T15] [V1] Check the return code of the git clone subprocess and treat a non-zero code as a failure
- [x] [T14] Merge Makefile and Justfiles: move Makefile capabilities to Justfile and remove Makefile.
- [x] [T13] Use uv for publishing package instead of hatch
- [x] Ensure code quality [cq:ensure]
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
  - [x] [T7] [cq:ruff-lint] Audit `ruff check` is clean across the codebase. Enable most of ruff linting checks. Run `just check-lint`.
  - [x] [T8] [cq:typecheck] Audit `mypy app/` passes. Add type hints in the code where possible. Run `just check-typecheck`.
  - [x] [T9] [cq:complexity] Audit cyclomatic complexity stays <= 8 across `app/` and `tests/`. Run `just check-complexity`.
  - [x] [T10] [cq:check] Ensure that just check command exist, it combines all the checks from Justfile and this `check` target passes.
  - [x] [T11] [cq:python] Ensure that latest stable python version is used.
  - [x] [T12] [cq:versions] Ensure that latest dependency versions are used.
