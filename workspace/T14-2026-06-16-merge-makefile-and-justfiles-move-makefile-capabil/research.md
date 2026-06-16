# Research Findings

Scope: `Makefile`, `Justfile`, Python CLI (`modernpackage/`), tests, CI
(`.github/workflows/`, `.gitlab-ci.yml`), docs (`README.md`, `docs/`).

## Q1: Makefile targets, their shell commands, and which lack a Justfile equivalent

### Findings — Makefile targets (`Makefile:1-78`)
- `.PHONY` declares: `lifecycle compile publish check fix lint fixlint format mypy deadcode audit test init` (`Makefile:1`).
- `lifecycle` (`Makefile:6-8`): `uv sync --group dev`, then a `while uv run lifecycle --max-tasks 1 --prior-tasks "$count"` loop.
- `check` (`Makefile:10`): aggregate → `test lint mypy audit deadcode`.
- `fix` (`Makefile:11`): aggregate → `format fixlint`.
- `.venv` (`Makefile:13-19`): installs `uv` if missing, `uv venv -p 3.14`, `uv pip sync requirements-dev.txt`, `uv pip install -e .[test]`.
- `publish` (`Makefile:21-24`): `rm -fr dist/*`, `uv build`, `uv publish` (depends on `.venv`).
- `lint` (`Makefile:26-27`): `.venv/bin/ruff check modernpackage tests`.
- `fixlint` (`Makefile:29-31`): `ruff check --fix ... --unsafe-fixes`, `deadcode --fix ...`.
- `format` (`Makefile:33-34`): `.venv/bin/ruff format modernpackage tests`.
- `mypy` (`Makefile:36-37`): `.venv/bin/mypy modernpackage tests`.
- `audit` (`Makefile:39-40`): `.venv/bin/pip-audit --skip-editable`.
- `deadcode` (`Makefile:42-43`): `.venv/bin/deadcode modernpackage tests`.
- `test` (`Makefile:45-46`): `.venv/bin/pytest -n "$(nproc --ignore=1)" $(TEST_NAME)`.
- `sync` (`Makefile:48-50`): `uv pip sync requirements-dev.txt`, `uv pip install -e .[test]` (not in `.PHONY`).
- `compile` (`Makefile:52-55`): two `uv pip compile -U -q` calls + `uv lock --upgrade`.
- `init` (`Makefile:60-75`): see Q7.
- `%:` catch-all (`Makefile:77-78`): `@:` — absorbs extra goals (e.g. the package-name arg).

### Justfile recipes (`Justfile:1-43`)
`lifecycle`, `sync`, `test *args`, `test-e2e *args`, `format`, `lint`, `typecheck`,
`check-format`, `check-lint`, `check-complexity`, `check-typecheck`, `check`, `compile`.

### Makefile targets with NO direct Justfile equivalent
- `publish` (`Makefile:21-24`) — absent from Justfile.
- `fix` (`Makefile:11`) and `fixlint` (`Makefile:29-31`) — no Justfile recipe.
- `mypy` (`Makefile:36-37`) — Justfile uses `typecheck` (`Justfile:23-24`) with identical command but a different name.
- `audit` (`Makefile:39-40`) — no Justfile recipe.
- `deadcode` (`Makefile:42-43`) — no Justfile recipe (Justfile's `check-complexity` runs `ruff --select C901` instead).
- `init` (`Makefile:60-75`) — no Justfile recipe.
- `.venv` (`Makefile:13-19`) — no Justfile equivalent (Justfile relies on `sync` only).
- `%:` catch-all (`Makefile:77-78`) — no Justfile analogue (Justfile uses `*args`).
- `check` differs in composition: Makefile `check` = `test lint mypy audit deadcode` (`Makefile:10`); Justfile `check` = `check-format check-lint check-complexity check-typecheck test` (`Justfile:33`). Justfile's `check` adds format/complexity gates but omits `audit` and `deadcode`.

### Justfile recipes with no Makefile equivalent
- `test-e2e` (`Justfile:14-15`): `uv run pytest -m e2e {{args}}`.
- `check-format`/`check-lint`/`check-complexity`/`check-typecheck` (`Justfile:26-32`).

## Q2: How recipes are defined — Justfile vs Makefile structure

### Justfile (`Justfile:1-43`)
- **Dependencies**: prerequisites follow a colon — `test *args: sync` (`Justfile:11`); every working recipe except `lifecycle` and `compile` depends on `sync`.
- **`sync` prerequisite** (`Justfile:6-8`): runs `uv pip sync requirements-dev.txt` + `uv pip install -e .[test]`; it is the shared dependency-install gate (`Justfile:11,14,17,20,23,26,29,32`).
- **Argument passing**: trailing `*args` variadic parameter in the signature (e.g. `test *args`, `test-e2e *args`) interpolated into the body with `{{args}}` (`Justfile:11-12,14-15`).
- **Shell/shebang conventions**: no shebang; recipe lines use leading `@` to silence echo (`Justfile:2-4,7-9,12`). Shell substitutions use `$(...)` and `$count` directly inside lines (`Justfile:4,12`).
- Recipes invoke tools via `uv run <tool>` (`Justfile:12,17,20,23`) rather than `.venv/bin/<tool>`.

### Makefile (`Makefile:1-78`) — structural contrasts
- **`.PHONY`** (`Makefile:1`) declares non-file targets explicitly — Just has no equivalent (every recipe is "phony" by default).
- **`.venv` target** (`Makefile:13-19`): a real-file prerequisite; targets depend on `.venv` (e.g. `lint: .venv`) so the venv is built once and reused. Just replaces this with the `sync` recipe prerequisite.
- **Argument passing**: `args = $(or $(filter-out $@,$(MAKECMDGOALS)), "modernpackage")` (`Makefile:2`) extracts the extra goal as the arg, defaulting to `modernpackage`; used in `init` as `$(args)`/`${args}`. `test` uses `$(TEST_NAME)` env var (`Makefile:46`). Just uses named `*args`/`{{args}}` instead.
- **OS branching**: `OS := $(shell uname)` (`Makefile:4`) with `ifeq`-style `if [ $(OS) = "Linux" ]` / `"Darwin"` shell conditionals inside `init` (`Makefile:62-67`); also `ifndef UV` for uv install in `.venv` (`Makefile:14-17`). Just has no such branching here.
- **`%:` catch-all** (`Makefile:77-78`): pattern rule absorbing the package-name goal so `make init mypackage` does not error. No Just equivalent; Just passes args via the variadic parameter.
- Tool invocation uses `.venv/bin/<tool>` (`Makefile:27,30,34,37,40,43,46`) vs Just's `uv run`.

## Q3: Where Python source invokes `make` as a subprocess

### Findings (`modernpackage/main.py:37-51`)
- `init_new_package(package_name)` runs the full scaffolding flow.
- Surrounding init flow:
  1. `new_package_path = Path.cwd() / package_name` (`main.py:39`).
  2. First `Popen`: `['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path]` with `stdin=PIPE, stdout=PIPE`; `pipe.communicate()[0]` (`main.py:41-46`).
  3. Second `Popen`: `['make', 'init', package_name]` with `stdin=PIPE, stdout=PIPE, cwd=new_package_path` (`main.py:48-53`).
- **Arguments to make**: `init` target + `package_name` as the extra goal (consumed by Makefile's `args`/`%:`).
- **Output handling**: `pipe.communicate()[0].decode().split('make:')[0].strip()` (`main.py:54`) — decodes stdout, truncates at the literal `make:` marker, strips; the result is **discarded** (not assigned, returned, or printed). No error/return-code checking on either call.
- Reached from `main()` (`main.py:57-62`): when `--version` not set and `package_name` provided, calls `init_new_package(package_name=parsed_args.package_name)`.
- `# noqa: S603`/`S607` suppress bandit subprocess/partial-path lint warnings (`main.py:42,43,49,50`).

## Q4: How tests cover the make-invoking path

### Findings (`tests/test_main.py:42-45`)
- `test_init_new_package` patches `modernpackage.main.Popen` (`patch('modernpackage.main.Popen') as popen_mock`), calls `init_new_package('mypackage')`, and asserts only `popen_mock.called` — i.e. that *some* subprocess was spawned.
- It does **not** assert the arguments (`make init ...`), call count (both `git clone` and `make` go through the same mock), `cwd`, or output handling. The `make` invocation is not asserted distinctly from `git clone`.
- `main()`-level coverage: `test_main_with_package_name` (`test_main.py:48-56`) patches `init_new_package` directly and asserts it is called once with `package_name='mypackage'` — so the actual `make` call is never exercised there.
- No test runs a real `make` subprocess. `pyproject.toml:40` sets `addopts = "... -m 'not e2e'"` and `pyproject.toml:41-43` defines the `e2e` marker (real external calls); no `e2e`-marked test file currently exists in `tests/` (only `tests/test_main.py` and `tests/__init__.py`; a stale `test_e2e_probe` `.pyc` exists in `__pycache__` but the source is absent).

## Q5: CI files referencing make targets

### Findings
- `.gitlab-ci.yml`: `before_script: - make .venv` (`.gitlab-ci.yml:16-17`); `test:` job `script: - make check` (`.gitlab-ci.yml:19-21`). Base image `python:latest` (`.gitlab-ci.yml:1`).
- `.github/workflows/check-modernpackage-on-python314.yml`: "Install dependencies" step runs `make .venv`; "Run checks" step runs `make check`. Triggered on push/PR to `main`, Python 3.14, `ubuntu-latest`.
- Both pipelines call exactly two targets: `make .venv` then `make check`. No CI references the Justfile.

## Q6: Documentation references to make / toolset / workflow

### Findings
- `README.md:8-9`: end-user post-init commands `make check`, `make publish`.
- `README.md:17-21` ("Development"): `make check`, `make fix`, `make publish`, `make compile`, `make sync` with one-line descriptions.
- `README.md:33`: toolset lists "Makefile - aliases for commonly used command line commands."
- `README.md:39-48`: feature-request notes incl. "remove init Makefile alias", "make compile and make sync does not work when virtual environment is activated".
- `README.md:56-75`: traceback showing the `make init` Popen call failing offline.
- `docs/overview.md:31-40`: describes `make check/fix/compile/test/test-e2e/lint/format/mypy/audit/deadcode/publish`. Note `make test`/`make test-e2e` are documented but the Makefile has no `test-e2e` target (`Makefile:1`), and `make test` does not exclude e2e the way docs claim.
- `docs/overview.md:45,57,60,75`: `just compile`, `git clone` + `make init`, `make compile`/`just compile` lockstep, "`just check` (or `make check`)".
- `docs/architecture.md:13-18`: structure block labels `Makefile` "canonical command hub", `Justfile` "just-based command shortcuts"; lines 66, 151, 290-292, 316, 327-328 reference `make init/publish/test/test-e2e/check`.
- `docs/specification.md:29,56,67,77-78,90,130,139,143,145`: documents the self-replication path, `%:`/`@:` catch-all, `make publish/compile/audit/check`, and notes a "Justfile vs. BACKLOG divergence" (`specification.md:145`).
- `BACKLOG.md` is referenced as listing "merge Makefile and Justfile" (`docs/overview.md:71`) and `just` commands (`docs/specification.md:145`).

## Q7: What the Makefile `init` recipe does, and `just` translation constraints

### Findings — `init` steps (`Makefile:60-75`)
1. `@echo "Initializing ${args}..."` (`Makefile:61`).
2. **Rename, Linux branch** (`Makefile:62-64`): `if [ $(OS) = "Linux" ]; then git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/$(args)/g'; fi` — in-place `sed -i` (GNU form, no backup suffix).
3. **Rename, macOS branch** (`Makefile:65-67`): same but `sed -i '' -e ...` (BSD form requiring an empty backup-suffix arg).
4. **Version reset** (`Makefile:68`): `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py` — resets version to `0.0.1`. (Uses GNU `sed -i` form only; not OS-branched.)
5. **Directory move** (`Makefile:69`): `mv modernpackage $(args)`.
6. **Git re-init** (`Makefile:70-73`): `rm -fr .git/ .venv`, `git init -b main .`, `git add .`, `git commit -m "Initial modern $(args) package setup"`.
7. **Final messages** (`Makefile:74-75`): success echo with ANSI color, then `@-exit 0` (the leading `-` ignores a nonzero exit).
- Relies on `args` from `MAKECMDGOALS` (`Makefile:2`) and the `%:` catch-all (`Makefile:77-78`) to consume the package-name goal without erroring.
- The `## NOTE` comment (`Makefile:57-59`) records that `--quiet`/`MAKEFLAGS += --quiet` was tried to suppress an "up to date" error but removed because it hid useful output.

### Constraints a `just` translation would face (observed, not prescriptive)
- `just` recipes get the package name via a named `*args`/`{{args}}` parameter, so the `args`/`MAKECMDGOALS`/`%:` mechanism (`Makefile:2,77-78`) has no direct port.
- OS branching (`uname` Linux vs Darwin, `Makefile:62-67`) would need to live inside recipe shell lines, since `just` has no `ifeq`/`ifndef` directives like Make (`Makefile:14,62,65`).
- Make's per-line separate-shell semantics differ from `just`'s; multi-statement logic (`if ...; then ...; fi`) already runs as single shell lines here, but the `0.0.1` version-reset line (`Makefile:68`) is GNU-`sed`-only and would carry the same Linux/macOS portability gap if branched.
- The trailing `@-exit 0` error-ignoring idiom (`Makefile:75`) maps to recipe-line error handling in `just` (e.g. a leading `-`), but the underlying "up-to-date" issue stems from Make's target model and may not arise in `just`.

## Cross-Cutting Observations
- **Two parallel command surfaces**: Makefile invokes tools via `.venv/bin/<tool>` and a real `.venv` target; Justfile invokes via `uv run` with a `sync` prerequisite. The Python CLI, both CI files, and the README all call **`make`**, never `just` (`main.py:50`, `.gitlab-ci.yml:17,21`, `.github/...yml`, `README.md`).
- **Naming drift**: `mypy`↔`typecheck`, `deadcode`↔`check-complexity (C901)`, and the differing `check` composition mean the two files are not 1:1.
- **Self-reference**: the project scaffolds copies of itself; `init` rewrites `modernpackage`→`<name>` across all tracked files via `git grep | sed` (`Makefile:62-67`).
- **Config hub**: tool settings centralized in `pyproject.toml`; recipes only invoke tools.

## Open Areas
- `BACKLOG.md` line-level content for "merge Makefile and Justfile" was referenced by docs (`docs/overview.md:71`, `docs/specification.md:145`) but not opened in full during this pass; the `Justfile` itself already contains the merged recipes, so the docs' claim that the Justfile "only defines a `lifecycle` target" (`specification.md:145`) is now stale relative to `Justfile:1-43`.
- Docs reference a `make test-e2e` target that does not exist in the current `Makefile` (`docs/overview.md:35`, `docs/architecture.md:291`); only the `Justfile` defines `test-e2e` (`Justfile:14-15`).
