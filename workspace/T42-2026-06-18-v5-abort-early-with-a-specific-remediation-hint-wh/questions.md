# Research Questions

## Context
Focus on the package-scaffolding CLI in `modernpackage/main.py` and its tests in
`tests/`. The relevant areas are the preflight check registry and verifier
functions, the construction and formatting of error/failure messages, and how
failures propagate from individual checks up to the process exit code.

## Questions
1. How is the preflight check sequence structured — how are individual checks
   registered, what order do they run in, and what happens when one of them
   fails partway through the sequence?
2. For each existing verifier (required tools on PATH, target directory
   availability, template remote reachability, package-name validity), what
   exactly does it signal on failure, and what text/content does each failure
   message carry?
3. What conventions exist across the module for composing user-facing error
   messages — for example how friendly/human-readable hints are combined with
   raw diagnostic detail, and where reusable hint strings or message-building
   helpers live?
4. How do failures raised by checks and subprocess steps propagate up through
   `init_new_package` and `main`, and how is the process exit status determined
   relative to where in the flow the failure occurs?
5. What ordering exists between the preflight checks and the first
   filesystem-mutating or network step (the git clone), and what guarantees that
   checks complete before any such mutation begins?
6. How are the preflight checks and verifier failure messages tested — what
   patterns (mocking, fixtures, asserting on message content) do the tests use
   to exercise success and failure paths?
