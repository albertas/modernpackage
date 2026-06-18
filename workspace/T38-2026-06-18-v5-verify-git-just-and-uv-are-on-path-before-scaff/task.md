# Task

Add a pre-flight check to the `modernpackage` scaffolding flow that verifies the
`git`, `just`, and `uv` executables are available on `PATH` before any scaffolding
work begins. The goal is to fail fast with a clear, actionable message naming the
missing tool, rather than failing partway through a clone or initialization step.
