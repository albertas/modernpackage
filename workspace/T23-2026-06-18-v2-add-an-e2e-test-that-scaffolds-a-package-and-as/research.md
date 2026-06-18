# Research Findings

## Q1: Package-scaffolding flow end to end

### Findings
- Entry point: `init_new_package(package_name)` at `modernpackage/main.py:83`.
  - Computes destination `new_package_path = Path.cwd() / package_name` (`main.py:85`).
  - Step 1 — git clone: `Popen(['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path], ...)` (`main.py:87-92`). The new package's files come from the **GitHub repo `albertas/modernpackage`** (hardcoded URL), not the local checkout.
  - Captures stderr via `communicate()`; on `returncode != 0` builds a raw message and an optional humanized one (`humanize_git_clone_error`, `main.py:47-53`) and raises `RuntimeError` (`main.py:93-100`).
  - Step 2 — `just init`: `Popen(['just', 'init', package_name], cwd=new_package_path)` (`main.py:103-108`). `FileNotFoundError` (just not installed) → `RuntimeError` with install hint (`main.py:110-115`). Non-zero exit → `RuntimeError` (`main.py:119-121`).
- CLI orchestration: `main()` (`main.py:124-138`) calls `init_new_package`, catches `RuntimeError`, prints to stderr, returns `1` on failure else `0`.
- `Justfile` `init` recipe (`Justfile:59-73`), runs inside the cloned dir with arg `package_name` (default `"modernpackage"`):
  1. `@echo "Initializing ..."` (`:60`).
  2. Linux: `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'` (`:61-63`); Darwin variant uses `sed -i ''` (`:64-66`). Renames all references in tracked files.
  3. `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py` — resets version to `0.0.1` (`:67`).
  4. `mv modernpackage {{package_name}}` — renames the package directory (`:68`).
  5. `rm -fr .git/ .venv` (`:69`), then `git init -b main .`, `git add .`, `git commit -m "Initial modern {{package_name}} package setup"` (`:70-72`).
  6. Final success echo with green-colored next-step hint (`:73`).
- Note: `init` depends on a populated `.git` (uses `git grep`); the clone provides it, and the recipe removes it before re-initializing.

## Q2: The `e2e` test marker — definition and wiring

### Findings
- Registered in `pyproject.toml:41-43` under `[tool.pytest.ini_options] markers`:
  `"e2e: tests that perform real external calls (network/subprocess/fs)"`.
- Default run excludes e2e: `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"` (`pyproject.toml:40`). So `just test` / plain `pytest` skip e2e tests.
- `just test *args` (`Justfile:13-14`): `uv run pytest -n "$(nproc --ignore=1)" {{args}}` — inherits `addopts` (`-m 'not e2e'`), runs under xdist.
- `just test-e2e *args` (`Justfile:16-17`): `uv run pytest -m e2e {{args}}` — a later `-m e2e` on the command line overrides the `-m 'not e2e'` from `addopts`, selecting only e2e-marked tests. Not run under `-n` (no xdist parallelism).
- **No e2e-marked tests currently exist**: `tests/` contains only `tests/__init__.py` and `tests/test_main.py`; grep for `e2e`/`@pytest.mark` in `tests/` returns no matches.

## Q3: Existing test patterns (isolation, subprocess, mocking)

### Findings
- All tests live in `tests/test_main.py`; only test file (`git ls-files tests/`). No `conftest.py`.
- Mocking via `unittest.mock` (`from unittest.mock import MagicMock, patch`, `test_main.py:2`). No `pytest-mock`.
- **Subprocess is fully mocked, never real**: `patch('modernpackage.main.Popen')` patches the seam on the `main` module object (`test_main.py:49,57,68,81,178`). Mocks set `.return_value.returncode` and `.communicate.return_value = (stdout_bytes, stderr_bytes)`.
  - Multiple sequential subprocess calls simulated with `popen_mock.side_effect = [git_clone_mock, just_init_mock]` (`test_main.py:69,82`).
  - `FileNotFoundError` simulated to test "just not installed" path (`test_main.py:69`).
- Other patched seams: `ArgumentParser`, `print`, `init_new_package`, all on `modernpackage.main` (`test_main.py:18-19,89-90,102-104`); `sys.argv` patched for `parse_args` tests (`test_main.py:37,43`).
- **No filesystem isolation patterns present**: no `tmp_path`, `tmpdir`, or `monkeypatch` usage anywhere in `tests/` (grep: no matches). No test creates real files/dirs; `init_new_package` is only exercised with mocked `Popen`.
- Assertions use plain `assert` and `pytest.raises(..., match=...)` (per `pyproject.toml:76` per-file-ignore `S101`/`D` for tests).
- Pattern of testing pure helpers directly: `check_alpha_numeric`, `humanize_git_clone_error` called with literal strings (`test_main.py:27-33,141-189`).

## Q4: `just check` and its sub-steps

### Findings
- `check: check-format check-lint check-complexity check-typecheck test audit` (`Justfile:52`). `deadcode` is commented out.
- Every sub-recipe lists `sync` as a dependency (runs env sync first; see Q6).
- `check-format` (`Justfile:28-29`): `uv run ruff format --check modernpackage tests` — fails if files are not already formatted. Config: `[tool.ruff.format]` single quotes, `docstring-code-format` (`pyproject.toml:62-64`), line-length 88 (`:57`).
- `check-lint` (`Justfile:31-32`): `uv run ruff check modernpackage tests`. Config: `select = ["ALL"]` with a few ignores (`pyproject.toml:66-73`); tests ignore `S101`,`D` (`:75-76`). Requires zero lint violations.
- `check-complexity` (`Justfile:34-35`): `uv run ruff check --select C901 modernpackage tests`. McCabe `max-complexity = 8` (`pyproject.toml:78-79`); fails if any function exceeds 8.
- `check-typecheck` (`Justfile:37-38`): `uv run mypy modernpackage tests`. `[tool.mypy]` `strict = true`, `python_version = "3.14"`, `warn_return_any`, `warn_unused_configs`, excludes build/dist/.venv (`pyproject.toml:81-89`).
- `test` (`Justfile:13-14`): `uv run pytest -n "$(nproc --ignore=1)"`; needs `nproc` (coreutils). Coverage gate via `addopts`: `--cov-fail-under=95.0` and `--no-cov-on-fail` (`pyproject.toml:40`) — fails if coverage < 95%. `-m 'not e2e'` excludes e2e tests from this gate.
- `audit` (`Justfile:40-41`): `uv run pip-audit --skip-editable` — scans installed dependencies for known vulnerabilities (`--skip-editable` skips the local editable package). Requires network to the PyPI advisory database.

## Q5: Steps depending on external resources

### Findings
- **Scaffolding (`init_new_package`)**:
  - `git clone https://github.com/albertas/modernpackage` (`main.py:88`) → requires **network + GitHub remote + `git` binary on PATH**. Failure modes humanized in `_GIT_CLONE_ERROR_MESSAGES` (`main.py:12-44`: unreachable host, repo not found, auth, dir exists, fs permissions).
  - `just init` (`main.py:103-108`) → requires **`just` binary** (missing → `RuntimeError`, `main.py:110-115`); the recipe itself shells out to `git grep`/`sed`/`mv`/`rm`/`git init/add/commit` (`Justfile:61-72`) → requires **`git`, `sed`, coreutils**.
- **`just check` / recipes**:
  - All recipes run `uv` (`Justfile`, every `uv run ...`) and the `sync` prerequisite → require **`uv` installed** and **network/package index** to install deps.
  - `audit` (`pip-audit`) → **network** to fetch the vulnerability database.
  - `test` → requires `nproc` (`Justfile:14`).
  - CI installs `just` via `uv tool install rust-just` and runs `just sync` then `just check` (`.gitlab-ci.yml:13-22`, `.github/workflows/check-modernpackage-on-python314.yml:26-34`).
- **Package index configuration**: extra uv index `gitlab` at `https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple` (`pyproject.toml:97-99`) — used to resolve `vupi` and other deps during `sync`.
- Repo notes an offline/connectivity concern: `issues/no_internet_connection_message` exists (file in repo root listing).

## Q6: Python environment & dependency management

### Findings
- `sync` recipe (`Justfile:9-11`): `@uv pip sync requirements-dev.txt` then `@uv pip install -e .[test]`. It is the prerequisite of test/format/lint/typecheck/audit/check recipes.
- `requirements.txt` (`requirements.txt:1-2`) is **empty of packages** — only the uv autogen header (project has no runtime `dependencies`, `pyproject.toml:18`).
- `requirements-dev.txt` (autogenerated by `uv pip compile --all-extras`) pins the full dev/test dependency tree (`requirements-dev.txt:1-199`), including `pytest==9.1.0`, `pytest-cov`, `pytest-xdist`, `ruff`, `mypy`, `pip-audit`, `deadcode`, `vupi`, etc.
- Optional dependency group `test` (`pyproject.toml:27-37`): `ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi>=0.0.7`. Installed editable via `uv pip install -e .[test]`.
- Lockfile `uv.lock` present (177KB). `requires-python = ">= 3.14"` (`pyproject.toml:8`); mypy `python_version = "3.14"` (`pyproject.toml:83`).
- `compile` recipe (`Justfile:75-78`) regenerates `requirements.txt`, `requirements-dev.txt` (`--all-extras`), and `uv lock --upgrade`.
- Build backend: `hatchling`; version sourced dynamically from `modernpackage/__init__.py` (`pyproject.toml:45-54`); `__version__ = '0.0.9'` (`modernpackage/__init__.py:3`). Build excludes `tests/**` (`pyproject.toml:49-51`).
- `lifecycle`/`vision` recipes (`Justfile:1-7`) drive the `vupi`/`uv run lifecycle` tooling, also gated on `uv pip sync`.

## Cross-Cutting Observations
- Subprocess seam is consistently `modernpackage.main.Popen`; tests patch it on the module object, matching the project convention (CLAUDE.md / Code Best Practices: patch the SDK/subprocess seam on the defining module).
- The e2e marker exists and the `test-e2e` recipe is wired, but **no e2e test exists yet** — the infrastructure (marker registration, exclusion from default run, separate recipe) is in place and unused.
- Real external dependencies for a true end-to-end scaffolding run: network → GitHub clone, plus `git`, `just`, `uv`, `sed`, coreutils on PATH. Current unit tests avoid all of these by mocking `Popen`.
- Quality gate (`just check`) is strict: ruff ALL-rules lint, format check, McCabe ≤ 8, mypy strict on 3.14, ≥95% coverage (excluding e2e), and a networked pip-audit.

## Open Areas
- No existing e2e test or filesystem-isolation fixture to model from; `tmp_path`/`monkeypatch` are unused in the suite (would be new patterns if introduced).
- Behavior of `pytest -m e2e` overriding `addopts`'s `-m 'not e2e'` is inferred from pytest's last-`-m`-wins semantics; not directly demonstrated by an existing e2e test in the repo.
