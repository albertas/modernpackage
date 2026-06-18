# Plan

## Phase 1: Propagate `just check` failure into the CLI exit code

### Context

`modernpackage/main.py` scaffolds a package and then runs `just check` inside it
(`init_new_package`, lines ~123-139). Failures of `git clone` and `just init`
are raised as `RuntimeError`, which `main()` catches and turns into a `return 1`.
But the `just check` step only *prints* a pass/fail message (T25) — it does not
influence the return value, so `init_new_package` returns `None` and `main()`
returns 0 even when `just check` failed.

The existing pass/fail reporting (the `print(...)` to stdout/stderr) must be
preserved; only the exit-code propagation is being added.

### Implementation

1. In `modernpackage/main.py`, change `init_new_package` to return an `int` exit
   code instead of `None`:
   - Annotate the signature as `-> int`.
   - In the `just check` block, keep the existing `print(...)` pass/fail
     reporting unchanged.
   - After printing, return `0` when `pipe.returncode == 0` and `1` otherwise
     (normalize to 1 rather than forwarding the raw `just` exit code, matching
     the `return 1` convention used elsewhere in `main()`).
   - The early `RuntimeError` paths (clone/init failures) are unchanged; they
     still raise and never reach the return.

2. In `main()`, return the value from `init_new_package` on the success path so
   a failed `just check` yields a non-zero exit:
   - Replace `init_new_package(package_name=...)` with
     `return init_new_package(package_name=...)` inside the `try`.
   - Keep the `except RuntimeError` branch returning 1 and the trailing
     `return 0` (for the `--version` / no-arg paths) intact.

### Tests (`tests/test_main.py`)

3. Update `test_init_new_package_reports_check_passed` to assert the return value
   is `0`.

4. Update `test_init_new_package_reports_check_failed` to assert the return value
   is `1` (the function still must not raise; keep the existing printed-message
   assertions).

5. Add a `main()`-level test, e.g. `test_main_returns_one_when_just_check_fails`,
   that patches `init_new_package` to return `1` (with `version=False`,
   `package_name='mypackage'`) and asserts `main()` returns `1`. Also confirm the
   existing `test_main_with_package_name` still passes (it patches
   `init_new_package`, whose `MagicMock` return is truthy — assert that test is
   adjusted to make the mock return `0` so `main()` returns `0`).

### Verify

- [x] Run `just test` (or `just check`) — all tests pass.
- [x] Spot-check: `init_new_package` returns `1` when the `just check` `Popen`
  mock has a non-zero `returncode`, and `main()` propagates it.
