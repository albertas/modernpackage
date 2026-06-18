# Research Questions

## Context
Focus on the CLI package-name handling in `modernpackage/main.py` — the
validation regex, the normalization helper, and the messages raised when a
name is rejected. Also look at how other user-facing failures are translated
into friendly explanations, how argument parsing surfaces these errors, and
how the related behavior is covered by tests.

## Questions
1. How does `validate_package_name` decide whether a name is acceptable, what
   rules does `_PACKAGE_NAME_RE` enforce, and what exact message(s) does the
   function raise on each rejection path?
2. What categories of names does the current validation reject or explicitly
   treat as out of scope (e.g. empty strings, leading/trailing separators,
   disallowed characters, leading digits, Python keywords, standard-library
   collisions), and where is each documented in code comments or docstrings?
3. How does `humanize_git_clone_error` map low-level failure text to ordered,
   human-friendly explanations, and what conventions does that pattern follow
   for message wording and precedence?
4. How are validation failures propagated from `validate_package_name` through
   argparse to the user, and what exit codes and output streams result?
5. How is `normalize_module_name` related to validation, and what assumptions
   does it make about its input having already been validated?
6. How do the existing tests in `tests/test_main.py` exercise valid names,
   invalid names, and standard-library collisions, and what message text do
   they assert on?
