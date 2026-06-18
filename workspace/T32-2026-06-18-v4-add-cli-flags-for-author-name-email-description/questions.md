# Research Questions

## Context
Focus on the `modernpackage` CLI entry point (`modernpackage/main.py`), its
argument parser, its package-initialization flow, the template `pyproject.toml`
metadata, the `just init` recipe in the `Justfile`, and the CLI tests under
`tests/`.

## Questions
1. How is the command-line argument parser constructed in `parse_args`, what
   positional arguments and flags does it currently define, and what conventions
   (short/long option names, defaults, help text) are used for each?
2. How does a parsed argument flow from `parse_args` through `main` into
   `init_new_package`, and how are values passed to that function and used
   inside it?
3. What patterns exist for validating and type-converting argument values (for
   example `validate_package_name` and `ArgumentTypeError`), and how are invalid
   inputs reported to the user?
4. What metadata fields (author name, author email, description, license,
   repository/homepage URL) exist in the template `pyproject.toml`, and what are
   their current literal placeholder values and section locations?
5. How does the `just init` recipe transform the cloned template (for example
   the `sed`/`git grep` substitutions and the version reset), and at what point
   in `init_new_package` is it invoked?
6. How are `parse_args` and `init_new_package` covered by the existing tests in
   `tests/`, including how the parser, subprocess calls, and argument flow are
   mocked and asserted?
