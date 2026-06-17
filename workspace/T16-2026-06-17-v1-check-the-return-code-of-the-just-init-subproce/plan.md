# Plan

## Phase 1: Fail loudly when `just init` returns a non-zero code

### What changes
In `modernpackage/main.py`, function `init_new_package` (the second `Popen`
block, currently `main.py:52-58`):

1. After the `just init` `pipe.communicate()` call, inspect `pipe.returncode`.
   `Popen.communicate()` waits for the process to finish and sets
   `returncode`, so it is available immediately afterward.
2. If `pipe.returncode != 0`, raise a `RuntimeError` with a clear message
   (e.g. `f'just init failed with exit code {pipe.returncode}'`), matching the
   wording style of the existing `git clone failed with exit code ...` check.
3. Keep the existing `communicate()[0].decode().strip()` call (its decoded
   output is currently discarded — leave that behaviour as-is; only add the
   return-code check after it).

### Why
This mirrors the `git clone` return-code check added in T15 and follows the
repo convention of raising `RuntimeError` for internal invariant violations
(see Code Best Practices). A failed `just init` leaves the cloned directory in
an incomplete state, so silently continuing is wrong.

### Testing → verify
- [x] Add a test in `tests/test_main.py` modeled on
  `test_init_new_package_git_clone_failure`. The two `Popen` calls share
  `popen_mock.return_value`, so to exercise the `just init` failure path while
  letting `git clone` succeed, give `popen_mock` a `side_effect` of two mock
  instances: the first with `returncode = 0` (git clone OK), the second with
  `returncode = 1` (just init fails). Assert `init_new_package('mypackage')`
  raises `RuntimeError` matching `'just init failed with exit code 1'`.
- [x] Confirm the existing success-path test (`test_init_new_package`, which
  sets `returncode = 0`) still passes and that both `Popen` calls are invoked.
- [x] Run `just check` (covers format, lint, complexity, typecheck, tests,
  audit) and confirm it passes.
