# modernpackage — Documentation Index

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset. This index provides navigation to all project documentation.

## What It Does

`modernpackage` is a standalone package that, when invoked as `modernpackage <name>` or `mp <name>`, clones itself to a new directory and rewrites all occurrences of "modernpackage" to the given package name. The result is a ready-to-build Python package with:

- **Modern tooling**: **ruff** (linting, formatting, complexity auditing), **mypy** (strict type checking), **pytest** (testing with parallel execution), **pip-audit** (vulnerability scanning), **deadcode** (unused code detection)
- **Single configuration hub** via `pyproject.toml` with strict settings (line-length 88, strict mypy with full type annotations verified, 95% test coverage minimum, cyclomatic complexity ≤ 8)
- **Comprehensive test coverage** (95% minimum) ensuring all code paths are exercised deterministically and in parallel across all-but-one CPU cores with fully mocked dependencies
- **Development workflow** via `Justfile` for common tasks: `check`, `fix`, `test`, `test-e2e`, `lint`, `format`, `typecheck`, `publish`, `audit`, `deadcode`
- **GitHub Actions and GitLab CI integration** that enforce quality gates
- **Full type hints** on all public functions with mypy strict mode enabled and passing

## Documentation Files

| File | Purpose |
|------|---------|
| [invocation.md](invocation.md) | **CLI usage**: entry points, command-line flags, argument validation, examples. |
| [architecture.md](architecture.md) | **Design & modules**: package structure, module responsibilities, init flow, build & versioning, developer tooling, test strategy. |
| [backlog_formats.md](backlog_formats.md) | **Task tracking format**: BACKLOG.md structure, progress markers, category tags. |
| [specification.md](specification.md) | **Complete architectural reference**: package goals, modules, CLI entry point, initialization flow, build/versioning, developer tooling, tests, repository structure, known gaps. Start here for deep understanding. |
| [README.md](../README.md) | User-facing usage guide and feature-request backlog. |
| [BACKLOG.md](../BACKLOG.md) | Task tracking with progress markers (`[x]` complete, `[~]` in-progress, `[ ]` pending). |

## Development Workflow

After cloning and `cd`-ing into the created package directory, developers use `just` commands via the canonical `Justfile`:

- **`just check`** — run all code quality gates in sequence: format check, ruff lint, complexity audit, mypy type check, unit tests, pip-audit security scan, deadcode detection. Primary quality gate; used in CI/CD.
- **`just fix`** — format code and auto-fix linting issues.
- **`just compile`** — regenerate and upgrade all dependency artifacts: `requirements.txt`, `requirements-dev.txt`, and `uv.lock` to the latest versions available.
- **`just test`** — run pytest unit tests in parallel across `nproc --ignore=1` workers (mocked-only, excludes e2e).
- **`just test-e2e`** — run only tests marked `@pytest.mark.e2e` (reserved for real external calls).
- **`just lint`** — check for linting violations.
- **`just format`** — reformat code with ruff.
- **`just typecheck`** — run type checker (mypy in strict mode).
- **`just audit`** — run security vulnerability scanner (pip-audit).
- **`just deadcode`** — detect unused code.
- **`just publish`** — build and publish to PyPI via `uv build` + `uv publish`.

Individual check sub-steps are also available:

- **`just check-format`**, **`just check-lint`**, **`just check-complexity`**, **`just check-typecheck`** — individual check-only steps (no auto-fix)
- **`just fix-lint`** — auto-fix linting and deadcode issues

`Justfile` recipes depend on synced dependencies (dev and test extras) via the `just sync` prerequisite.

## Key Implementation Details

- **Single-file CLI**: `modernpackage/main.py` handles argument parsing and orchestrates `git clone` + `just init`. Both the `git clone` and `just init` steps capture stderr and check for errors (non-zero exit codes), raising `RuntimeError` with detailed error output on failure (including stderr from the failed subprocess). Errors are caught in `main()` and printed to stderr as clean messages, providing visibility into failures without Python tracebacks.
- **Package replication**: the `just init` recipe uses `git grep + sed` to rename all "modernpackage" occurrences to the new package name, resets version to `0.0.1`, and reinitializes git.
- **Configuration-as-code**: all tool settings live in `pyproject.toml` (ruff, mypy, pytest, deadcode, pip-audit); the Justfile delegates to them via `uv run`.
- **Dependency compilation workflow**: `just compile` regenerates all three dependency artifacts in lockstep (`requirements.txt`, `requirements-dev.txt`, `uv.lock`) to ensure they always agree on shared package versions and are upgraded to the latest versions available in the GitLab index.
- **Private index**: GitLab private package index configured for pulling internal dependencies; dependency resolution is capped by what this index serves, which may lag behind PyPI.

## Known Gaps & Future Work

See [specification.md § Known gaps & divergences](specification.md#known-gaps--divergences) for:
- Version drift between `__init__.py` and published wheels.

See [BACKLOG.md](../BACKLOG.md) for planned improvements: coverage measurement, deterministic tests with pytest-xdist, latest Python/dependency versions, uv-based publishing.

## Next Steps

- To understand the codebase in detail, read [specification.md](specification.md).
- To report issues or request features, see [BACKLOG.md](../BACKLOG.md) and [README.md § Feature requests](../README.md#feature-requests).
- To contribute, ensure `just check` passes before opening a pull request.
