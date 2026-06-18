# Research Questions

## Context
Focus on `modernpackage/main.py`, which orchestrates package scaffolding by
invoking external command-line tools, and its companion tests in
`tests/test_main.py` and `tests/test_e2e.py`. The relevant areas are how external
executables are invoked, how their absence or failure is surfaced to the user, and
how those behaviors are exercised by tests.

## Questions
1. Trace the scaffolding control flow in `init_new_package` and `main`: which
   external executables are invoked, in what order, and at what point does each
   subprocess get launched relative to filesystem changes?
2. What external tools does the scaffolding rely on indirectly — for example,
   which executables do the `just init` and `just check` recipes themselves call,
   and where are those recipes defined?
3. How does the current code detect and report a missing executable versus a
   non-zero exit from a command that does exist? Catalog every `FileNotFoundError`
   handler, `RuntimeError` raise, and exit-code path, and the exact user-facing
   message each produces.
4. What conventions govern user-facing error and notice messages in this module
   (wording, stderr vs stdout, raise-vs-print, friendly-message humanization), and
   where are they defined?
5. How do the existing tests mock or stub subprocess invocations (`Popen`, `run`)
   and assert on missing-tool and command-failure behavior, and what helper or
   fixture patterns are used?
6. Is there any existing mechanism that checks whether a required tool is present
   on `PATH` (for example `shutil.which`), and where and how is it used today?
