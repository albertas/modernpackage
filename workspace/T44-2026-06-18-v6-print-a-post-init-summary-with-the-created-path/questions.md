# Research Questions

## Context
Focus on the CLI scaffolding flow in `modernpackage/main.py`, specifically the
`init_new_package` function and its success/failure path after subprocesses run.
Also look at the user-facing output helpers (dry-run plan, preflight checklist),
the version constant, and the test suite in `tests/`.

## Questions
1. Trace the end of `init_new_package`: after the `just init` and `just check`
   subprocesses run, what does the code print to stdout vs stderr, in what
   order, and what return codes accompany each outcome?
2. How are the created directory path, the distribution/package name, and the
   import-safe module name derived inside `init_new_package`, and which of these
   values are already available as local variables in the success path?
3. How is the package version represented and reset during scaffolding — where
   does the `0.0.1` reset value come from, how does `just init` perform the
   reset, and how does existing code (e.g. the dry-run plan) reference that
   value?
4. What conventions do existing user-facing output blocks follow — how are the
   dry-run plan (`_format_dry_run_plan`) and preflight checklist
   (`_run_preflight_checks`) structured into formatter vs printer helpers, and
   what formatting/indentation patterns do they use?
5. How does the test suite (`tests/test_main.py`, `tests/test_e2e.py`) capture
   and assert on stdout/stderr output from `init_new_package`, and what mocking
   patterns are used for the `git`/`just` subprocess calls?
