# Research Questions

## Context
Focus on the CLI argument-parsing layer in `modernpackage/main.py`, the
validation helpers it uses, and how parsed metadata options flow into
`init_new_package`. Also examine the test suite (`tests/test_main.py`,
`tests/test_e2e.py`) for how arguments, defaults, and environment variables are
currently exercised.

## Questions
1. How are the metadata command-line options (author name, author email,
   description, license, repository URL) defined in `parse_args`, including their
   defaults, `type=` validators, and help text?
2. How do the `validate_author_email` and `validate_repository_url` helpers and
   their regex constants work, and at what point in the argparse lifecycle are
   these validators invoked relative to default values?
3. How are parsed argument values threaded from `parse_args` through `main` into
   `init_new_package`, and how does that function currently consume or discard
   the metadata parameters?
4. Where in the codebase (source or tests) are environment variables read or
   referenced today, and what naming conventions and access patterns are used
   for them?
5. How does the existing test suite construct argument scenarios and verify
   defaults, and what mechanisms (e.g. patching `sys.argv`, `monkeypatch`,
   environment fixtures) are used to isolate and exercise these code paths?
6. What conventions does the module follow for module-level constants, regex
   naming, type annotations, and small helper functions that new code would be
   expected to match?
