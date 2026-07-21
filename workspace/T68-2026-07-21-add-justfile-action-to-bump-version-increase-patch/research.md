# Research Findings

## Q1: Where is the version defined/stored, and how is it wired into the build backend?

### Findings
- Canonical version string lives in `modernpackage/__init__.py:3`: `__version__ = '0.0.9'`.
- Build backend is Hatchling: `pyproject.toml:47-48` (`requires = ["hatchling"]`, `build-backend = "hatchling.build"`).
- Version is declared **dynamic**, not static, in `pyproject.toml:24`: `dynamic = ["version"]` (no `version = ` key under `[project]`).
- Hatchling reads the version from the `__init__.py` via `pyproject.toml:54-55`: `[tool.hatch.version]` with `path = "modernpackage/__init__.py"`. Hatchling extracts the `__version__ = '...'` assignment from that file at build time.
- Runtime consumers import it: `modernpackage/main.py:17` (`from modernpackage import __version__`) and print it at `main.py:1024` (`print(f'modernpackage {__version__}')`).

## Q2: What does the `publish` recipe (and related build/release recipes) do step by step?

### Findings
`Justfile:53-57`, recipe `publish` (no `sync` dependency, unlike most recipes):
1. `git push` — with inline comment noting modernpackage clones code from GitLab, so updated code must be on both GitLab and PyPI for release.
2. `rm -fr dist/*` — clears the `dist/` directory.
3. `uv build` — builds sdist/wheel via the Hatchling backend.
4. `uv publish` — uploads to the index.
- No version-bump step exists inside `publish`; it publishes whatever `__version__` currently is.
- Related build/lock recipes: `compile` → `uv lock` (`Justfile:9-10`); `lock` → `uv lock --upgrade` (`Justfile:73-74`); `sync` → `uv sync` (`Justfile:6-7`).
- No git commands appear anywhere else in the Justfile except `publish`'s `git push` and the `init` recipe's `git init`/`git add`/`git commit` (`Justfile:69-71`).

## Q3: Existing patterns for reading/parsing/rewriting the version string; where is a version hardcoded/reset?

### Findings
- **sed rewrite in Justfile** (`init` recipe, `Justfile:67`): `@sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py` — resets any `N.N.N` version to `0.0.1`. macOS/Linux name-rename sed lives separately at `Justfile:61-66`.
- **Python does NOT rewrite the version file.** No `re.sub`, no file write to `__init__.py` in `modernpackage/main.py`. The scaffolder only *documents/reports* the reset via a hardcoded constant.
- Hardcoded reset constant: `modernpackage/main.py:649` `_RESET_VERSION: str = '0.0.1'`. Its comment (`main.py:647-648`) explicitly says it "mirrors the Justfile sed value at Justfile:67; coupled by convention, not programmatically."
- `_RESET_VERSION` is only used for display in dry-run plan (`main.py:709`) and init summary (`main.py:757`), not to write files.
- Scaffolding stub hardcodes `0.0.1`: `_TEST_MAIN_STUB` (`main.py:516-522`) writes a `tests/test_main.py` asserting `__version__ == '0.0.1'`.

## Q4: Conventions existing Justfile recipes follow (deps, `sync`, shell, invoking Python/tools).

### Findings
- Most task recipes declare a `sync` prerequisite: `test *args: sync`, `format: sync`, `lint: sync`, `typecheck: sync`, `check-format: sync`, etc. (`Justfile:12`, `18`, `21`, `24`, ...). `sync` itself runs `@uv sync` (`Justfile:6-7`).
- Recipes that do NOT depend on `sync`: `lifecycle`, `vision`, `compile`, `publish`, `init`, `lock` (they either sync inline or don't need the venv).
- Project code / tools are invoked through `uv run <tool>`: `uv run pytest`, `uv run ruff ...`, `uv run mypy ...`, `uv run pip-audit`, `uv run lifecycle`, `uv run vision` (`Justfile:2-3`, `13`, `19`, `22`, `28`, ...).
- Recipe arguments use just's `{{args}}` / `{{package_name}}` interpolation (`Justfile:12`, `59`). Variadic args via `*args`.
- Aggregate recipes chain other recipes as dependencies: `check: check-format check-lint check-complexity check-typecheck test audit` (`Justfile:51`); `fix: format fix-lint` (`Justfile:48`); `e: test-e2e` (`Justfile:15`).
- Multi-line shell logic uses `\`-continued `if`/`while` blocks with `@` to suppress echo, and OS branching on `$(uname)` = Linux/Darwin (`init` recipe `Justfile:59-72`; `lifecycle` `Justfile:1-3`).
- Package name passed via recipe default parameter: `init package_name="modernpackage":` (`Justfile:59`).

## Q5: Version-manipulation tooling already available (hatch/uv version) and how invoked.

### Findings
- Build backend `hatchling` is present (`pyproject.toml:47`), but the standalone `hatch` CLI (which has `hatch version`) is **not** in `[dependency-groups].dev` (`pyproject.toml:34-43`: ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi). Only `hatchling` (the backend library) is available, invoked implicitly by `uv build`.
- `uv` is the project driver (used throughout the Justfile). `uv version` subcommand exists and supports `--bump {major,minor,patch,...}`, `--dry-run`, `--short`, `--no-sync` (verified via `uv version --help`).
- **However `uv version` fails on this project** because the version is dynamic: running `uv version` or `uv version --bump patch --dry-run` returns `error: We cannot get or set dynamic project versions in: pyproject.toml`. So `uv version` cannot currently read/bump the version given `dynamic = ["version"]` + `[tool.hatch.version]` sourcing from `__init__.py`.
- The only version-mutation mechanism currently invoked anywhere is the raw `sed` in the `init` recipe (`Justfile:67`).

## Q6: How the version is referenced/asserted in tests and scaffolding, for consistency.

### Findings
- `tests/test_main.py:10` imports `from modernpackage import __version__`.
- `tests/test_main.py:52` asserts the `--version` output: `print_mock.assert_called_once_with(f'modernpackage {__version__}')` (uses the live value, not a literal).
- `tests/test_main.py:118-121` `test_parse_args_version_flag` checks `result.version is True` for the `--version` flag.
- Scaffolding-related tests assert the reset literal `'0.0.1'`:
  - `tests/test_main.py:566`, `591` — init summary / printed output contains `0.0.1`.
  - `tests/test_main.py:1100` — test writes `(tmp_path / 'modernpackage' / '__init__.py').write_text("__version__ = '0.0.1'\n")`.
  - `tests/test_main.py:1126-1127` — generated stub contains `0.0.1` and `def test_version`.
  - `tests/test_main.py:1236` — dry-run plan text contains `0.0.1`.
- E2E tests assert the reset literal after real `just init`:
  - `tests/test_e2e.py:188` — `assert '0.0.1' in init_file.read_text()` (the scaffolded `__init__.py`).
  - `tests/test_e2e.py:211-213` — generated stub test contains `0.0.1`.
- Scaffolder's own embedded stub asserts `assert __version__ == '0.0.1'` (`modernpackage/main.py:520-521`).
- The `_RESET_VERSION = '0.0.1'` constant (`main.py:649`) must stay in sync with the Justfile sed literal (`Justfile:67`) — coupling is by convention/comment, not enforced.

## Cross-Cutting Observations
- Single source of truth for the live version is `modernpackage/__init__.py:3`; everything else imports it or (for the scaffold-reset path) hardcodes `0.0.1`.
- Two independent representations of the "reset to 0.0.1" fact exist and are manually kept in sync: `Justfile:67` (sed) and `modernpackage/main.py:649` (`_RESET_VERSION`, display-only).
- The dynamic-version + Hatchling setup means Hatchling reads `__init__.py` at build; `uv version` is incompatible with it (Q5). Any programmatic bump would currently target `modernpackage/__init__.py` directly (as the sed already does), not `pyproject.toml`.
- Justfile idioms for a new recipe: optionally `: sync`, invoke tooling via `uv run`, `@`-prefix to silence, `{{...}}` for params, chain recipes as deps.

## Open Areas
- No existing recipe bumps the version; there is no prior art for "increment patch" in the repo beyond the reset-to-`0.0.1` sed. Whether a bump should edit `__init__.py` (consistent with current sourcing) vs. switch to static `[project] version` is a design question, not answerable from current code.
