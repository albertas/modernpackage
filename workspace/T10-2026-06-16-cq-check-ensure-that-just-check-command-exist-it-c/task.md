# Task

Ensure the `Justfile` exposes a single `check` target that combines every
quality check defined in the file (format, lint, complexity, typecheck, tests),
and confirm that running `just check` passes cleanly. This is the capstone of
the code-quality backlog (T6–T9), giving a one-command gate for the whole
project.
