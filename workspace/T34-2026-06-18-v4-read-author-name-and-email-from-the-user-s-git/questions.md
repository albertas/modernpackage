# Research Questions

## Context
Focus on `modernpackage/main.py` and its tests under `tests/`. The relevant
areas are how author/contributor metadata defaults are sourced and resolved,
how the code invokes external command-line tools as subprocesses, and how those
behaviors are tested.

## Questions
1. How is author name and email metadata currently resolved at startup — which
   sources are consulted, what helper functions read them, and what precedence
   governs which source wins?

2. How does the code invoke external command-line tools as subprocesses, and
   what is the standard pattern for capturing their output, checking return
   codes, and handling a missing executable?

3. How are optional/default metadata values represented when absent, and where
   and how are name and email values validated before use?

4. After metadata values are resolved, how are they threaded through the rest of
   the program — which functions receive them and how (if at all) are they
   consumed downstream?

5. What patterns do the tests use to exercise code that shells out to external
   commands — how is the subprocess seam mocked or patched, and what fixtures
   support this?

6. What conventions does the codebase follow for module-private helper
   functions, naming of module-level constants, and type annotations on those
   helpers?
