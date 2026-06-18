# Structure Outline

## Approach

Bundle the scaffolding template inside the published wheel and make
`init_new_package` materialize it locally instead of cloning from the network.
Hatchling `force-include` maps the curated template files into
`modernpackage/_template/` at build time (no committed copy, no build hook); at
runtime `importlib.resources` + `shutil.copytree` copy that tree into the target,
a `git init`/`git add -A` re-stage gives `just init`'s `git grep` a tracked
working tree, and the now-dead remote probe + clone-error machinery is retired.
`_write_package_metadata` and the `Justfile` recipes stay unchanged.

Note: source paths below are repo-relative; the CLI module lives at
`modernpackage/main.py` (design/research refer to it as `main.py`).

---

## Phase 1: Bundle the template tree into the wheel

Add the `force-include` build config so `uv build` ships a curated
`modernpackage/_template/` tree inside the wheel. No runtime code reads it yet —
this is the self-contained-artifact foundation and is independently verifiable.

**Files**: `pyproject.toml`

**Key changes**:
- New table `[tool.hatch.build.targets.wheel.force-include]` mapping each curated
  source path → `modernpackage/_template/<same path>`:
  `Justfile`, `pyproject.toml`, `README.md`, `.gitignore`, `uv.lock`,
  `requirements*.txt`, `docs/`, `tests/`, `.github/`,
  `modernpackage/__init__.py`, `modernpackage/main.py`.
- Exclude cruft by omission: `workspace/`, `errors/`, `issues/`, `BACKLOG.md`,
  `metrics.yml`, `lifecycle_state.yml` are NOT mapped (Decision 2).
- Keep existing `[tool.hatch.build] include = ["**/*.py"]` (real package code).

**Verify**: `uv build` succeeds; then
`python -c "import glob,zipfile; n=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert 'modernpackage/_template/Justfile' in n and 'modernpackage/_template/pyproject.toml' in n and not any('workspace/' in x for x in n if '_template' in x), n"`
exits 0.

---

## Phase 2: Materialize from the bundled template (replaces clone)

Replace the `git clone` block in `init_new_package` with a copy-from-resource +
git re-stage step, and rewrite the tests that asserted the clone flow. After this
phase `modernpackage <name>` scaffolds with zero network access.

**Files**: `modernpackage/main.py`, `tests/test_main.py`, `tests/test_e2e.py`

**Key changes**:
- `import importlib.resources` (new); `shutil` already imported.
- New constant `_BUNDLED_TEMPLATE_DIRECTORY: str = '_template'` with comment
  (single-source-of-truth, Decision 3).
- New constant `_TEMPLATE_COPY_ERROR_MESSAGE: str` — single filesystem-permission
  message for copy/`git init` failures (Decision 7).
- `_materialize_template(target_path: Path) -> None` — new. Resolves
  `importlib.resources.files('modernpackage') / _BUNDLED_TEMPLATE_DIRECTORY`,
  wraps in `importlib.resources.as_file(...)`, `shutil.copytree(source,
  target_path)`, then re-stages via the `Popen` seam:
  `git init -b main` + `git add -A` with `cwd=target_path`. Filesystem/process
  failures raise `RuntimeError(_TEMPLATE_COPY_ERROR_MESSAGE)` (no traceback).
- `init_new_package(...)`: delete the clone `Popen` block (and its
  `humanize_git_clone_error` branch); call `_materialize_template(new_package_path)`
  before `_write_package_metadata`. `just init` / `just check` blocks unchanged.
- Tests: `test_main.py` — replace the "exactly 3 `Popen` calls (clone, init,
  check)" assertions with the new sequence (`git init`, `git add`, `just init`,
  `just check`) and mock `shutil.copytree`/`importlib.resources`; drop the
  clone-failure mock. `test_e2e.py` — switch from cloning `REPO_ROOT` to
  exercising the real bundled template (build+install wheel, scaffold offline);
  keep assertions at `test_e2e.py:82-103` intact.

**Verify**: `just check` passes (unit suite). Offline e2e (agent-executable):
`uv build && python -m venv /tmp/mp && /tmp/mp/bin/pip install dist/*.whl && cd /tmp && unshare -rn /tmp/mp/bin/modernpackage demopkg && test -d /tmp/demopkg/demopkg && grep -q "0.0.1" /tmp/demopkg/demopkg/__init__.py && ! grep -q "email@example.com" /tmp/demopkg/pyproject.toml`
exits 0 (scaffold built with network namespace removed; metadata substituted).
If `unshare` is unavailable, run the same without it plus
`! rg -n "git clone|ls-remote" modernpackage/main.py`.

---

## Phase 3: Retire dead network machinery, dry-run text, and docs

Remove the now-unreachable remote-probe and clone-error code paths, fix the
dry-run plan wording, and update docs. Pure cleanup — if it slips, Phases 1–2
still deliver offline scaffolding.

**Files**: `modernpackage/main.py`, `tests/test_main.py`, `docs/invocation.md`,
`docs/specification.md`, `docs/overview.md`

**Key changes**:
- Delete `_verify_template_remote_reachable()` (main.py:647-680),
  `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (main.py:75), and its
  `PreflightCheck('template remote reachable', ...)` registry entry
  (main.py:700). Remaining 3 preflight checks unchanged.
- In `_GIT_CLONE_ERROR_MESSAGES`: delete network / not-found / auth patterns
  (main.py:22-41); keep only filesystem-permission/dir-exists messaging needed
  by copy errors — or remove `humanize_git_clone_error` entirely if unused after
  Phase 2 (decide during impl). `_TEMPLATE_REPOSITORY_URL` stays (metadata
  target, Decision 6) with its comment updated to "metadata only".
- `_print_dry_run_plan`: replace `clone {url} into {target}` (main.py:551) with
  copy-from-bundled-template wording.
- `git` remains in `_REQUIRED_TOOLS` (re-stage + `just init` need it).
- Docs: drop clone/`ls-remote`/timeout/clone-failure-mode descriptions in
  `docs/invocation.md` (:74,:147,:208,:287-340),
  `docs/specification.md` (:27,:57), `docs/overview.md` (:58); describe
  copy-from-bundled-wheel instead.
- Tests: assert preflight now prints 3 `[ok]` lines; remove probe mocks.

**Verify**: `just check` passes; and
`! rg -n "_verify_template_remote_reachable|_REMOTE_REACHABILITY_TIMEOUT_SECONDS|ls-remote" modernpackage/ && ! rg -n "git clone|ls-remote|reachab" docs/`
exits 0. Dry run shows no clone wording:
`modernpackage --dry-run demopkg | grep -qi copy && ! (modernpackage --dry-run demopkg | grep -qi clone)`.

---

## Open decision (flag during Phase 1/2 impl)

**Inherited `force-include` block** in the scaffolded package's `pyproject.toml`
is inert there (no `_template/` dir present). Faithful to the prior clone but a
wart (design Open Risks). Decide whether `_write_package_metadata` (or the
template's own `pyproject.toml`) should prune it; default is leave-as-is unless
it breaks the scaffold's own `uv build`.

---

## Testing Checkpoints

- **After Phase 1**: `uv build` produces a wheel containing
  `modernpackage/_template/` with curated files and no cruft. Runtime behavior
  unchanged (still clones).
- **After Phase 2**: `modernpackage <name>` scaffolds with no network access;
  unit suite green for the copy + `git init`/`git add` + `just init`/`just check`
  sequence; offline e2e produces a package whose `just check` passes and whose
  `pyproject.toml` carries substituted metadata (contract at
  `test_e2e.py:82-103`).
- **After Phase 3**: no remote-probe / clone-error / `ls-remote` references
  remain in code or docs; preflight runs 3 checks; dry-run plan describes a copy,
  not a clone. `just check` green.
