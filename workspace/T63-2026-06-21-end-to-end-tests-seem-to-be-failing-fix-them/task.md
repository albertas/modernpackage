# Task

The repository's end-to-end test suite (`tests/test_e2e.py` and the standalone
`tests_e2e/` directory) is currently failing when run via `just test-e2e`.
These tests scaffold packages from the local checkout and exercise the generated
stack through container compose, `just check`, database migrations, and (for
fullstack) the frontend; the goal is to diagnose why they fail in this
environment and make them pass again. Observations so far point to at least two
distinct root causes — the compose-driven runtime tests and the `passes_check`
tests both fail — so the fix likely spans more than one area.
