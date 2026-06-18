# Plan

## Phase 1: Report the post-scaffold `just check` outcome

### Context

In `modernpackage/main.py`, `init_new_package()` runs `just check` as its final
step (currently lines 123–130):

```python
pipe = Popen(
    ['just', 'check'],  # noqa: S607
    stdin=PIPE,
    stdout=PIPE,
    stderr=PIPE,
    cwd=new_package_path,
)
pipe.communicate()
```

The return code is never inspected, so the user is told nothing about whether
the freshly scaffolded package passed validation. This phase adds a clear
pass/fail message.

Out of scope: changing `main()`'s exit code on failure (separate backlog task).
`init_new_package` keeps its current behavior of not raising for a `just check`
failure — it only reports.

### Implementation

1. Capture the return code of the `just check` invocation:

   ```python
   pipe = Popen(
       ['just', 'check'],  # noqa: S607
       stdin=PIPE,
       stdout=PIPE,
       stderr=PIPE,
       cwd=new_package_path,
   )
   pipe.communicate()

   if pipe.returncode == 0:
       print(f'just check passed — {package_name} scaffold is valid.')  # noqa: T201
   else:
       print(  # noqa: T201
           f'just check failed with exit code {pipe.returncode}'
           f' — review the output in {package_name}.',
           file=sys.stderr,
       )
   ```

   - Success message goes to stdout; failure message goes to stderr, matching the
     module's existing convention (version → stdout, errors → stderr via `sys.stderr`).
   - Use `print` (not logging) to stay consistent with the rest of `main.py`, and
     because the tests patch `modernpackage.main.print`.
   - `sys` is already imported.

2. Do not change the function signature or return value, and do not raise on a
   non-zero `just check` exit code (exit-code handling is a separate task).

### Testing

Add tests to `tests/test_main.py` following the existing `Popen`-mocking pattern.
Note the existing tests use `popen_mock.return_value` for all three calls; for
distinct return codes per call use `popen_mock.side_effect` with separate
`MagicMock` objects (as in `test_init_new_package_just_init_failure`).

1. `test_init_new_package_reports_check_passed`:
   - All three `Popen` calls return `returncode == 0`.
   - Patch `modernpackage.main.print`; assert a message containing
     `'just check passed'` was printed.

2. `test_init_new_package_reports_check_failed`:
   - git clone and `just init` mocks return `returncode == 0`; the `just check`
     mock returns a non-zero `returncode` (e.g. `1`).
   - Patch `modernpackage.main.print`; assert a message containing
     `'just check failed'` and the exit code was printed.
   - Assert `init_new_package` does **not** raise (failure is reported, not fatal).

3. Confirm existing tests (`test_init_new_package`,
   `test_init_new_package_runs_just_check`) still pass — they use
   `returncode == 0`, so the new success branch must not break them.

### Verification

- [x] `just check` passes (format, lint, complexity, typecheck, tests, audit).
- [x] New and existing tests in `tests/test_main.py` pass.
