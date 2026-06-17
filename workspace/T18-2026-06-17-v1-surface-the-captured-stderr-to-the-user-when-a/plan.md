# Plan

## Phase 1: Surface captured stderr to the user on step failure

### Context

`modernpackage/main.py` runs two scaffolding steps via `Popen`: `git clone` and
`just init`. Each step already captures stderr and raises a `RuntimeError` whose
message includes the captured stderr text (delivered by T17). However, `main()`
calls `init_new_package(...)` without handling that exception, so a failed step
currently surfaces to the user as a raw Python traceback rather than the
captured stderr.

Scope note: exiting with a non-zero status code is a **separate** backlog task.
This task only makes the captured stderr visible to the user. Do not add
`sys.exit(...)` here.

### Implementation

In `modernpackage/main.py`:

1. Add `import sys` to the imports.
2. In `main()`, wrap the `init_new_package(...)` call in a `try`/`except
   RuntimeError` and print the error message to `sys.stderr`:

   ```python
   elif parsed_args.package_name:
       try:
           init_new_package(package_name=parsed_args.package_name)
       except RuntimeError as error:
           print(error, file=sys.stderr)  # noqa: T201
   ```

   The `RuntimeError` message already contains the captured stderr, so printing
   the error surfaces it as a clean, single message instead of a traceback.

### Tests

In `tests/test_main.py`, add a test asserting that when `init_new_package`
raises `RuntimeError`, `main()` catches it and prints the message (containing
the stderr) to the user instead of propagating:

```python
def test_main_surfaces_stderr_on_failure() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        init_mock.side_effect = RuntimeError(
            'git clone failed with exit code 1: boom'
        )
        main()  # must not raise
    # error message (with captured stderr) was shown to the user
    printed = str(print_mock.call_args.args[0])
    assert 'boom' in printed
```

Note: existing tests patch `modernpackage.main.print`; keep that seam. If the
implementation passes `file=sys.stderr`, assert on `print_mock.call_args.kwargs`
accordingly, or simply assert the message content as above.

### Verify

- [x] `just test` — new test passes, existing tests still pass.
- [x] `just check` — lint/format/typecheck clean (ensure the `# noqa: T201` is
  present on the new `print`).
