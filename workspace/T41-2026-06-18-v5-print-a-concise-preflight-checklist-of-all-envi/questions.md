# Research Questions

## Context
Focus on the `modernpackage/main.py` CLI entry point, specifically the
pre-scaffolding verification functions and the `init_new_package` orchestration
flow. Also look at how the module emits user-facing output and how the test
suite (`tests/test_main.py`) exercises these areas.

## Questions
1. What pre-scaffolding verification functions exist (tool availability,
   target directory, template remote reachability, name validation), what does
   each check, and in what order are they invoked within `init_new_package`?
2. How does each verification function report success and failure today — what
   does it return, what exceptions does it raise, and what message text does it
   produce?
3. What conventions does the module use for user-facing output (e.g. `print`
   calls, stdout vs stderr, any formatting/styling, `noqa: T201` markers), and
   are any third-party output/formatting libraries available as dependencies?
4. How is the CLI's success/failure messaging structured at the end of a run
   (e.g. the `just check` passed/failed output), and how are exit codes derived?
5. How does `tests/test_main.py` test the verification functions and any
   captured console output — what fixtures, patching seams, and assertion
   patterns are used?
6. Where are the constants and data that define the set of checks (e.g.
   required tools list, template repository URL, timeout values) declared, and
   how are they referenced by the verification functions?
