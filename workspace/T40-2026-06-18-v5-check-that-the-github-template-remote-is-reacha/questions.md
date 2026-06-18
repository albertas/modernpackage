# Research Questions

## Context
Focus on the package-scaffolding flow in `modernpackage/main.py`, specifically
the function that drives cloning of the upstream template and the helpers it
calls before and after invoking git. Also examine the test suite under `tests/`
for how subprocess-backed behavior is exercised.

## Questions
1. Trace the end-to-end flow of `init_new_package` in `modernpackage/main.py`:
   what ordered steps run, which external commands are invoked via `subprocess`
   (`Popen`/`run`), and where in that sequence the template repository URL is
   used?
2. What pre-flight validation helpers run before the clone step (e.g. tool and
   target-directory checks), how are they named and structured, and how do they
   signal failure to the caller?
3. How are git/subprocess failures detected and reported today — how are exit
   codes inspected, how is stderr captured and decoded, and how does the
   error-humanizing layer (`humanize_git_clone_error` and its pattern table)
   map raw messages to friendly ones?
4. Where is the template remote URL defined and referenced across the module,
   and is it a shared constant or a repeated string literal?
5. How does the test suite exercise the scaffolding/clone path — what patterns
   are used to mock or patch `Popen`/`run`, simulate non-zero exit codes and
   stderr output, and assert on raised `RuntimeError` messages?
6. What conventions does the module follow for invoking subprocesses defensively
   (capture vs. pipe, `check` handling, decoding, and the `# noqa` security
   annotations), and how do existing error messages phrase remediation guidance
   to the user?
