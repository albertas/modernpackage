# Task

Audit that cyclomatic complexity stays at or below 8 across the package
(`modernpackage/`) and `tests/`, enforced via `just check-complexity`
(which runs `ruff check --select C901`). The McCabe threshold must be
configured so the rule actually fails on functions whose complexity exceeds 8,
rather than relying on Ruff's default of 10.
