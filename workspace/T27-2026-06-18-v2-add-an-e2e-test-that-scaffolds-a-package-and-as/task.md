# Task

Add an end-to-end test that scaffolds a new package from the project's template
and asserts that the generated package passes `just check`. The goal is to
guarantee, via a real subprocess/filesystem run, that the scaffolding flow
produces a package that is lint-, type-, and test-clean rather than only
verifying scaffolding internals with mocks.
