# Task

The `modernpackage` CLI scaffolds a new Python package by cloning a template
repository and running `just init` inside it. This task extends the scaffolding
flow so that, after `just init` completes, the tool runs `just check` inside the
freshly created package. The goal is to confirm that the generated package
passes its own combined quality gate before the scaffolding tool reports
completion.
