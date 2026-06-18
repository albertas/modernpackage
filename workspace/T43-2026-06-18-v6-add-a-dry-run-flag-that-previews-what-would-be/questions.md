# Research Questions

## Context
Focus on the `modernpackage` CLI implemented in `modernpackage/main.py`, its
argument parsing, and its package-initialization flow. Relevant areas are the
end-to-end scaffolding sequence, the subprocess calls it makes, how it mutates
files on disk, and how it reports progress and errors. The tests in
`tests/test_main.py` and `tests/test_e2e.py` and the docs under `docs/` describe
expected behavior and conventions.

## Questions
1. Trace the full sequence of operations in `init_new_package`: which steps
   create directories, write or modify files, or rename anything on disk, and in
   what order do they run relative to the preflight checks?
2. What subprocess commands does the scaffolder invoke (e.g. `git clone`,
   `just init`, `just check`), and what side effects does each have on the
   filesystem — in particular, what does the `just init` step rename or
   transform inside the cloned template?
3. How does `_write_package_metadata` decide what to change in the cloned
   `pyproject.toml`, and which template placeholders or literals does it replace?
4. How are CLI flags defined and threaded through the code — from `parse_args`
   into `main` and then into `init_new_package` — and what conventions govern
   boolean/store-true flags, defaults, and help text?
5. What conventions does the codebase follow for user-facing output: what goes
   to stdout versus stderr, and how are status lines, checklists, and summaries
   formatted (e.g. the preflight checklist)?
6. How are the scaffolding flow and its subprocess interactions tested — what
   mocking patterns (e.g. patching `Popen`/`run`), fixtures, and markers
   distinguish the unit tests from the end-to-end test?
