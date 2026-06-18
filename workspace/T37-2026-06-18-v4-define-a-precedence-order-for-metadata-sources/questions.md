# Research Questions

## Context
Focus on the CLI argument-parsing layer in `modernpackage/main.py`, specifically
the function that parses options and then fills in default values, and the small
helper functions that read values from environment variables, git config, and a
per-user TOML config file. Also look at the unit tests in `tests/` that exercise
those helpers and at the `docs/` files (overview, architecture, specification)
that describe how metadata defaults are resolved.

## Questions
1. After argparse produces its namespace, trace the step-by-step sequence by
   which each metadata field is populated from the environment, git config, and
   config-file readers — in what order are these consulted, and what guards
   each step so it does not overwrite a value already supplied by a stronger
   source?
2. What helper functions read a metadata value from an environment variable,
   from git config, and from the per-user config file, and what shared
   convention (if any) do they use for treating empty, missing, or
   wrong-typed values as "unset"?
3. For each of the five metadata fields, which of the available sources can
   supply it — are all fields backed by every source, or do some sources apply
   only to a subset of fields, and where is that asymmetry encoded?
4. How do the existing tests verify the interaction between two or more sources
   competing to supply the same field (for example one source set while another
   is also set), what naming pattern do those tests follow, and what
   fixtures/mocks (environment patching, subprocess stubbing, temp config files)
   do they rely on?
5. Where and how is the ordering relationship between metadata sources currently
   described — in code comments, in `--help` text, and across the `docs/`
   files — and how consistent are those descriptions with each other?
6. Once the metadata fields are resolved, where do those values flow next — how
   are they passed into the package-initialisation path and written into the
   generated `pyproject.toml`, and how are still-unset values handled there?
