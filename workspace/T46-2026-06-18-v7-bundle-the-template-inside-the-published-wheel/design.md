# Design Discussion

## Current State

Scaffolding is **clone-from-remote**. `init_new_package` (`main.py:712-804`)
sources the template entirely over the network from one constant
`_TEMPLATE_REPOSITORY_URL = 'https://github.com/albertas/modernpackage'`
(`main.py:71`):

- A preflight check probes the remote with `git ls-remote` bounded by a 10s
  timeout (`_verify_template_remote_reachable`, `main.py:647-680`; registered at
  `main.py:700`).
- The template is fetched with `git clone <url> <target>` via `Popen`
  (`main.py:740-745`); failures are classified by `humanize_git_clone_error`
  against network/auth/not-found regex patterns (`main.py:20-52,78-84`).
- `_write_package_metadata` rewrites placeholders in the **cloned**
  `pyproject.toml` as plain text via `str.replace` (`main.py:432-479`).
- `just init <module>` then substitutes the name with `git grep -l 'modernpackage'
  | xargs sed` (`Justfile:62,65`), seds the version to `0.0.1` (`Justfile:67`),
  renames `modernpackage/` → `<module>/` (`Justfile:68`), removes `.git`, and
  recreates a fresh repo with an initial commit (`Justfile:69-72`).
- `just check` validates the result (`main.py:785-792`).

The published wheel ships **only** `modernpackage/*.py` (`pyproject.toml:50`,
`include = ["**/*.py"]`); no template tree is bundled. Nothing reads
package-internal resources — `importlib.resources` is unused and `Path(__file__)`
is never referenced in `main.py` (research Q4).

The repo is its own template: `git clone` copies all **259 tracked files**,
including development-lifecycle cruft (`workspace/`, `errors/`, `issues/`,
`BACKLOG.md`, `metrics.yml`, `lifecycle_state.yml`) that has no business in a
scaffolded package. `just check` and the e2e assertions never touch that cruft.

## Desired End State

`modernpackage <name>` scaffolds a new package from template files **shipped
inside the installed wheel**, with no network access. Verify by:

1. The wheel contains a `modernpackage/_template/` tree (inspect
   `dist/*.whl` after `uv build`).
2. `init_new_package` performs **no** `git clone` and **no** remote reachability
   probe; it copies the bundled tree into the target directory.
3. Offline run (network disabled) produces a package whose `just check` passes
   and whose `pyproject.toml` carries the substituted metadata — i.e. the e2e
   contract in `test_e2e.py:82-103` still holds.
4. The materialized package is functionally identical to the clone-based result
   for everything the e2e test asserts.

## Patterns to Follow

- **Targeted text rewrite of `pyproject.toml`** via `str.replace` on known
  literals (`main.py:460-497`) — keep unchanged; it already operates on the
  materialized target directory (`package_path / 'pyproject.toml'`), not the
  source.
- **Subprocess seam via `Popen`/`run` on the module object** (`main.py:740`,
  `:656`) — unit tests patch these on `modernpackage.main` (`test_main.py:290-291`).
  New subprocess steps (`git init`, `git add`) must go through the same seam so
  tests can mock them.
- **Graceful degradation at filesystem/process boundaries** (CLAUDE.md §error
  handling; `main.py:451-458`, `:656-680`) — copy failures should surface a
  friendly message, not a traceback.
- **Single-source-of-truth constants with explanatory comments** (`main.py:71`,
  `:514`) — introduce the bundled-template path the same way.
- **Avoid abbreviations** in new identifiers (CLAUDE.md §6).
- **Pattern NOT to follow / to retire**: the network-specific branches of
  `_GIT_CLONE_ERROR_MESSAGES` (`main.py:22-41`) and the reachability probe
  (`main.py:647-680`) become dead once cloning is gone — do not preserve them
  speculatively.

## Design Decisions

1. **Bundle via hatchling `force-include`, not a committed snapshot or build
   hook**: add `[tool.hatch.build.targets.wheel.force-include]` to
   `pyproject.toml` mapping each template path to `modernpackage/_template/...`
   (replaces/extends `pyproject.toml:49-51`). This adds zero committed
   duplication, keeps bundled content derived from the live repo files, and is
   declarative (no `hatch_build.py`). A build hook was rejected as over-complex
   (CLAUDE.md §2); a committed `_template/` copy was rejected for drift risk.
2. **Curated template set, not byte-identical clone**: bundle only scaffolding
   files (`Justfile`, `pyproject.toml`, `README.md`, `.gitignore`, `docs/`,
   `tests/`, `requirements*.txt`, `uv.lock`, `.github/`, and the inner
   `modernpackage/__init__.py` + `main.py`). Exclude `workspace/`, `errors/`,
   `issues/`, `BACKLOG.md`, `metrics.yml`, `lifecycle_state.yml`. This is a
   deliberate deviation from "identical to the clone" — the clone shipped cruft;
   the e2e contract (`test_e2e.py:82-103`) is unaffected. Recorded as the main
   judgment call.
3. **Materialize with `shutil.copytree` from `importlib.resources`**: resolve the
   tree with `importlib.resources.files('modernpackage') / '_template'` wrapped
   in `importlib.resources.as_file(...)` for a concrete path, then `copytree`
   into `new_package_path`. Replaces the `git clone` block (`main.py:740-753`).
   `shutil` is already imported (`main.py:5`).
4. **Re-stage a git working tree before `just init`**: after `copytree`, run
   `git init` + `git add -A` in the target so `git grep` (`Justfile:62,65`) finds
   tracked files. The clone previously supplied this `.git`; we reproduce it. The
   `Justfile` stays **unchanged**, keeping the scaffolded package identical
   (no commit needed here — `just init` removes `.git` and re-inits anyway,
   `Justfile:69-72`).
5. **Drop the remote-reachability preflight check**: remove
   `_verify_template_remote_reachable` (`main.py:647-680`),
   `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`main.py:75`), and its registry entry
   (`main.py:700`). The bundled template is always present, so the check is
   meaningless. Remaining preflight checks (name valid, required tools, target
   dir absent — `main.py:691-699`) stay.
6. **Keep `_TEMPLATE_REPOSITORY_URL` for metadata only**: the constant is still
   the template `pyproject.toml` homepage (`pyproject.toml:21`) and the
   replacement target in `_write_package_metadata` (`main.py:471-474`). Retain
   it; just stop using it for clone/probe. Update its comment (`main.py:69-71`).
7. **Replace clone-error humanizing with copy-error handling**: delete the
   network/auth/not-found patterns (`main.py:22-41`); keep a single
   filesystem-permission message for `copytree`/`git init` failures. `git` stays
   a required tool (`_REQUIRED_TOOLS`, `main.py:56`) since `just init` and the
   re-stage step need it.

## What We're NOT Doing

- Not changing the `Justfile` `init`/`check` recipes (Decision 4 preserves
  `git grep`).
- Not changing `_write_package_metadata` logic (`main.py:432-479`).
- Not stripping the bundling config out of the **scaffolded** package's
  `pyproject.toml` (the `force-include` block it inherits is inert there; see
  Open Risks).
- Not renaming the inner `modernpackage/` template dir or the
  `.github/.../check-modernpackage-*.yml` filename — `just init` only rewrites
  file *contents*, matching current behavior.
- Not adding offline support to `just check` itself (it still runs `uv sync` /
  networked `pip-audit`; out of scope, see `test_e2e.py:13-14`).

## Open Risks

- **Inherited bundling config**: the materialized `pyproject.toml` carries the
  `force-include`/`_template` build config, which is inert in the scaffolded
  package (no `_template` dir present). Faithful to the clone but a wart; flag
  during implementation whether to prune it.
- **`importlib.resources` path materialization**: `files()/as_file()` must yield
  a real directory for `copytree`. uv/pip install unzipped, so this holds, but
  verify against the built wheel, not just the editable install.
- **Test rework**: unit tests assert exactly 3 `Popen` calls (clone, init, check;
  `test_main.py:297,310-330`) and mock clone failures (`:333-356`). These must be
  rewritten for the copy + `git init`/`git add` + init + check flow. The e2e test
  (`test_e2e.py:63`) should switch from cloning `REPO_ROOT` to exercising the real
  bundled-template path now that no network is required.
- **Docs drift**: `docs/invocation.md` (`:74,:147,:208,:287-340`),
  `docs/specification.md` (`:27,:57`), and `docs/overview.md` (`:58`) describe the
  clone + reachability probe and must be updated.
- **`uv.lock` size / staleness** in the bundled set — include it for reproducible
  scaffolds, but confirm it does not bloat the wheel unacceptably.
