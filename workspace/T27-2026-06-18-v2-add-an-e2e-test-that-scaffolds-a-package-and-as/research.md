# Research Findings

## Q1: How does `init_new_package` in `modernpackage/main.py` work end to end (clone, init, check), and how are failures/exit codes propagated?

### Findings
- Entry: `main()` parses args (`main.py:143-157`); if `package_name` set it calls
  `init_new_package(package_name=...)` inside a `try/except RuntimeError` and
  returns 1 on caught error, printing the error to stderr (`main.py:150-155`).
- `init_new_package` runs **three** subprocesses via `subprocess.Popen` in order
  (`main.py:83-140`):
  1. **Clone** — `git clone https://github.com/albertas/modernpackage <cwd>/<name>`
     (`main.py:87-92`). Destination is `Path.cwd() / package_name` (`main.py:85`).
     On non-zero return, builds `raw` message, augments with
     `humanize_git_clone_error(stderr)` if a known pattern matches, and
     `raise RuntimeError` (`main.py:96-100`).
  2. **Init** — `just init <name>` with `cwd=new_package_path` (`main.py:103-109`).
     `FileNotFoundError` (just missing) is caught → `RuntimeError` advising install
     (`main.py:110-115`). Non-zero return → `RuntimeError` (`main.py:119-121`).
  3. **Check** — `just check` with `cwd=new_package_path` (`main.py:123-130`).
     Return code 0 → prints `"just check passed — ... scaffold is valid."` and
     returns `0` (`main.py:132-134`). Non-zero → prints failure to stderr and
     returns `1` (`main.py:135-140`).
- Exit-code contract: clone/init failures raise `RuntimeError` (→ caught in
  `main`, exit 1). The final `just check` does **not** raise; it returns 0 or 1
  directly, which `main` returns (`main.py:152`). So `just check` failure is a
  non-exception path that still yields exit code 1.
- Error humanization: `humanize_git_clone_error` (`main.py:47-53`) lowercases
  stderr and returns the first matching friendly message from
  `_GIT_CLONE_ERROR_MESSAGES` (`main.py:12-44`, ordered most-specific first:
  network → repo-not-found → auth → dir-exists → broad fs-permission), or `None`.
- Validation: `check_alpha_numeric` rejects non-alnum names via
  `ArgumentTypeError` at arg-parse time (`main.py:56-61`, used at `main.py:78`).

## Q2: What does the `init` Justfile recipe do — what filesystem/git state does it produce?

### Findings
- Recipe `init package_name="modernpackage"` (`Justfile:59-73`):
  1. `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/<name>/g'` —
     replaces every occurrence of `modernpackage` in tracked files (Linux branch
     `Justfile:61-63`; macOS/Darwin `sed -i ''` branch `Justfile:64-66`).
  2. `sed ... 0.0.1 ... modernpackage/__init__.py` — rewrites any
     `N.N.N` version to `0.0.1` in the package `__init__.py` (`Justfile:67`).
     Note: runs against the pre-rename `modernpackage/__init__.py` path.
  3. `mv modernpackage <name>` — renames the package source directory
     (`Justfile:68`).
  4. `rm -fr .git/ .venv` — deletes cloned git history and any virtualenv
     (`Justfile:69`).
  5. `git init -b main .` → `git add .` → `git commit -m "Initial modern <name>
     package setup"` — fresh repo with one initial commit on `main`
     (`Justfile:70-72`).
- Resulting state: a renamed package dir, version pinned to `0.0.1`, no template
  git history, a brand-new git repo with a single commit, and all `modernpackage`
  references replaced by the new name. Prints a green next-step hint
  (`Justfile:73`).
- Git commit requires an author identity; the e2e test injects one via env
  (see Q5, `test_e2e.py:27-32,62-66`).

## Q3: What does `just check` run, what external tools/network does it need, how long/environment-sensitive is it?

### Findings
- `check: check-format check-lint check-complexity check-typecheck test audit`
  (`Justfile:52`). Each sub-recipe `depends on sync` (`Justfile:28-41`).
- `sync` runs `uv pip sync requirements-dev.txt` + `uv pip install -e .[test]`
  (`Justfile:9-11`) — requires **`uv`** and network (PyPI + the GitLab index at
  `pyproject.toml:97-99`).
- Sub-steps:
  - `check-format`: `uv run ruff format --check` (`Justfile:28-29`)
  - `check-lint`: `uv run ruff check` (`Justfile:31-32`)
  - `check-complexity`: `uv run ruff check --select C901` (`Justfile:34-35`)
  - `check-typecheck`: `uv run mypy` (`Justfile:37-38`)
  - `test`: `uv run pytest -n "$(nproc --ignore=1)"` (`Justfile:13-14`) — note
    pytest default `addopts` excludes `e2e` (`pyproject.toml:40`), so the inner
    `just check` does **not** recurse into the e2e test.
  - `audit`: `uv run pip-audit --skip-editable` (`Justfile:40-41`) — **networked**
    vulnerability lookup.
- External tool deps: `just`, `uv`, `nproc`, plus tool packages `ruff`, `mypy`,
  `pip-audit`, `pytest`, `pytest-xdist`, `pytest-cov` (`pyproject.toml:28-37`).
- Environment sensitivity: needs network for `uv sync` and `pip-audit`; offline
  runners fail at sync. The e2e docstring notes it "takes minutes and requires
  network" (`test_e2e.py:13-14`).

## Q4: How is the test suite structured; how is the `e2e` marker defined, selected, and excluded by default?

### Findings
- Two test files under `tests/`: `test_main.py` (unit, fully mocked `Popen`,
  `test_main.py:1-249`) and `test_e2e.py` (real subprocess, `test_e2e.py:1-75`).
  `tests/__init__.py` is empty. No `conftest.py` present.
- Marker definition: `pyproject.toml:41-43` —
  `markers = ["e2e: tests that perform real external calls (network/subprocess/fs)"]`.
- Default exclusion: `pyproject.toml:40`
  `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`.
  So plain `pytest` (and `just test`, `Justfile:13-14`) skip e2e and enforce
  ≥95% coverage.
- Explicit selection: `just test-e2e` runs `uv run pytest -m e2e` (`Justfile:16-17`).
  Because `addopts` already contains `-m 'not e2e'`, the later `-m e2e` on the
  command line overrides it (last `-m` wins in pytest).
- Marker application: only `test_scaffolded_package_passes_check` is decorated
  `@pytest.mark.e2e` (`test_e2e.py:50`). All `test_main.py` tests are unmarked
  unit tests.

## Q5: What existing e2e/integration coverage exists for the scaffolding flow; approach and documented caveats?

### Findings
- `tests/test_e2e.py` holds one e2e test: `test_scaffolded_package_passes_check`
  (`test_e2e.py:50-74`). Approach:
  - Skips if `git`, `just`, or `uv` not on PATH (`test_e2e.py:25,52-54`).
  - Clones the **local committed checkout** `REPO_ROOT` (not the GitHub URL) into
    `tmp_path/scaffoldcheck` (`test_e2e.py:24,56-60`).
  - Runs `just init scaffoldcheck` with injected git identity env
    (`_GIT_IDENTITY_ENV`, `test_e2e.py:27-32,62-67`).
  - Asserts `<dest>/scaffoldcheck/__init__.py` exists and contains `0.0.1`
    (`test_e2e.py:69-71`).
  - Runs `just check` and asserts exit 0 (`test_e2e.py:73-74`).
  - Helper `_run` wraps `subprocess.run(..., check=False, capture_output=True,
    text=True)` (`test_e2e.py:35-47`).
- Documented caveats (module docstring `test_e2e.py:7-14`):
  - Deliberately replicates the clone+init flow against the local repo rather
    than calling `init_new_package` (which clones GitHub), so local template
    regressions fail the test.
  - `git clone` copies **committed** state only; uncommitted edits not exercised.
  - Inner `just check` runs full `uv sync` + networked `pip-audit`, takes minutes
    and requires network; offline runners fail at sync.
- `test_main.py` covers the scaffolding orchestration via mocks (no real
  subprocess): 3-call sequence (`test_main.py:49-64`), clone/init failures
  (`test_main.py:67-95`), check pass/fail and exit codes (`test_main.py:201-233`),
  and error humanization (`test_main.py:165-198,236-248`).

## Q6: How do CI configs (`.gitlab-ci.yml`, `.github/`) run test/check flows; how do they handle network/subprocess-dependent tests?

### Findings
- **GitLab** (`.gitlab-ci.yml`): image `python:latest`; `before_script` installs
  `uv`, `uv tool install rust-just`, adds `~/.local/bin` to PATH, runs `just sync`
  (`.gitlab-ci.yml:13-17`). The single `test` job runs `just check`
  (`.gitlab-ci.yml:19-23`). Caches `.cache/pip`; sets `RUFF_CACHE_DIR`
  (`.gitlab-ci.yml:5-11`).
- **GitHub** (`.github/workflows/check-modernpackage-on-python314.yml`): on
  push/PR to `main`; ubuntu-latest, Python 3.14; installs `uv` + `rust-just`,
  adds `~/.local/bin` to PATH, `just sync`, then `just check`
  (`.github/workflows/check-modernpackage-on-python314.yml:6-35`).
- Both CIs run only **`just check`**, which invokes `just test`
  (pytest with default `-m 'not e2e'`, `pyproject.toml:40`). Therefore the
  `e2e`-marked scaffolding test is **not** run in CI; only the mocked
  `test_main.py` unit tests run.
- Network handling: neither CI special-cases network/subprocess tests. `just
  check` itself depends on network (`uv sync`, `pip-audit` — Q3), so CI assumes a
  networked runner. No job invokes `just test-e2e`.

## Cross-Cutting Observations
- The default-exclude (`-m 'not e2e'` in `addopts`) plus CI only running
  `just check` means e2e tests are opt-in only via `just test-e2e`
  (`Justfile:16-17`); nothing in CI currently executes them.
- The e2e test intentionally diverges from production `init_new_package` (clones
  local repo, not GitHub URL `main.py:88`) to test the local template
  (`test_e2e.py:7-12`).
- `just init`'s `git commit` (`Justfile:72`) makes git author identity a
  requirement, which the e2e test satisfies via env injection
  (`test_e2e.py:27-32`); the production CLI relies on the ambient git config.
- Coverage gate ≥95% with `--no-cov-on-fail` applies to the default (non-e2e)
  run (`pyproject.toml:40`).

## Open Areas
- No `conftest.py` or shared fixtures exist beyond pytest builtins (`tmp_path`).
- Whether any runner currently invokes `just test-e2e` outside CI is not
  determinable from the repo; no scheduled/nightly workflow file exists under
  `.github/` (only the single Python 3.14 check workflow).
