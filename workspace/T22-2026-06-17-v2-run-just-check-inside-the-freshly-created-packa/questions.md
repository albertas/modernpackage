# Research Questions

## Context
Focus on the CLI orchestration in `modernpackage/main.py`, the subprocess
invocation pattern it uses, the `Justfile` command recipes, and the test suite
in `tests/`. The relevant areas are how the tool drives external commands in a
newly created directory and how those flows are covered by tests.

## Questions
1. How does `init_new_package` in `modernpackage/main.py` orchestrate its
   external commands today — what is the exact sequence of `Popen` calls, how is
   each subprocess constructed (arguments, `cwd`, stdio handling), and how are
   their return codes and stderr inspected?

2. What conventions does the codebase follow for handling and reporting
   subprocess failures (return codes, raising `RuntimeError`, surfacing stderr,
   the `humanize_*` helpers, and how `main()` translates errors into exit codes)?

3. What does the `Justfile` `check` recipe do — which sub-recipes does it run,
   what dependencies (e.g. `sync`) do those recipes trigger, and what
   environment or tooling do they assume to be present?

4. After `just init` runs, what is the resulting directory layout and state of
   the freshly created package (directory rename, version reset, `.git`
   re-initialization), and from which working directory are subsequent commands
   expected to run?

5. What patterns does `tests/test_main.py` use to exercise the subprocess flow —
   how are `Popen` calls mocked, how are multi-step subprocess sequences and
   their return codes simulated, and how are success and failure paths asserted?

6. How are end-to-end / real-subprocess tests configured in this project (the
   `e2e` pytest marker, `pyproject.toml` `addopts`, the `test-e2e` recipe), and
   are there existing e2e tests that actually invoke the scaffolding flow?
