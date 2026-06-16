# Task: Audit mypy type-checking passes

Ensure static type-checking via mypy passes cleanly across the package and tests.
The `just check-typecheck` recipe runs `mypy modernpackage tests` under strict
configuration; the goal is for it to report no issues, adding type hints in the
code wherever they are missing so the audit succeeds.
