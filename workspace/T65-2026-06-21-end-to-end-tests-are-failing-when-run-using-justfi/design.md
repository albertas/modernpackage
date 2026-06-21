# Design Discussion

## Current State

`just e` → `test-e2e` runs `uv run pytest -m e2e --no-cov` serially
(`Justfile:16-18`). Result today: **3 failed, 4 passed, 146 deselected**
(`research.md` Q6). All three failures share one root cause.

The 4 passing tests (`*_passes_check`, `has_no_backend_or_frontend`) exercise
scaffolding + host-side `just check` and never start a container. The 3 failing
tests all call `podman compose up -d --build`, which returns exit code 2:

- `tests/test_e2e.py::test_fullstack_package_runs_end_to_end` (assert `:504-505`)
- `tests_e2e/test_backend_e2e.py::test_backend_package_runs_end_to_end` (`:53`)
- `tests_e2e/test_fullstack_feature_e2e.py::test_fullstack_feature_runs_end_to_end` (`:56`)

The build dies in `backend_template/Containerfile:11-14`, builder STEP 5:

```
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
```

Only `uv.lock` and `pyproject.toml` are mounted. Even with
`--no-install-project`, uv builds the root project's *metadata* to satisfy the
locked resolution. The project uses a hatchling dynamic version
(`pyproject.toml:54-55` `[tool.hatch.version] path = "modernpackage/__init__.py"`,
renamed to `<module>/__init__.py` by `just init`). Hatchling's regex version
source reads that file — which is **not** in the build context at this layer
(source only arrives at STEP 6 `COPY . /app`). Error:

```
OSError: Error getting the version from source `regex`:
file does not exist: backend_run_pkg/__init__.py
error: Failed to generate package metadata for `backend-run-pkg @ editable+.`
```

Compose build context is the package root (`compose.yml:5,16` `build: .`), so
bind-mount sources are resolved relative to the package root.

Environment (`research.md` Q5): git/just/uv/npm/podman/podman-compose all
present; `docker` absent (podman used). Compose tests therefore do **not** skip —
they run and fail. Networking to the GitLab `vupi` index and GitHub works.

## Desired End State

`just e` produces a green suite: all 7 e2e tests pass (none skip in this
environment, since podman + npm are present). Concretely:

1. `podman compose up -d --build` returns 0 for backend and fullstack scaffolds.
2. The container builds the renamed package's editable metadata at STEP 5
   without needing the full source tree (preserving the dependency-layer cache).
3. The 4 currently-passing tests stay green (no regression to scaffolding,
   `just init`, or host-side `just check`).

**Verification:** `just e` exits 0 with `7 passed`. Spot-check by reading the
captured output for `compose up` returning 0 in each runtime test.

## Patterns to Follow

- **Bind-mount only what the build layer needs, keyed on the `modernpackage`
  token.** The Containerfile already mounts `uv.lock` + `pyproject.toml`
  (`Containerfile:12-13`). Add the dynamic-version source file the same way. The
  CMD line already carries the token (`Containerfile:26`
  `modernpackage.app:create_app`), and `just init` rewrites every `modernpackage`
  literal in tracked files via `git grep -l 'modernpackage' | xargs sed`
  (`Justfile:55-72`, `research.md` Q4). So writing `source=modernpackage/__init__.py`
  in the template is automatically rewritten to `source=<module>/__init__.py`.
- **Template files must be tracked before `just init`.** The e2e flow stages
  injected files with `git add -A` before init (`research.md` Q4,
  `tests/test_e2e.py:238-240`); the new mount line rides along inside the already
  copied/tracked `Containerfile`. No new staging step required.
- **Two-stage builder caching is intentional — keep it.** STEP 5 installs deps
  without project source so the dependency layer caches independently of source
  edits (`Containerfile:11-17`). The fix must not collapse the two syncs into
  one or `COPY . /app` early.

### Patterns NOT to follow

- Do **not** mirror the fix into `tests/test_e2e.py` / `tests_e2e/_scaffold.py`
  duplicated helpers (`research.md` Cross-Cutting). The fix is entirely in the
  template; test helpers need no change.
- Do **not** convert the package to a static version to dodge the file read.
  Dynamic version is the project's chosen pattern (`pyproject.toml:17,54-55`);
  `just init` pins the value to `0.0.1` at runtime, but the mechanism stays
  dynamic.

## Design Decisions

1. **Fix location — `backend_template/Containerfile` STEP 5 only.** The failure
   is isolated to the container build (`research.md` Q6); scaffolding, `just
   init`, and host `just check` already work. Smallest change that addresses the
   root cause.

2. **Mechanism — add a bind mount for the dynamic-version source file.** Add
   `--mount=type=bind,source=modernpackage/__init__.py,target=modernpackage/__init__.py`
   to the STEP 5 `RUN`. `just init` rewrites the token to the real module name;
   the file exists in the build context at that path post-init. This is the
   uv-documented idiom for hatchling dynamic versions in layered Docker builds.

3. **Also mount `README.md`.** `pyproject.toml:7` sets `readme = "README.md"`,
   and hatchling's `prepare_metadata_for_build_editable` reads it for the
   long-description field. The version error surfaces first, but the README is
   the likely next failure once version resolves. Mounting both up front avoids a
   second debug round-trip. A `_README_STUB` is written during strip
   (`research.md` Q4), so the file exists. **Assumption:** if verification shows
   README is not actually required, drop that mount to stay minimal.

4. **Leave the uv pin (`ghcr.io/astral-sh/uv:0.5`, `Containerfile:6`)
   untouched.** The bind-mount fix is uv-version-independent. The host/container
   uv mismatch (0.11 vs 0.5) is an open area (`research.md` Open Areas) but not
   the root cause; bumping it is out of scope unless verification proves the
   metadata behavior is version-specific.

5. **No change to `just e` / pytest selection.** The alias and `-m e2e
   --no-cov` override already select and run the right tests (`research.md` Q1).
   The suite is correctly wired; only the container build is broken.

## What We're NOT Doing

- Not de-duplicating `tests_e2e/_scaffold.py` vs `tests/test_e2e.py` helpers.
- Not changing the version scheme, `[project.scripts]`, or `just init` sed logic.
- Not adding `docker`, parallelizing e2e (`-n`), or touching coverage config.
- Not modifying the 4 passing tests or their scaffold assertions.
- Not editing `compose.yml`, the runtime stage, or `_expose_db_port`.
- Not bumping the pinned uv image (unless verification forces it — Decision 4).

## Open Risks

- **README may not be the only extra metadata file.** If hatchling needs more
  than version + readme for editable metadata, STEP 5 may fail on the next file.
  Mitigation: run `just e` after the change and read the build error; add
  mounts iteratively. Bounded — the metadata build reads a small, fixed set.
- **uv version sensitivity.** If uv 0.5 evaluates dynamic metadata differently
  than a modern uv would, the bind mount is still correct, but behavior under the
  pinned image is the source of truth — verify against the actual container build,
  not host uv.
- **Compose runtime flakiness.** Even with a green build, the runtime tests poll
  `/readyz` and exercise migrate/HTTP/Playwright (`research.md` Q2). These can be
  slow (~300 s suite) or flake on container/DB startup; distinguish a build fix
  from a runtime flake when reading results.
- **No recorded prior passing run** (`research.md` Open Areas) — we cannot diff
  against a known-good Containerfile; correctness is established only by making
  `just e` green here.
