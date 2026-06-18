# Research Questions

## Context
Focus on the CLI entry module (`modernpackage/main.py`), the project `Justfile`
init recipe, and the unit tests in `tests/`. These areas cover how a
user-supplied package name is accepted, validated, transformed, and used to
create the scaffolded package's directory and source files.

## Questions
1. How is the user-supplied package name accepted, validated, and passed from
   the CLI through to the scaffolding subprocess calls? Trace the flow from
   argument parsing to where the name is consumed.

2. What exactly does the `just init` recipe in the `Justfile` do with the
   provided name — which text substitutions, file/directory renames, and source
   edits depend on it, and what character set does each step assume?

3. What format does the current name-validation regex permit (which characters
   are allowed and where), and what naming standards or conventions does it
   reference?

4. Where in the codebase is the package name used as a Python import path or
   source-package directory name versus as a distribution/display name, and are
   those uses currently distinguished?

5. What helper-function patterns exist in `main.py` for transforming or
   classifying strings (e.g. the git-error humanizer), including their
   signatures, return contracts, and module-level constants?

6. How are name-handling and string-transformation functions covered by the
   existing tests — what assertion style, fixtures, and edge cases are used?
