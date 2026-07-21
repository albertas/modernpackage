# Task

When `modernpackage` scaffolds a new package from the cloned template, the
generated tree must not carry the scaffolder's own operational artifacts:
the `errors/`, `issues/`, and `workspace/` directories, and the
`lifecycle_state.yml` and `metrics.yml` files. These are development/process
files of the scaffolder repository and are meaningless (and noisy) in a
freshly generated package, so they should be stripped during instantiation
alongside the CLI, docs, and BACKLOG that are already removed.
