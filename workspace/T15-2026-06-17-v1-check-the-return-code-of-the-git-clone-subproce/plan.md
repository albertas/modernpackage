# Plan

## Phase 1: Fail loudly when git clone returns a non-zero code

### What changes
In `modernpackage/main.py`, function `init_new_package`:

1. After the git clone `pipe.communicate()` call, inspect `pipe.returncode`.
   `Popen.communicate()` waits for the process to finish and sets
   `returncode`, so it is available immediately afterward.
2. If `pipe.returncode != 0`, raise a `RuntimeError` with a clear message
   (e.g. `f'git clone failed with exit code {pipe.returncode}'`) so the
   function stops before attempting `just init` on a missing/incomplete
   directory.
3. Leave the subsequent `just init` `Popen` block unchanged — it is out of
   scope for this task.

### Why
Raising loudly matches the repo convention of using `RuntimeError`/`ValueError`
for internal invariant violations (see Code Best Practices). A failed clone is
a hard precondition failure for the rest of `init_new_package`, so continuing
makes no sense.

### Testing → verify
- [x] Add a test in `tests/test_main.py` modeled on the existing
  `test_init_new_package`. Patch `modernpackage.main.Popen` so the mocked
  `pipe.returncode` (or the value set after `communicate()`) is non-zero, then
  assert `init_new_package('mypackage')` raises `RuntimeError`.
  - Note: the existing mock returns a `MagicMock`; configure
    `popen_mock.return_value.returncode = 1` (or set it on the instance) to
    drive the failure path, and `= 0` to confirm the success path still
    proceeds.
- [x] Add/confirm a success-path test asserting that with `returncode == 0` the
  function does not raise and the second (`just init`) `Popen` is still invoked.
- [x] Run `just check` (covers format, lint, complexity, typecheck, tests, audit)
  and confirm it passes.
