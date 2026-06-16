# Task: Merge Makefile into Justfile

The project currently maintains both a `Makefile` and a `Justfile` with
overlapping and divergent command sets. The goal is to consolidate on a single
task runner by moving every capability the `Makefile` provides (and that the
`Justfile` lacks) into the `Justfile`, then deleting the `Makefile`.

All places that invoke `make` — the CLI's package initialisation flow, CI
pipelines, and documentation — must be updated to use the equivalent `just`
targets so nothing breaks once the `Makefile` is removed.
