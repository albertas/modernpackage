# T64 — Fix end-to-end tests failing via the Justfile alias

The `modernpackage` end-to-end tests (the `e2e`-marked tests run through the
Justfile alias, e.g. `just e` / `just test-e2e`) are currently failing and must
be made green. Each e2e test should install this package in editable mode,
scaffold a fresh package, run the generated package's checks (which must pass),
then apply modifications to that scaffolded package and confirm the checks still
pass after the modifications. The task is complete only when every end-to-end
test passes when invoked through the Justfile alias.
