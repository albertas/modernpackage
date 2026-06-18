# modernpackage — Documentation Index

`modernpackage` is a self-replicating CLI scaffolder for new Python packages using a strict, modern toolset. This index provides navigation to all project documentation.

## What It Does

`modernpackage` is a standalone package that, when invoked as `modernpackage <name>` or `mp <name>`, validates the package name, verifies required tools are on PATH, checks that the target directory does not already exist, clones itself to a new directory, removes the scaffolder's own CLI, tests, and documentation, and rewrites all occurrences of "modernpackage" to a normalized module name (converting hyphens and dots to underscores for import-safety). On successful scaffolding, it prints a summary block showing the created package name, directory path, and version (0.0.1) to stdout after the validation passes, followed by a "next steps" hint suggesting the user run `cd <module_name> && just check` to continue development. A `--dry-run` flag is available to preview what scaffolding would do without making any changes. The result (when scaffolding proceeds) is a clean, ready-to-build Python package with:

- **Input validation**: Package names are validated to match PEP 508 / PyPI distribution names with specific, actionable error messages (empty name, disallowed character, leading/trailing separator, or stdlib collision). Validation rejects invalid names and stdlib collisions before any scaffolding begins. Optional metadata flags (`--author-name`, `--author-email`, `--description`, `--license`, `--repository-url`) are also validated at parse time (email and URL formats are checked; free-string metadata is unconstrained). When flags are omitted, values fall back in precedence order: first to corresponding environment variables (`MODERNPACKAGE_AUTHOR_NAME`, `MODERNPACKAGE_AUTHOR_EMAIL`, `MODERNPACKAGE_DESCRIPTION`, `MODERNPACKAGE_LICENSE`, `MODERNPACKAGE_REPOSITORY_URL`), then (for `author-name` and `author-email` only) to the user's git config (`user.name` and `user.email`). Environment-sourced and git-config-sourced email and URL values are validated with the same rules as flag-supplied values
- **Clean package generation**: The scaffolder clones the template repository, removes the scaffolder's own CLI (`modernpackage/main.py`), scaffolder tests (`tests/test_e2e.py`), documentation (`docs/`), and project-metadata files (`BACKLOG.md`), replaces the template's README and test suite with minimal stubs compatible with the generated package, and removes the scaffolder's entry points (`[project.scripts]`). This ensures generated packages are clean, minimal, and ready for user customization without inheriting the scaffolder machinery
- **Preflight checks with checklist**: Before any git clone or filesystem mutation, the scaffolder runs a series of preflight checks in order and prints a concise, one-line-per-check checklist to stdout showing each check's outcome (`[ok]` or `[FAIL]`). The checks include: verify all required tools (`git`, `just`, `uv`) are on PATH, verify the target package directory does not already exist, and verify the template remote is reachable (via a `git ls-remote` probe with a timeout). If any check fails, the checklist is printed up to and including the failing check (with `[FAIL]` marker), the error message is printed to stderr, and scaffolding aborts before any clone subprocess is spawned or any directory is created. If all checks pass, the full `[ok]` checklist is printed and scaffolding proceeds
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
- **`just test-e2e`** — run only the end-to-end test marked `@pytest.mark.e2e` (real external calls: scaffolds a package and runs `just check` on it).
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

- **Preflight checks with checklist**: Before any scaffolding begins (before cloning or creating any directories), `init_new_package()` performs a series of preflight checks and prints a checklist to stdout:
  1. **Checklist orchestrator** via `_run_preflight_checks()`: orchestrates a registry of checks, prints a header line (`Preflight checks:`), runs each check in order, and prints one indented line per check showing its outcome (`[ok]` or `[FAIL]`). If any check raises `RuntimeError`, the failing line is marked `[FAIL]`, the error is re-raised (and caught in `main()` to print to stderr), and subsequent checks never run. If all checks pass, the full checklist is printed with all `[ok]` markers and scaffolding proceeds to the clone step.
  2. **Tool verification** via `_verify_required_tools()`: verifies that `git`, `just`, and `uv` are all available on `PATH` via `shutil.which()`. If any tool is missing, raises `RuntimeError` with a per-tool install hint: one line per missing tool showing its canonical install URL (e.g., `git` → `https://git-scm.com/downloads`, `uv` → `https://docs.astral.sh/uv/getting-started/installation/`, `just` → `https://github.com/casey/just#installation`). The message names all absent tools and provides specific remediation URLs without creating the target directory or running any subprocess. This fail-fast approach with actionable hints prevents confusing late failures.
  3. **Target directory check** via `_verify_target_directory_absent()`: verifies that the computed target package directory does not already exist (file or directory). If the path exists, raises `RuntimeError` with a clear, actionable message suggesting the user choose a different package name or remove the existing directory. This prevents git clone from failing with a cryptic error message.
  4. **Template remote reachability** via `_verify_template_remote_reachable()`: verifies that the template repository is reachable by running `git ls-remote` with a timeout. If the remote is unreachable (network error, not found, authentication failed, etc.), raises `RuntimeError` with a friendly, actionable message and raw stderr details for diagnostics.
- **Module name normalization**: The CLI accepts PEP 508 / PyPI distribution names (which may contain hyphens and dots, e.g., `my-cool.package`). Before cloning and initialization, the name is normalized to a valid Python module identifier by replacing hyphens and dots with underscores (e.g., `my_cool_package`). This normalized name is used for the clone directory, the `just init` argument, and all printed messages, ensuring that the created directory and all Python import paths are valid identifiers.
- **Precise validation diagnostics**: When package name validation fails, the `_explain_invalid_package_name()` helper provides specific, actionable error reasons (empty name, disallowed character, leading/trailing separator) in precedence order, so users know exactly what to fix. The stdlib collision check remains separate and unchanged.
- **Optional metadata flags**: Five optional flags allow recording package metadata at scaffolding time: `--author-name`, `--author-email`, `--description`, `--license`, and `--repository-url`. Email and URL formats are validated at parse time (permissive regex patterns); free-string fields are unconstrained. Invalid metadata causes exit code 2 before any scaffolding. When omitted, flags fall back to dedicated environment variables (`$MODERNPACKAGE_AUTHOR_NAME`, etc.); environment-sourced values are validated with the same rules as flag-supplied values, and invalid env values exit cleanly with a CLI error instead of a traceback. File-sourced values rank below git config as the weakest source (`flag > env > git config > config file > None` for name/email, `flag > env > config file > None` for the rest), read from a flat-key TOML file at `$XDG_CONFIG_HOME/modernpackage/config.toml` (fallback `~/.config/modernpackage/config.toml`); malformed files print a notice to stderr and continue. All five environment variables are advertised in the `--help` output. The metadata is automatically written to the generated package's `pyproject.toml` file: supplied values are applied as targeted TOML-escaped `str.replace()` substitutions of known template placeholders after cloning and before `just init`, ensuring the metadata appears in the initial git commit. When omitted (value is `None`), the corresponding placeholder remains untouched.
- **Single-file CLI**: `modernpackage/main.py` handles argument parsing and orchestrates `git clone` + `just init` + `just check`. The first two steps capture stderr and check for errors (non-zero exit codes). On `git clone` failure, common error patterns are recognized and mapped to actionable messages (e.g., "repository unreachable — check your network connection"), followed by the raw stderr for diagnostics. Unknown errors fall back to the raw stderr. Both `git clone` and `just init` failures raise `RuntimeError` with detailed error output. The `just check` step validates the newly scaffolded package against all quality gates and reports the outcome: a success message (`'just check passed — {module_name} scaffold is valid.'`) is printed to stdout, followed by a summary block showing the created package name, directory path, and reset version, and a "next steps" hint suggesting `cd {module_name} && just check` to continue development if all gates pass, or a failure message (`'just check failed with exit code {returncode} — review the output in {module_name}.'`) is printed to stderr if any gate fails. The `just check` result is now propagated via the return code: `init_new_package()` returns 0 on success and 1 on validation failure. Errors from `git clone` or `just init` are caught in `main()` and printed to stderr as clean messages, providing visibility into failures without Python tracebacks. The `main()` function returns an integer exit code (0 for success including validation success, 1 for any failure including validation failure), which is translated to the process exit status by the console script entry point wrapper, allowing CI/CD pipelines to reliably detect failures.
- **Scaffolding removal**: After cloning the template but before the rename step, `_strip_scaffolding()` removes the scaffolder's own machinery from the cloned tree — deleting `main.py` (the self-replicating CLI), the end-to-end test (`test_e2e.py`), the `docs/` directory, and `BACKLOG.md` (project-metadata). It rewrites `tests/test_main.py` with a minimal one-test stub that imports the package version (satisfying the minimum test collection requirement and coverage gate), replaces `README.md` with a generic template, and removes the `[project.scripts]` entry points table from `pyproject.toml` to avoid dangling console-script entries. Deletions are tolerated if files are absent (graceful degradation for different template shapes). This stripping happens **before** the rename sed and git commit in `just init`, so the initial commit captures a clean tree without the scaffolder machinery.
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
