# modernpackage — Documentation Index

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset. This index provides navigation to all project documentation.

## What It Does

`modernpackage` is a standalone package that, when invoked as `modernpackage <name>` or `mp <name>`, clones itself to a new directory and rewrites all occurrences of "modernpackage" to the given package name. The result is a ready-to-build Python package with:

- Modern tooling: **ruff** (linting, formatting), **mypy** (type checking), **pytest** (testing), **pip-audit** (vulnerability scanning)
- Single configuration hub via `pyproject.toml` with strict settings (line-length 88, strict mypy, 50% test coverage minimum)
- Development workflow via `Makefile` and `Justfile` for common tasks: `check`, `fix`, `test`, `lint`, `format`, `publish`
- GitHub Actions and GitLab CI integration that enforce quality gates

## Documentation Files

| File | Purpose |
|------|---------|
| [specification.md](specification.md) | **Complete architectural reference**: package goals, modules, CLI entry point, initialization flow, build/versioning, developer tooling, tests, repository structure, known gaps. Start here for deep understanding. |
| [README.md](../README.md) | User-facing usage guide and feature-request backlog. |
| [BACKLOG.md](../BACKLOG.md) | Task tracking with progress markers (`[x]` complete, `[~]` in-progress, `[ ]` pending). |

## Development Workflow

After cloning and `cd`-ing into the created package directory, developers use:

- **`make check`** — run all code quality gates in sequence: unit tests, ruff lint, ruff format check, mypy, pip-audit, deadcode detection. Primary quality gate; used in CI/CD.
- **`make fix`** — format code and auto-fix linting issues.
- **`make test`** — run pytest unit tests.
- **`make lint`** — check for linting violations.
- **`make format`** — reformat code with ruff.
- **`make mypy`** — run type checker.
- **`make audit`** / **`make deadcode`** — run security and dead-code scanners.
- **`make publish`** — build and publish to PyPI.

Alternatively, use equivalent **`just` targets** (Justfile) for the same commands:

- **`just check`** — runs `check-format check-lint check-complexity check-typecheck test`
- **`just test`** — runs `uv run pytest`
- **`just format`** — runs `uv run ruff format modernpackage tests`
- **`just lint`** — runs `uv run ruff check modernpackage tests`
- **`just typecheck`** — runs `uv run mypy modernpackage tests`
- **`just check-format`**, **`just check-lint`**, **`just check-complexity`**, **`just check-typecheck`** — individual check sub-steps

Both `Makefile` and `Justfile` targets depend on synced dependencies (dev and test extras).

## Key Implementation Details

- **Single-file CLI**: `modernpackage/main.py` handles argument parsing and orchestrates `git clone` + `make init`.
- **Package replication**: the `Makefile init` target uses `git grep + sed` to rename all "modernpackage" occurrences to the new package name, resets version to `0.0.1`, and reinitializes git.
- **Configuration-as-code**: all tool settings live in `pyproject.toml` (ruff, mypy, pytest, deadcode, pip-audit); the Makefile and Justfile delegate to them via `uv run`.
- **Private index**: GitLab private package index configured for pulling internal dependencies.

## Known Gaps & Future Work

See [specification.md § Known gaps & divergences](specification.md#known-gaps--divergences) for:
- No error handling in `init_new_package()` — cloning/initialization failures are silently discarded.
- Version drift between `__init__.py` and published wheels.

See [BACKLOG.md](../BACKLOG.md) for planned improvements: coverage measurement, deterministic tests with pytest-xdist, latest Python/dependency versions, merge Makefile and Justfile, uv-based publishing.

## Next Steps

- To understand the codebase in detail, read [specification.md](specification.md).
- To report issues or request features, see [BACKLOG.md](../BACKLOG.md) and [README.md § Feature requests](../README.md#feature-requests).
- To contribute, ensure `just check` (or `make check`) passes before opening a pull request.
