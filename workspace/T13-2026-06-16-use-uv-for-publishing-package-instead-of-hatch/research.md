# Research Findings

Scope: build/packaging/release tooling — `Makefile`, `Justfile`, `pyproject.toml`,
CI files, `docs/`. All citations are `file:line`.

## Q1: Current build-and-publish flow end to end

### Findings
- **`Makefile` is the canonical command hub for publishing**; the `Justfile` has
  no build/publish target (`Justfile:1-43` covers only sync/test/checks/compile).
- `make publish` target (`Makefile:22-25`):
  1. depends on `.venv` (built first; see below),
  2. `rm -fr dist/*` — clears prior artifacts,
  3. `.venv/bin/hatch build` — builds sdist + wheel into `dist/`,
  4. `.venv/bin/hatch -v publish` — uploads artifacts (verbose).
- The tool invoked for both build and publish is **hatch**, run from the venv,
  not via `uv run`. `dynamic`/version comes from hatchling (see Q2/Q3).
- `.venv` target (`Makefile:13-20`) bootstraps the environment before publish:
  installs `uv` via `pip` if missing (`ifndef UV`, `Makefile:14-17`),
  `uv venv -p 3.14`, `uv pip sync requirements-dev.txt`,
  `uv pip install -e .[test]`. `hatch` is available because it is listed in the
  `test` optional-dependencies group (`pyproject.toml:28-38`).
- No explicit index/repository argument is passed to `hatch publish`; target
  index/credentials are not configured in-repo (no `[tool.hatch.publish.*]`,
  no `publish-url`, no `UV_PUBLISH_*`/`HATCH_*` env). Confirmed by repo-wide grep.
- Other `Makefile` targets in the same family: `compile` (`Makefile:53-56`),
  `sync` (`Makefile:49-51`), `check`/`fix` (`Makefile:10-11`).
- `Justfile` `compile` (`Justfile:39-42`) mirrors `Makefile` compile:
  `uv pip compile` ×2 + `uv lock --upgrade`.
- Order summary for publish: `.venv` (uv bootstrap) → clear `dist/` →
  `hatch build` → `hatch publish`.
- Docs corroborate: `docs/specification.md:77`, `docs/architecture.md:149-151`,
  `docs/overview.md:40` ("build and publish to PyPI").

## Q2: How the distribution version is determined at build time

### Findings
- Version is **dynamic** in project metadata: `dynamic = ["version"]`
  (`pyproject.toml:17`). No static `version =` key in `[project]`.
- Hatchling resolves it from a source file via
  `[tool.hatch.version] path = "modernpackage/__init__.py"`
  (`pyproject.toml:54-55`).
- The source-of-truth value is the module constant
  `__version__ = '0.0.9'` (`modernpackage/__init__.py:3`).
- Participating files: `pyproject.toml:17` (declares dynamic),
  `pyproject.toml:54-55` (hatch version plugin path),
  `modernpackage/__init__.py:3` (actual value).
- Runtime use of the same constant: `main.py` imports `__version__` for the
  `--version` CLI output (`docs/invocation.md:35`, `docs/architecture.md:33`).
- `make init` rewrites the version to `0.0.1` on scaffolding via `sed`
  (`Makefile:69`).
- Observed version drift: built artifacts in `dist/` are `0.0.8`
  (`modernpackage-0.0.8-py3-none-any.whl`, `modernpackage-0.0.8.tar.gz`) while
  the source constant is `0.0.9` — noted in `docs/specification.md:137,144`.

## Q3: `[build-system]` and how backend / frontend CLI / backend config relate

### Findings
- `[build-system]` (`pyproject.toml:46-48`):
  `requires = ["hatchling"]`, `build-backend = "hatchling.build"`.
- **Backend** = `hatchling` (PEP 517 backend that produces the sdist/wheel).
- **Frontend CLI** = `hatch` (`hatch build` / `hatch publish`,
  `Makefile:24-25`). The frontend invokes the backend declared in
  `[build-system]`. `hatch` is installed via the `test` extra
  (`pyproject.toml:29`), not pinned beyond name.
- **Backend-specific config sections**, all under `[tool.hatch.*]`:
  - `[tool.hatch.build]` (`pyproject.toml:50-52`): `include = ["**/*.py"]`,
    `exclude = ["tests/**"]` — controls file selection in distributions.
  - `[tool.hatch.version]` (`pyproject.toml:54-55`): `path` for dynamic version
    (satisfies the `dynamic = ["version"]` declaration from Q2).
- Relationship: `[project].dynamic` defers version to the backend; the backend
  (hatchling) reads its `[tool.hatch.*]` tables; the frontend (hatch) drives the
  backend per PEP 517. Docs: `docs/architecture.md:138-144`,
  `docs/specification.md:69-73`.

## Q4: How `uv` is already used; uv and index configuration

### Findings
- **Environment / dependency management** (not building/publishing):
  - `uv venv -p 3.14`, `uv pip sync requirements-dev.txt`,
    `uv pip install -e .[test]` in `.venv`/`sync` (`Makefile:13-20,49-51`;
    `Justfile:1-8`).
  - Task runner: `uv run <tool>` for pytest/ruff/mypy in `Justfile:10-37`;
    `uv run lifecycle ...` in `Makefile:6-8` and `Justfile:1-4`.
- **Locking / compiling** (`Makefile:53-56`, `Justfile:39-42`):
  - `uv pip compile -U -q pyproject.toml -o requirements.txt`
  - `uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt`
  - `uv lock --upgrade` → produces `uv.lock`.
- **Index configuration** in `pyproject.toml:98-100`:
  ```
  [[tool.uv.index]]
  name = "gitlab"
  url = "https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple"
  ```
  - This is a **resolution/install** index (`url`, `simple` API). It has **no
    `publish-url`** key — so it is not wired for any publish step. Confirmed via
    grep: `publish-url` appears nowhere in the repo.
  - `uv.lock` records all dependencies as sourced from this same GitLab registry
    (`source = { registry = ".../packages/pypi/simple" }`, e.g. `uv.lock:12,21,...`).
- No `[tool.uv]` settings beyond the index array; no `UV_PUBLISH_*` env anywhere.
- Docs: private GitLab index described at `docs/specification.md:79`,
  `docs/architecture.md:196`, `docs/overview.md:61`.

## Q5: Where build/publish tooling is referenced/documented across the repo

### Findings
- **`README.md`**: lists `make publish` "publishes current package version to
  pypi.org" (`README.md:9,19`); Toolset line "hatch - for publishing package to
  pypi.org" and "uv - for ... dependency management" (`README.md:31-32`);
  feature-request "uv-based publishing" implied in backlog references.
- **`Makefile`**: actual publish implementation (`Makefile:22-25`); env
  bootstrap and uv usage (`Makefile:13-20,49-56`).
- **`Justfile`**: no publish target; uv usage for sync/test/checks/compile
  (`Justfile:1-43`).
- **`pyproject.toml`**: `[build-system]` hatchling (`46-48`), `[tool.hatch.*]`
  (`50-55`), `[[tool.uv.index]]` (`98-100`).
- **`docs/specification.md`**: build backend hatchling (`71`), build config
  (`72`), version mgmt (`73`), publishing flow (`77`), private index (`79`),
  dist artifacts `0.0.8` and version-drift gap (`137,144`).
- **`docs/architecture.md`**: Build & Versioning section (`138-147`),
  Publishing (`149-151` — `hatch build`/`hatch publish`), compile/lock
  (`160-165`), `[[tool.uv.index]]` note (`196`), `uv run` delegation (`234`).
- **`docs/overview.md`**: workflow list incl. `publish` (`12,40`); compile
  artifacts (`33,60`); planned "uv-based publishing" in backlog summary (`69`).
- **CI workflow files**:
  - `.github/workflows/check-modernpackage-on-python314.yml`: runs `make .venv`
    then `make check` on push/PR to `main` (`26-30`). **No publish step.**
  - `.gitlab-ci.yml`: `before_script: make .venv` (`13-15`), `test: make check`
    (`16-18`). **No publish step.** Uses `python:latest` image (`1`).
- Neither CI file builds or publishes artifacts; both only run quality gates.

## Q6: `uv` capabilities for building/publishing (external behavior)

Source: docs.astral.sh/uv (web research). Not currently exercised in this repo.

### Findings
- **`uv build`** is a PEP 517 build *frontend*: it sets up a build env and
  invokes the backend declared in `[build-system]`. Produces sdist (`.tar.gz`)
  and wheel (`.whl`), both by default; `--sdist`/`--wheel` restrict output.
  Default output dir `dist/`, overridable with `-o/--out-dir`. `--no-sources`
  builds as a non-uv consumer would; `--force-pep517` forces the subprocess
  path. Ref: docs.astral.sh/uv/concepts/projects/build/.
- **`uv publish`** uploads distributions. With no positional `FILES` it uploads
  all `.whl`/`.tar.gz` found in `dist/` (every matching file, not just the
  latest version). Also uploads attestation sidecars unless `--no-attestations`.
  `--check-url`/`UV_PUBLISH_CHECK_URL` skips already-present identical files.
  Ref: docs.astral.sh/uv/guides/package/.
- **Target index selection** — two mutually exclusive ways:
  - `--publish-url <URL>` / `UV_PUBLISH_URL` — raw upload endpoint.
  - `--index <NAME>` / `UV_PUBLISH_INDEX` — references a `[[tool.uv.index]]`
    entry that must carry a `publish-url` field; its `url` then doubles as the
    `--check-url`. (Note: the repo's `gitlab` index entry has only `url`, no
    `publish-url` — `pyproject.toml:98-100`.)
- **Authentication**:
  - Token: `--token` / `UV_PUBLISH_TOKEN` (sends username `__token__`).
  - Basic: `--username`/`--password` or `UV_PUBLISH_USERNAME`/`UV_PUBLISH_PASSWORD`.
  - Trusted Publishers (OIDC) automatically in GitHub Actions with
    `id-token: write`.
  - Keyring: `--keyring-provider subprocess` / `UV_KEYRING_PROVIDER` /
    `tool.uv.keyring-provider`.
- **Build backend requirement**: `uv build` always uses a backend; with no
  `[build-system]` it falls back to legacy setuptools. uv ships its own native
  backend `uv_build` (`requires = ["uv_build>=...,<..."]`,
  `build-backend = "uv_build"`), pure-Python only, configured via
  `[tool.uv.build-backend]`. Ref: docs.astral.sh/uv/concepts/build-backend/.

## Cross-Cutting Observations
- Two parallel command hubs: `Makefile` (full: publish, audit, deadcode, init)
  and `Justfile` (subset: no publish/audit/deadcode/init). Build+publish live
  only in `Makefile:22-25`.
- uv currently spans env mgmt + locking + task running; hatch/hatchling owns
  build + publish + dynamic version. The `[[tool.uv.index]]` is read-only
  (install side); no uv publish wiring exists.
- Version single-sourced at `modernpackage/__init__.py:3` via hatchling dynamic
  version; `dist/` lags (`0.0.8` vs `0.0.9`).
- CI (GitHub + GitLab) runs only `make check`; releasing is a manual local
  `make publish`.

## Open Areas
- **Credentials/target for the current `hatch publish`** are not defined in-repo
  (no `[tool.hatch.publish]`, no env in CI). Presumed to rely on
  user-level `~/.pypirc`/hatch config or interactive entry — not verifiable from
  the repository.
- Whether the GitLab index is also the intended *publish* destination (vs
  pypi.org per README) is ambiguous: README/docs say "pypi.org"
  (`README.md:9`), but the only configured index is GitLab
  (`pyproject.toml:98-100`). Not resolvable from code alone.
