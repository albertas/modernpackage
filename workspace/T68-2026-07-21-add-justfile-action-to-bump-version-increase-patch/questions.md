# Research Questions

## Context
Focus on how the package version is declared, stored, and read; how the
`Justfile` recipes are structured (especially any build/publish/release flow and
any git interaction inside them); and any existing code that programmatically
reads or rewrites the version string. Also look at the packaging/build backend
configuration and the available tooling in the dependency set.

## Questions
1. Where is the package version string defined and stored, and how is it wired
   into the build backend configuration (pyproject.toml) so that packaging picks
   it up?
2. What does the current `publish` recipe (and any related build/release
   recipes) in the `Justfile` do step by step, including any git commands it
   runs and their ordering?
3. What patterns already exist in the codebase for programmatically reading,
   parsing, or rewriting the version string in the source file (for example any
   sed commands in the `Justfile` or file-rewriting logic in Python), and where
   is a version value hardcoded or reset?
4. What conventions do existing `Justfile` recipes follow (dependencies between
   recipes, `sync` prerequisites, shell syntax, how a recipe invokes Python or
   external tooling), and how does a recipe currently shell out to run project
   code?
5. What version-manipulation tooling is already available in the project's
   dependencies or build backend (for example hatch/hatchling version commands,
   `uv version`, or similar), and how is such tooling invoked elsewhere?
6. How is the version value referenced or asserted in tests and in any
   scaffolding logic, so that changes to how the version is stored would need to
   stay consistent with those references?
