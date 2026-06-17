# Plan

## Phase 1: Detect missing `just` and print an actionable message

### Context

`modernpackage/main.py::init_new_package` runs two subprocesses via `Popen`:
`git clone ...` and then `just init <package_name>`. When `just` is not installed,
`Popen(['just', 'init', ...])` raises `FileNotFoundError` before `communicate()`,
which currently surfaces as an unhandled traceback rather than a friendly message.

The module already has an established failure pattern: build a helpful message,
`raise RuntimeError(message)`, and let `main()` catch `RuntimeError`, print it to
`sys.stderr`, and return exit code `1`. The new behavior should reuse this pattern so
exit-code and stderr handling stay consistent with `git clone` failures.

### Implementation

In `modernpackage/main.py`, in `init_new_package`, wrap the construction of the
`just init` subprocess so a missing executable becomes a `RuntimeError` with an
actionable message. Concretely:

- Wrap the `Popen([...'just'...])` call (the second `Popen`) in a
  `try` / `except FileNotFoundError` block.
- In the `except` branch, `raise RuntimeError(message) from error` where `message`
  is a clear, actionable string, for example:
  `"'just' command not found — install it to initialize the package. See https://github.com/casey/just#installation"`
- Keep the existing non-zero `returncode` handling for the case where `just` exists
  but `just init` fails.

This keeps the change surgical: `main()` already catches `RuntimeError`, prints it to
stderr, and returns `1`, so no change is needed there.

(Note: `git clone` could fail the same way if `git` is missing, but that is out of
scope for this task — only `just` detection is requested.)

### Testing

Add a unit test in `tests/test_main.py` mirroring the existing
`test_init_new_package_just_init_failure` style:

- Patch `modernpackage.main.Popen` so the first call (git clone) returns a mock with
  `returncode = 0` and `communicate() -> (b'', b'')`, and the second call raises
  `FileNotFoundError` (use `side_effect = [git_clone_mock, FileNotFoundError(...)]`).
- Assert `init_new_package('mypackage')` raises `RuntimeError` whose message contains
  the actionable text (e.g. `match="just"` and references installation).

Optionally add a `main()`-level test confirming exit code `1` is returned when the
`just`-missing `RuntimeError` propagates (the existing `test_main_returns_one_on_failure`
already covers the generic `RuntimeError -> 1` path, so this is optional).

### Verification

- [x] `just check` passes (format, lint, complexity, typecheck, tests, audit).
- [x] New test fails before the implementation change and passes after.
