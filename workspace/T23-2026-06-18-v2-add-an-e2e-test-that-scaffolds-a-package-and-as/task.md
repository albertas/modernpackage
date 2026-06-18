# Task

Add an end-to-end test that scaffolds a new package from this template (the
`just init` / `init_new_package` scaffolding path) and then asserts that
`just check` passes inside the freshly generated package. This gives confidence
that the template always produces a project whose full quality gate (format,
lint, complexity, typecheck, tests, audit) is green out of the box.

The test should be marked as `e2e` so it is excluded from the default test run
and only executed via the `just test-e2e` path, since it performs real
subprocess, filesystem, and possibly network calls.
