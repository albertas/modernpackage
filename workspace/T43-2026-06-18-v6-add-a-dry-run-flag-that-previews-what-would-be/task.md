# Task

Add a `--dry-run` flag to the `modernpackage` CLI that previews what the
scaffolder would create and rename without writing anything to disk or invoking
the scaffolding subprocesses. When the flag is set, the tool should report the
intended actions (target directory, files written, renames) and exit cleanly so
users can inspect the plan before committing to a real run.
