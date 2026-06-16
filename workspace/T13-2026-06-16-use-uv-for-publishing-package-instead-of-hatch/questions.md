# Research Questions

## Context
Focus on the project's build, packaging, and release tooling: the `Makefile`,
`Justfile`, `pyproject.toml`, CI configuration, and the `docs/` describing the
build/publish flow. The relevant concerns are how artifacts are built, how the
package version is derived, how artifacts are published to an index, and how
each tool is configured and invoked.

## Questions
1. Trace the current build-and-publish flow end to end: which command targets
   exist (in the `Makefile` and `Justfile`), what each step does, what tool it
   invokes, and in what order?
2. How is the package's distribution version determined at build time, and which
   configuration and source files participate in that mechanism?
3. What does `[build-system]` declare, and how do the build backend, the build
   frontend CLI, and any backend-specific configuration sections in
   `pyproject.toml` relate to one another?
4. How is `uv` already used in this project (dependency management, locking,
   syncing, indexes), and what configuration exists for `uv` and for any package
   indexes it targets?
5. Where is the build/publish tooling referenced or documented across the
   repository (README, `docs/`, CI workflow files), and what does each reference
   describe or rely on?
6. What capabilities does `uv` provide for building distributions and publishing
   them to an index, including how it locates artifacts, selects a target index,
   and handles authentication credentials?
