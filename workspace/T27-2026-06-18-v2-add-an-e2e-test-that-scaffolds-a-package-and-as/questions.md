# Research Questions

## Context
Focus on the package-scaffolding tool: the CLI entrypoint that clones a template
and initializes a new package, the `Justfile` recipes that drive initialization
and quality checks, and the test suite. Pay attention to how tests are
organized, marked, and selected, and how the same flows run under CI.

## Questions
1. How does the scaffolding entrypoint in `modernpackage/main.py` work end to
   end — what steps does `init_new_package` perform (clone, init, check), and
   how are failures and exit codes propagated?
2. What does the `init` recipe in the `Justfile` do to transform the template
   into a named package, and what filesystem/git state does it produce?
3. What does the `just check` recipe run, what external tools and network access
   does it depend on, and how long-running or environment-sensitive is it?
4. How is the test suite structured, and specifically how is the `e2e` pytest
   marker defined, selected, and excluded by default (in `pyproject.toml` and
   the `Justfile`)?
5. What existing end-to-end or integration test coverage exists for the
   scaffolding flow (e.g. `tests/test_e2e.py`), what approach does it take, and
   what caveats or deviations does it document?
6. How do the CI configurations (`.gitlab-ci.yml`, `.github/`) run the test and
   check flows, and how (if at all) do they handle network- or
   subprocess-dependent tests?
