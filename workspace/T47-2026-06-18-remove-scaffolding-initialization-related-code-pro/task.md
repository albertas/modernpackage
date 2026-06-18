# Task

`modernpackage` is a self-replicating CLI scaffolder: it clones itself as the
template for a new package and runs `just init` to rename it. The resulting
generated project currently still carries the scaffolder's own
initialization/scaffolding code (the clone / preflight / metadata-writing / init
CLI in `main.py`, plus its tests and docs).

This task makes the initialization flow programmatically strip that
scaffolding/initialization code out of the resulting project, so a freshly
scaffolded package ships clean (without the self-replicating CLI) while still
passing `just check`.
