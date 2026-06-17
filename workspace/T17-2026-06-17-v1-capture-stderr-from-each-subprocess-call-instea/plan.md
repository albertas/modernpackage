# Plan

## Phase 1: Capture and surface subprocess stderr

### Context

`modernpackage/main.py` defines `init_new_package`, which runs two subprocesses
via `subprocess.Popen`:

1. `git clone ...` (lines 41-50)
2. `just init <package_name>` (lines 52-62)

Both pass `stdin=PIPE, stdout=PIPE` but no `stderr`, so the child's stderr is
inherited/lost. On non-zero exit, each raises a `RuntimeError` that only reports
the exit code, not the captured error output.

### Changes

In `modernpackage/main.py`, for both `Popen` calls:

1. Add `stderr=PIPE` to each `Popen(...)` call so stderr is captured.
2. Capture stderr from `communicate()`. `communicate()` returns
   `(stdout, stderr)`; bind both, e.g.:
   ```python
   _stdout, stderr = pipe.communicate()
   ```
3. On non-zero `returncode`, include the decoded stderr text in the
   `RuntimeError` message, e.g.:
   ```python
   message = f'git clone failed with exit code {pipe.returncode}: {stderr.decode().strip()}'
   ```
   Do the same for the `just init` failure message.

Keep the existing `# noqa` comments and style. Do not change any unrelated code.

### Verify

- [x] `just test` passes. Update the two failure tests
  (`test_init_new_package_git_clone_failure`,
  `test_init_new_package_just_init_failure`) so the mocked `Popen` return value /
  side-effect mocks provide a `communicate()` return of a `(stdout, stderr)`
  tuple (e.g. `mock.communicate.return_value = (b'', b'some error')`), and assert
  the new message still matches via the existing `match=` patterns (the exit-code
  substring is preserved). Confirm `test_init_new_package` (success path) still
  passes, providing a `communicate()` tuple where needed.
- [x] `just check` (format, lint, complexity, typecheck) passes.
