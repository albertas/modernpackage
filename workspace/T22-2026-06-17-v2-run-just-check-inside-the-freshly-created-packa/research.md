# Research Findings

## Q1: How does `init_new_package` orchestrate its external commands?

### Findings
- `init_new_package(package_name)` is defined at `modernpackage/main.py:83-121`.
- Computes target dir as `Path.cwd() / package_name` (`main.py:85`).
- **Two sequential `Popen` calls**, no `subprocess.run`:
  1. **git clone** (`main.py:87-92`): args `['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path]`; `stdin=PIPE, stdout=PIPE, stderr=PIPE`; no `cwd` (runs in current dir). `# noqa: S603`/`S607` suppress bandit warnings.
  2. **just init** (`main.py:103-109`): args `['just', 'init', package_name]`; same three pipes; `cwd=new_package_path` so it runs *inside* the freshly cloned directory.
- Each call drives I/O via `pipe.communicate()` (`main.py:93`, `116`); only stderr is used — stdout is discarded into `_stdout`.
- stderr is decoded and stripped: `stderr_text = stderr.decode().strip()` (`main.py:94`, `117`).
- Return codes checked via `pipe.returncode != 0` after each step (`main.py:96`, `119`).
- The second `Popen` is wrapped in `try/except FileNotFoundError` (`main.py:110-115`) to detect a missing `just` binary before `communicate()` is reached.

## Q2: Conventions for subprocess failure handling/reporting

### Findings
- **Failures raise `RuntimeError`** (never sys.exit inside `init_new_package`):
  - git clone non-zero: builds `raw = f'git clone failed with exit code {returncode}: {stderr_text}'`, then prepends a friendly message if available (`main.py:96-100`).
  - just init non-zero: `f'just init failed with exit code {returncode}: {stderr_text}'` (`main.py:119-121`).
  - missing `just`: `RuntimeError(...) from error` with install hint + URL (`main.py:110-115`).
- **stderr is always surfaced** by embedding the captured `stderr_text` into the exception message.
- **`humanize_*` helper**: `humanize_git_clone_error(stderr_text)` (`main.py:47-53`) lowercases stderr and matches against the ordered `_GIT_CLONE_ERROR_MESSAGES` regex table (`main.py:12-44`). Returns first friendly string or `None`. Ordering is intentional — most-specific first; auth precedes broad "permission denied"; the broad filesystem pattern is last. When friendly is found the message is `f'{friendly}\n\n{raw}'`, else just `raw` (`main.py:99`).
- **`main()` translates errors to exit codes** (`main.py:124-138`): wraps `init_new_package` in `try/except RuntimeError`, prints the error to `sys.stderr` (`main.py:135`), and `return 1`. Success / version / no-arg paths `return 0` (`main.py:138`). The `mp`/`modernpackage` console scripts call `main` (`pyproject.toml:23-25`).
- `check_alpha_numeric` validates package name, raising `ArgumentTypeError` at argparse layer (`main.py:56-61`).

## Q3: What does the `Justfile` `check` recipe do?

### Findings
- `check` (`Justfile:52`) depends on, in order: `check-format check-lint check-complexity check-typecheck test audit`.
  - `check-format` → `ruff format --check modernpackage tests` (`Justfile:28-29`)
  - `check-lint` → `ruff check modernpackage tests` (`Justfile:31-32`)
  - `check-complexity` → `ruff check --select C901 modernpackage tests` (`Justfile:34-35`)
  - `check-typecheck` → `mypy modernpackage tests` (`Justfile:37-38`)
  - `test` → `pytest -n "$(nproc --ignore=1)" {{args}}` (`Justfile:13-14`)
  - `audit` → `pip-audit --skip-editable` (`Justfile:40-41`)
- **`deadcode` is commented out** of the `check` list and the `fix-lint` recipe (`Justfile:43-44`, `48`, `52`).
- **Every sub-recipe depends on `sync`** (`Justfile:9-11`): `uv pip sync requirements-dev.txt` then `uv pip install -e .[test]`. So each step re-syncs the environment.
- **Assumed tooling**: `uv`, `just`, `nproc`, and (via `.[test]`) `ruff`, `mypy`, `pip-audit`, `pytest`, `pytest-cov`, `pytest-xdist` (`pyproject.toml:27-37`). All commands run through `uv run`. Requires Python ≥ 3.14 (`pyproject.toml:8`).

## Q4: Directory layout / state after `just init`

### Findings
- `init` recipe (`Justfile:59-73`), default `package_name="modernpackage"`; `init_new_package` invokes it as `just init <package_name>` with `cwd` = the cloned dir.
- Steps performed in the cloned directory:
  1. `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'` — replaces the string everywhere; OS-branched for Linux vs Darwin sed syntax (`Justfile:61-66`).
  2. **Version reset**: `sed -i ... 's/X.Y.Z/0.0.1/g' modernpackage/__init__.py` (`Justfile:67`). (Current source version is `0.0.9`, `modernpackage/__init__.py:3`.)
  3. **Directory rename**: `mv modernpackage {{package_name}}` (`Justfile:68`).
  4. **Git re-init**: `rm -fr .git/ .venv` then `git init -b main .`, `git add .`, `git commit -m "Initial modern {{package_name}} package setup"` (`Justfile:69-72`).
  5. Prints next step: `cd {{package_name}} && just check` (`Justfile:73`).
- **Subsequent commands** (e.g. `just check`) are expected to run from inside the new package directory (`cwd()/<package_name>`), as the final echo instructs `cd {{package_name}}`.

## Q5: How `tests/test_main.py` exercises the subprocess flow

### Findings
- **`Popen` is patched at the module seam**: `patch('modernpackage.main.Popen')` (`test_main.py:49`, `57`, `68`, `81`, `178`).
- **Single-shared-mock pattern** (success/simple failure): set `popen_mock.return_value.returncode` and `popen_mock.return_value.communicate.return_value = (stdout_bytes, stderr_bytes)`; both `Popen` calls return the same mock. Used in `test_init_new_package` (returncode 0, asserts `popen_mock.call_count == 2`, `test_main.py:48-53`) and `test_init_new_package_git_clone_failure` (`test_main.py:56-61`).
- **`side_effect` list for multi-step sequences** where steps differ: `popen_mock.side_effect = [git_clone_mock, just_init_mock]`, each a `MagicMock` with its own `returncode`/`communicate.return_value`. Used in `test_init_new_package_just_init_failure` (clone OK, init fails → `RuntimeError 'just init failed with exit code 1'`, `test_main.py:74-84`) and `test_init_new_package_just_not_installed` where the second element is `FileNotFoundError('just not found')` to simulate the missing binary (`test_main.py:64-71`).
- **Failure assertions** use `pytest.raises(RuntimeError, match=...)` (`test_main.py:60`, `70`, `83`) and, for the humanized path, `pytest.raises(...) as exc_info` then asserts substrings in `str(exc_info.value)` (`test_main.py:177-189`: checks `'check your network'`, `'git clone failed with exit code 1'`, `'Could not resolve host'`).
- **`main()`-level tests** patch `ArgumentParser`, `init_new_package`, and `print` (`test_main.py:87-138`); failure tests inject `init_mock.side_effect = RuntimeError(...)` and assert the message is printed (`test_main.py:99-111`) and that `main()` returns `1` (`test_main.py:114-124`).
- `humanize_git_clone_error` is unit-tested directly across network/not-found/auth/dir-exists/unknown cases (`test_main.py:141-174`).
- All mocking is via `unittest.mock` `MagicMock`/`patch` (`test_main.py:2`); no real subprocesses are spawned anywhere in this file.

## Q6: How are e2e / real-subprocess tests configured?

### Findings
- **Marker defined**: `e2e: tests that perform real external calls (network/subprocess/fs)` (`pyproject.toml:41-43`).
- **`addopts` excludes e2e by default**: `--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'` (`pyproject.toml:40`). Default `pytest` / `just test` runs skip e2e and enforce ≥95% coverage.
- **`test-e2e` recipe** runs only e2e: `uv run pytest -m e2e {{args}}` (after `sync`) (`Justfile:16-17`).
- **No e2e tests exist**: `tests/` contains only `test_main.py` (and empty `__init__.py`); grep for `e2e`/`pytest.mark` in `tests/` returns no matches. No test actually invokes the real scaffolding flow (git clone / just init); all subprocess interaction is mocked (see Q5).

## Cross-Cutting Observations
- Single source module `modernpackage/main.py` (139 lines) holds all CLI orchestration; single test module `tests/test_main.py`.
- Tests rely on patching the exact import name on the `modernpackage.main` module object (`Popen`, `ArgumentParser`, `print`, `init_new_package`) — consistent with the CLAUDE.md "patch the SDK seam on the defining module" convention.
- Failure model is layered: low-level functions raise `RuntimeError` with embedded stderr; `main()` is the sole place that converts exceptions to a non-zero exit code and writes to stderr.
- Coverage gate (95%) + `not e2e` default means any new real-subprocess test must be tagged `e2e` to avoid running in the default suite, and must not be counted on for coverage.
- Ruff `select = ["ALL"]` with mccabe `max-complexity = 8` (`pyproject.toml:78-79`) — note `Justfile` `check-complexity` uses `--select C901`; the inline mccabe cap differs from the CLAUDE.md-cited 10.

## Open Areas
- No e2e test currently invokes the live `git clone` + `just init` scaffolding path; whether one is intended to be added is outside what `questions.md`/the code reveal.
- `just init` performs `git grep`/`sed`/`mv`/`git init` directly; the OS-branching assumes only Linux/Darwin (`Justfile:61-66`) — Windows behavior is undefined by the recipe.
