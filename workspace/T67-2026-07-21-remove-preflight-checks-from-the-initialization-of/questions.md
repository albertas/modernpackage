# Research Questions

## Context
Focus on the package-initialization flow in `modernpackage/main.py`, its
supporting helper functions and module-level constants, the tests in
`tests/test_main.py`, and the documentation under `docs/`. The area of interest
is the sequence of steps run when a new package is scaffolded and the validation
that occurs before the template is cloned.

## Questions
1. What is the end-to-end control flow of `init_new_package` in
   `modernpackage/main.py` — which steps run in what order, and how is the
   preflight checklist step invoked and structured within it?

2. What helper functions and module-level constants exist for the preflight
   checks (e.g. `PreflightCheck`, `_run_preflight_checks`, `_verify_*`,
   `_format_check_line`, `_PREFLIGHT_HEADER`, `_REQUIRED_TOOLS`,
   `_TOOL_INSTALL_HINTS`, `_REMOTE_REACHABILITY_TIMEOUT_SECONDS`), and which of
   these are referenced only by the preflight logic versus shared with other
   parts of the module?

3. How does the initialization flow detect and report failures during the
   actual clone and `just init` steps (for example `humanize_git_clone_error`,
   handling of a missing `just` executable, and existing-directory conditions),
   independent of the preflight checklist?

4. How does `tests/test_main.py` cover the preflight behavior — which test
   functions, fixtures, and helpers exercise the checklist and its individual
   verifiers, and do any of them also assert on shared helpers used elsewhere?

5. Where and how do the documentation files under `docs/` (e.g. `invocation.md`,
   `overview.md`, `architecture.md`, `data_flows.md`, `specification.md`)
   describe the preflight checks and their place in the initialization flow?

6. How is stdout output formatted and colorized across the initialization flow
   (e.g. `_green`, `_color_enabled`, `_format_check_line`, and the dry-run /
   summary / next-steps blocks), and which of these formatting helpers are used
   beyond the preflight checklist?
