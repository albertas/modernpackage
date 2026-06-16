# Task

Audit that `ruff format` is clean across the codebase and bring it into
compliance. `just check-format` currently fails because
`modernpackage/main.py` is not formatted to `ruff format` standards; the goal
is for `just check-format` to pass with all files reported as already
formatted.
