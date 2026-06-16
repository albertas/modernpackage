# Research Findings

Scope: where the Python interpreter version is declared, pinned, or assumed across
the repo. Repo currently targets **Python 3.14** almost everywhere; the only
divergences are a stale CI workflow *filename* and incidental `python3.12` strings
in example tracebacks.

## Q1: Version-encoding fields in `pyproject.toml`

### Findings
- `requires-python = ">= 3.14"` — `pyproject.toml:8`.
- Trove classifier `"Programming Language :: Python :: 3.14"` — `pyproject.toml:15`
  (a generic `"Programming Language :: Python"` classifier also present, `pyproject.toml:14`).
- `[tool.mypy] python_version = "3.14"` — `pyproject.toml:84`.
- No version in `[tool.ruff]` (only `line-length = 88`, `pyproject.toml:57-58`); ruff
  has no `target-version` set, so it infers from `requires-python`.
- `[build-system]` uses `hatchling` with no Python pin (`pyproject.toml:46-48`).
- Every explicit value is `3.14` / `>= 3.14`. Consistent.

## Q2: Dev virtualenv creation in `Makefile` and `Justfile`

### Findings
- **Makefile `.venv` target** (`Makefile:13-20`): `uv venv -p 3.14` (`Makefile:18`) — the
  one place an interpreter version is explicitly requested. Followed by
  `uv pip sync requirements-dev.txt` and `uv pip install -e .[test]` (`Makefile:19-20`).
- All other Makefile recipes depend on the `.venv` target and call binaries under
  `.venv/bin/...` (e.g. `Makefile:27-47`).
- **Justfile** has no explicit interpreter version. Its `sync` recipe runs
  `uv pip sync requirements-dev.txt` + `uv pip install -e .[test]` (`Justfile:6-8`);
  other recipes run via `uv run ...` (`Justfile:10-37`). `uv run`/`uv pip` resolve the
  interpreter from `requires-python` (`pyproject.toml:8`), not from an explicit flag.
- `Makefile:7` (`lifecycle` target) uses `uv sync --group dev`; no version flag.

## Q3: CI Python version selection

### Findings
- **GitHub Actions**: single workflow file `.github/workflows/check-modernpackage-on-python311.yml`.
  - Filename says `python311`, but contents target **3.14**:
    - `name: Checks modernpackage with Python3.14` (`:4`)
    - step `name: Set up Python 3.14` (`:22`)
    - `actions/setup-python@v3` with `python-version: "3.14"` (`:23-25`).
  - Steps: `make .venv` (`:26-28`) then `make check` (`:29-31`).
  - **Discrepancy**: the file *name* embeds `python311` while every in-file value is
    `3.14`. The "311" appears only in the filename.
- **GitLab CI** (`.gitlab-ci.yml`): `image: python:latest` (`:1`) — no pinned version;
  uses whatever `python:latest` provides. `before_script: make .venv` (`:13-14`), then
  job `test: script: make check` (`:16-18`). Note `make .venv` re-pins to 3.14 via
  `uv venv -p 3.14`, so the `python:latest` base image is largely overridden for the
  actual run.

## Q4: Static-analysis / build tools with a target Python version

### Findings
- **mypy**: `python_version = "3.14"` — `pyproject.toml:84` (within `[tool.mypy]`,
  `:82-90`, `strict = true`).
- **ruff**: no `target-version` configured (`[tool.ruff]` is only `line-length`,
  `pyproject.toml:57-58`); falls back to `requires-python` inference.
- **hatchling** (build backend): no Python version pin (`pyproject.toml:46-55`).
- **deadcode**: no Python version setting (`[tool.deadcode]`, `pyproject.toml:92-96`).
- **pytest**: no Python version setting (`[tool.pytest.ini_options]`, `pyproject.toml:40-44`).
- Net: only mypy carries an explicit tool-level target version (`3.14`).

## Q5: Python version mentions in `README.md` and `docs/`

### Findings
- **README.md**: no normative version statement. Only incidental `python3.12` strings
  inside a pasted traceback in the "Feature requests" section
  (`README.md:66`, `:68`, `:71`, `:73`). Also a feature-request bullet
  "Provide Python version for modernpackage CLI command." (`README.md:47`).
- **docs/specification.md**: Python requirement `>= 3.14` (`:74`); mypy
  `python_version = "3.14"` (`:87`); `.venv` "creates Python 3.14 virtual environment" (`:92`).
- **docs/architecture.md**: `python_version = "3.14"` snippet (`:105`); "type checks
  assume Python 3.14 or later" (`:116`); Python requirement `>= 3.14` (`:145`);
  mypy `python_version = "3.14"` (`:177`); `.venv` "creates Python 3.14 virtualenv" (`:194`).
- Other docs (`overview.md`, `invocation.md`, `backlog_formats.md`) have no Python
  version references (grep returned none).
- The only non-3.14 version in narrative files is `python3.12` in the README/issue
  traceback examples (also `issues/no_internet_connection_message:8-15`).

## Q6: Scaffolder copy/rewrite flow (`modernpackage/main.py` + `make init`)

### Findings
- **CLI entry**: `modernpackage`/`mp` → `modernpackage.main:main` (`pyproject.toml:23-25`).
  `main()` (`main.py:57-65`) dispatches: `-v` prints version, else
  `init_new_package(package_name=...)`.
- **Clone step** (`main.py:37-46`): `git clone https://github.com/albertas/modernpackage
  <new_package_path>` — copies the entire repo (all files, version strings included)
  into the new package directory.
- **Rewrite step** (`main.py:48-54`): runs `make init <package_name>` in the clone
  (`cwd=new_package_path`).
- **`make init`** (`Makefile:60-75`) performs the only rewrites:
  - `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/<args>/g'`
    (Linux `Makefile:63`; macOS `Makefile:66`) — renames the package string only.
  - `sed -i ... 's/<x.y.z>/0.0.1/g' modernpackage/__init__.py` (`Makefile:68`) — resets
    the version number to `0.0.1` (operates on `__init__.py`, e.g. `__version__ = '0.0.9'`,
    `modernpackage/__init__.py:3`).
  - `mv modernpackage <args>` (`Makefile:69`) — renames the package directory.
  - Re-inits git, commits "Initial modern `<args>` package setup" (`Makefile:70-73`).
- **Python-version strings during init**: NONE are rewritten. `make init` only touches
  the literal `modernpackage` name and the semantic version in `__init__.py`. So
  `requires-python = ">= 3.14"`, the `3.14` classifier, mypy `python_version = "3.14"`,
  `uv venv -p 3.14`, the CI `python-version: "3.14"`, and the `python311` workflow
  *filename* all propagate verbatim into a generated package. The generated package
  keeps Python 3.14 and inherits the same filename-vs-content mismatch.

## Cross-Cutting Observations
- Single source of an *explicit* interpreter pin: `uv venv -p 3.14` (`Makefile:18`).
  Everything else is either declarative metadata (`requires-python`, classifier,
  mypy `python_version`) or CI config that mirrors it.
- The repo is internally consistent on **3.14** for all functional config; the lone
  outliers are cosmetic/incidental: the `python311` workflow filename and the
  `python3.12` paths inside example tracebacks.
- `docs/specification.md` and `docs/architecture.md` document 3.14 in prose and would
  need updating in lockstep with any version change.
- The scaffolder is a clone-then-`sed` mechanism; it rewrites only the package name and
  semantic version, never the Python version — version bumps must be made in the source
  repo to reach generated packages.

## Open Areas
- The intent behind the `python311` filename vs `3.14` contents is not recorded in the
  repo; observed as a mismatch only.
- `.gitlab-ci.yml` `image: python:latest` resolves at CI runtime to whatever upstream
  publishes; its concrete version cannot be determined from the repo (and is overridden
  for the actual run by `uv venv -p 3.14`).
