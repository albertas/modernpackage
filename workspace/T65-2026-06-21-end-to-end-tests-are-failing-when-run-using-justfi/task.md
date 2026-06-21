# Task

The end-to-end tests fail when invoked through the project's Justfile alias
(`just e` / `just test-e2e`). The end-to-end suite is meant to install this
package in editable mode, scaffold a fresh package, run its quality checks
(which should pass), then modify the scaffolded package and re-run the checks to
confirm they still pass.

The goal is to make every end-to-end test green when run through the Justfile
alias. The task is not complete until the full e2e suite passes via that alias.
