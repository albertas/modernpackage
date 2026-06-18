# Plan

## Phase 1: Print next commands after a successful run

### Goal
On a successful scaffold (the `just check passed` branch of
`init_new_package`), print a "next steps" hint of the form
`cd <name> && just check` so the user has an actionable command to continue.

### Implementation
All changes are in `modernpackage/main.py`, in the success path of
`init_new_package` (currently around lines 778–781) and alongside the existing
`_format_init_summary` / `_print_init_summary` helpers.

1. Add a formatter helper mirroring the existing summary helpers, e.g.
   `_format_next_commands(module_name: str) -> str` returning a short block such
   as:

   ```
   Next steps:
     cd modulename && just check
   ```

   Use `module_name` (the created directory name, e.g. `my_package`) for
   `<name>`, since that is the directory the user must `cd` into — consistent
   with `new_package_path = Path.cwd() / module_name` and the `path:` line in
   `_format_init_summary`. Define any header as a module-level constant
   (e.g. `_NEXT_COMMANDS_HEADER`) following the existing
   `_INIT_SUMMARY_HEADER` / `_PREFLIGHT_HEADER` style.

2. Add `_print_next_commands(module_name: str) -> None` that prints the
   formatted block to stdout (with the same `# noqa: T201` convention used by
   the other print helpers).

3. In the `if pipe.returncode == 0:` success branch, call
   `_print_next_commands(module_name)` after `_print_init_summary(...)` so the
   ordering is: `just check passed` line → created-package summary → next steps.

### Tests
Add tests in `tests/test_main.py` alongside the existing summary tests:

1. `test_format_next_commands_contains_cd_and_just_check` — call
   `_format_next_commands('my_package')` and assert the output contains
   `cd my_package` and `just check` (and the `&&` join).

2. Extend / add a success-path test like
   `test_init_new_package_prints_summary_on_success` asserting that the printed
   calls include the next-commands hint (`cd mypackage && just check`). Import
   the new helper at the top of the test module next to `_format_init_summary`.

### Verify
- [x] `just test` — all tests pass, including the new ones.
- [x] `just check` — format, lint, typecheck, and complexity gates pass.
- [x] Confirm `questions.md` is not needed (simple task).
