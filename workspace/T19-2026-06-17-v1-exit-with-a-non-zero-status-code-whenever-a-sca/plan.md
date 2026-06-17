# Plan

## Phase 1: Return a non-zero exit code on scaffolding failure

### Background
- The console entry points are `modernpackage = "modernpackage.main:main"` and
  `mp = "modernpackage.main:main"` (see `pyproject.toml`). The generated
  console-script wrapper calls `sys.exit(main())`, so whatever `main()` returns
  becomes the process exit code (`None` and `0` both mean success).
- `init_new_package()` already raises `RuntimeError` when `git clone` or
  `just init` returns a non-zero code (tasks T15–T18). `main()` currently
  catches that error, prints it to stderr, and falls through — returning `None`,
  i.e. exit status 0.

### Change
In `modernpackage/main.py`:
- Change `main()` to return an `int` exit code (update its signature
  `-> int` and docstring accordingly).
- On the success paths (`--version`, successful scaffold, and no args) return
  `0`.
- In the `except RuntimeError` block, after printing the error to stderr,
  return a non-zero code (`1`).

Prefer returning an exit code over calling `sys.exit(1)`: the existing test
`test_main_surfaces_stderr_on_failure` calls `main()` directly and asserts it
"must not raise", which `sys.exit(1)` (raising `SystemExit`) would violate.
Returning an int keeps all current tests passing and lets the entry-point
wrapper translate the value into the process exit status.

### Tests (in `tests/test_main.py`)
- Add a test asserting `main()` returns `1` when `init_new_package` raises
  `RuntimeError` (failure path), reusing the mocking style of
  `test_main_surfaces_stderr_on_failure`.
- Add/adjust assertions so the success paths return `0`:
  - `test_main_with_package_name` (successful scaffold) returns `0`.
  - `test_show_version` returns `0`.
  - `test_main_no_args` returns `0`.
- Confirm existing `test_main_surfaces_stderr_on_failure` still passes (still
  must not raise).

### Verify
- [x] `just check` passes (ruff format, ruff lint, complexity, mypy — note `main`
  now annotated `-> int` —, and the full test suite at >= 95% coverage).
