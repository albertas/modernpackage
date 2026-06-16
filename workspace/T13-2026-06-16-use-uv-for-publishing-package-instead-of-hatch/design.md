# Design Discussion

## Current State

The package is built and published exclusively through the **`hatch` CLI**, driven
from the `Makefile` (the `Justfile` has no publish target — `Justfile:1-43`).

- `make publish` (`Makefile:22-25`) does four things: depends on `.venv`,
  `rm -fr dist/*`, `.venv/bin/hatch build`, then `.venv/bin/hatch -v publish`.
- The `.venv` target (`Makefile:13-20`) bootstraps the environment with `uv`
  (`uv venv -p 3.14`, `uv pip sync`, `uv pip install -e .[test]`). `hatch` is on
  the PATH only because it is listed in the `test` extra
  (`pyproject.toml:28-38`, specifically `pyproject.toml:29`).
- Build backend is **hatchling**: `requires = ["hatchling"]`,
  `build-backend = "hatchling.build"` (`pyproject.toml:46-48`).
- Backend config lives under `[tool.hatch.*]`: file selection
  (`[tool.hatch.build]`, `pyproject.toml:50-52`) and the dynamic version plugin
  (`[tool.hatch.version] path = "modernpackage/__init__.py"`,
  `pyproject.toml:54-55`), which satisfies `dynamic = ["version"]`
  (`pyproject.toml:17`). The version value is single-sourced at
  `modernpackage/__init__.py:3` (`__version__ = '0.0.9'`).
- No publish target/credentials are configured in-repo: no `[tool.hatch.publish]`,
  no `publish-url`, no `UV_PUBLISH_*`/`HATCH_*` env (research grep, Q1/Q4).
- A `gitlab` install index exists but is **resolution-only** — it has a `url`
  but no `publish-url` (`pyproject.toml:98-100`).
- `uv` is already the project's environment/locking/task-running tool
  (`Makefile:13-20,49-56`, `Justfile:1-43`); it just does not yet do build/publish.
- Docs and README describe the hatch flow: `README.md:9,19,31-32`,
  `docs/architecture.md:149-151`, `docs/specification.md:77`, `docs/overview.md:40`.
- CI (`.github/workflows/...:26-30`, `.gitlab-ci.yml:13-18`) runs only
  `make check` — no build/publish step. Releasing is a manual local `make publish`.

## Desired End State

`make publish` builds and uploads the package using **`uv`** (`uv build` +
`uv publish`); the `hatch` CLI is no longer invoked or installed.

Verification:
1. `make publish` no longer references `hatch`; it runs `uv build` then `uv publish`.
2. `uv build` produces `dist/modernpackage-0.0.9.tar.gz` and
   `dist/modernpackage-0.0.9-py3-none-any.whl` (sdist + wheel, version matching
   `modernpackage/__init__.py:3`). This is locally verifiable end-to-end.
3. `hatch` no longer appears in `pyproject.toml` (`grep -r hatch` returns only the
   retained `hatchling` backend tables, not the `hatch` CLI dependency).
4. `make check` still passes (build-backend and dynamic version unchanged).
5. README/docs describe uv-based publishing instead of hatch.

## Patterns to Follow

- **Makefile target style** — global `uv` subcommands, not `.venv/bin/` wrappers:
  the existing `compile`/`sync` targets call `uv` directly (`Makefile:49-56`).
  Mirror that for build/publish (`uv build`, `uv publish`), unlike the current
  `.venv/bin/hatch` invocation (`Makefile:24-25`).
- **Keep the PEP 517 backend declaration intact.** `uv build` is a build
  *frontend* that invokes the backend in `[build-system]` (research Q6); hatchling
  stays as the backend so the dynamic-version plugin (`pyproject.toml:54-55`)
  keeps single-sourcing the version from `modernpackage/__init__.py:3`.
- **Default-index behavior matches today.** `hatch publish` passed no index/URL
  (research Q1); `uv publish` with no `--index`/`--publish-url` defaults to PyPI
  (research Q6), matching README's "publishes ... to pypi.org" (`README.md:9`).
- **`dist/` is cleared before each build** (`Makefile:23`) — retain, because
  `uv publish` uploads *every* matching artifact in `dist/`, not just the latest
  version (research Q6). Stale artifacts would otherwise be re-uploaded.
- **Pattern NOT to follow / fix opportunistically:** the existing version drift
  (`dist/` held `0.0.8` while source is `0.0.9`,
  `docs/specification.md:137,144`) is exactly why clearing `dist/` matters; do not
  drop the `rm -fr dist/*` step.

## Design Decisions

1. **Keep hatchling as the build backend** — replace only the `hatch` *CLI*, not
   the backend. The task targets the publishing flow, and hatchling's
   `[tool.hatch.version]` plugin is what single-sources the version from
   `__init__.py:3`. Migrating to uv's native `uv_build` backend would force the
   version to move (uv_build does not read a source-file constant the same way),
   a larger, riskier change outside this task's scope.
2. **`make publish` becomes `uv build` + `uv publish`** — direct `uv` subcommands
   replacing `.venv/bin/hatch build` / `.venv/bin/hatch -v publish`
   (`Makefile:24-25`). Keep `rm -fr dist/*` and the `.venv` prerequisite for a
   surgical change.
3. **Remove `hatch` from the `test` extra** (`pyproject.toml:29`) — it was present
   only to provide the publish CLI; nothing else uses it. `hatchling` is pulled in
   automatically by `uv build`'s isolated build env, so no dependency replaces it.
4. **Default publish target = PyPI, no in-repo `publish-url`** — preserves current
   observable behavior (hatch passed no target; README says pypi.org). Adding a
   `publish-url` to the `gitlab` index is deliberately *not* done (see Open Risks),
   because the intended destination is ambiguous from code alone (research Open
   Areas) and the existing flow already defaults to PyPI.
5. **Authentication stays out-of-repo via env/keyring** — `uv publish` reads
   `UV_PUBLISH_TOKEN` (or `--token`, keyring) (research Q6), mirroring how `hatch
   publish` relied on user-level `~/.pypirc`/interactive entry (research Open
   Areas). No credentials are committed.
6. **Update README + docs to describe uv publishing** — `README.md:31-32`
   (toolset line "hatch - for publishing"), `docs/architecture.md:149-151`,
   `docs/specification.md:77`, `docs/overview.md:40`. Keep edits minimal and
   factual; do not rewrite surrounding prose.
7. **Leave CI untouched** — neither workflow builds/publishes
   (`.github/...:26-30`, `.gitlab-ci.yml:13-18`); wiring publish into CI is new
   behavior, not part of this task.

## What We're NOT Doing

- Not migrating the build backend to `uv_build` (hatchling stays).
- Not adding a `publish-url` to the `gitlab` index or changing the publish
  destination.
- Not adding a publish step to GitHub/GitLab CI.
- Not adding a `publish` recipe to the `Justfile` (it has no publish target today;
  build/publish remain `Makefile`-only).
- Not committing credentials or changing the auth mechanism.
- Not bumping/fixing the package version or rebuilding stale `dist/` artifacts as
  part of this change.

## Open Risks

- **Publish destination ambiguity.** README/docs say pypi.org (`README.md:9`) but
  the only configured index is GitLab (`pyproject.toml:98-100`). We default
  `uv publish` to PyPI to match the old behavior; if the real intent is GitLab,
  a follow-up must add `publish-url` to the index and call `uv publish --index
  gitlab`. Flag for the implementer to confirm.
- **Credentials not verifiable from repo** (research Open Areas). The build step is
  fully locally verifiable; the upload step cannot be exercised without a token,
  so end-to-end publish verification is manual/out-of-band.
- **`uv build` isolated-env backend resolution.** `uv build` installs `hatchling`
  in an isolated PEP 517 env; if offline or the index lacks hatchling this could
  fail where `hatch` (already installed in `.venv`) did not. Low risk given uv
  already resolves from the configured indexes.
