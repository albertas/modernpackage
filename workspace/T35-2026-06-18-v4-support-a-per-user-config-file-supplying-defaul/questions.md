# Research Questions

## Context
Focus on the `modernpackage` CLI entry point (`modernpackage/main.py`), its
argument parsing and the way default values for metadata fields (author name,
author email, description, license, repository URL) are resolved from multiple
sources. Also look at the project's dependency/configuration conventions
(`pyproject.toml`, declared dependencies) and the unit-test suite
(`tests/test_main.py`).

## Questions
1. Trace the full flow of `parse_args()`: how is each metadata field's final
   value resolved, in what order are the existing default sources consulted,
   and where in the function is that ordering enforced?
2. How do the existing default-source helper functions (the environment-variable
   reader and the git-config reader) read their values, signal "not set", and
   degrade when a source is unavailable or returns an empty value?
3. How and where are metadata values validated, and how does validation apply
   to values that originate from non-flag sources versus values supplied
   directly as command-line flags?
4. What conventions does the project already use for reading and parsing
   structured files (e.g. file formats, standard-library or third-party
   parsing modules, file-location/path-resolution patterns), and what relevant
   parsing dependencies are already declared in `pyproject.toml`?
5. How does the CLI advertise its available default sources to the user (help
   text, README, docs), and what wording/format conventions are used there?
6. What patterns does `tests/test_main.py` use to test default resolution from
   different sources (fixtures for environment variables, monkeypatching, and
   isolating filesystem/subprocess access), and how are precedence and
   graceful-degradation cases asserted?
