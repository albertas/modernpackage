# Task: Audit ruff lint is clean (cq:ruff-lint)

Ensure `ruff check` runs clean across `modernpackage/` and `tests/` with most
ruff linting rules enabled (`select = ["ALL"]`), and that `just check-lint`
reports no errors and no warnings. The lint configuration in `pyproject.toml`
currently emits a warning about the removed `ANN101` rule in its ignore list,
which must be cleaned up so the audit passes cleanly.
