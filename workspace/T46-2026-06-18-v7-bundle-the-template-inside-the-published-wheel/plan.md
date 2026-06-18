# Implementation Plan

## Overview

Bundle the scaffolding template inside the published wheel (via hatchling
`force-include` into `modernpackage/_template/`) and make `init_new_package`
materialize it locally with `importlib.resources` + `shutil.copytree` + a
`git init`/`git add` re-stage, so `modernpackage <name>` scaffolds with **no
network access**. The now-dead remote-reachability probe and `git clone`
error-classification machinery are retired.

All repo paths below are relative to `/home/niekas/tools/modernpackage`. The CLI
module is `modernpackage/main.py` (design/research call it `main.py`).

---

## Phase 1: Bundle the template tree into the wheel

Add the `force-include` build config so `uv build` ships a curated
`modernpackage/_template/` tree inside the wheel. No runtime code reads it yet —
this is the self-contained-artifact foundation, independently verifiable.

### Changes

#### 1. Wheel build config — map curated template files into `_template/`
**File**: `pyproject.toml`
**Action**: modify

Keep the existing real-package include (`pyproject.toml:49-51`) unchanged:

```toml
[tool.hatch.build]
include = ["**/*.py"]
exclude = ["tests/**"]
```

Add a new table **after** `[tool.hatch.version]` (i.e. after line 54, before
`[tool.ruff]`). `force-include` bypasses the `include`/`exclude` filters above,
so `tests/` is bundled despite `exclude = ["tests/**"]`, and the inner
`modernpackage/*.py` files land at a distinct destination so they do not collide
with the real package modules:

```toml
[tool.hatch.build.targets.wheel.force-include]
"Justfile" = "modernpackage/_template/Justfile"
"pyproject.toml" = "modernpackage/_template/pyproject.toml"
"README.md" = "modernpackage/_template/README.md"
".gitignore" = "modernpackage/_template/.gitignore"
"uv.lock" = "modernpackage/_template/uv.lock"
"requirements.txt" = "modernpackage/_template/requirements.txt"
"requirements-dev.txt" = "modernpackage/_template/requirements-dev.txt"
"docs" = "modernpackage/_template/docs"
"tests" = "modernpackage/_template/tests"
".github" = "modernpackage/_template/.github"
"modernpackage/__init__.py" = "modernpackage/_template/modernpackage/__init__.py"
"modernpackage/main.py" = "modernpackage/_template/modernpackage/main.py"
```

**Curated set rationale (Decision 2)**: only scaffolding files are mapped.
Development-lifecycle cruft is excluded *by omission* (not mapped):
`workspace/`, `errors/`, `issues/`, `BACKLOG.md`, `metrics.yml`,
`lifecycle_state.yml`.

**Assumption (flag to human)**: `.gitlab-ci.yml` exists at repo root but is
**not** in the curated list in `structure.md`/`design.md`, so it is left
unmapped. `just check` and the e2e contract never reference it, so excluding it
is safe; this is a deliberate narrowing consistent with the curated set.

### Verification
#### Automated
- [ ] `uv build` succeeds (produces `dist/modernpackage-*.whl`).
- [ ] Wheel contains the curated `_template/` tree and no cruft:
  ```bash
  uv build && python -c "import glob,zipfile; n=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert 'modernpackage/_template/Justfile' in n and 'modernpackage/_template/pyproject.toml' in n and 'modernpackage/_template/modernpackage/__init__.py' in n and 'modernpackage/_template/tests/test_main.py' in n and not any('workspace/' in x or '/errors/' in x or '/issues/' in x or 'BACKLOG.md' in x for x in n if '_template' in x), n"
  ```
  exits 0.

#### Manual
- [ ] Inner template Python files present (so the runtime copy has package code):
  ```bash
  python -c "import glob,zipfile; n=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert 'modernpackage/_template/modernpackage/main.py' in n, [x for x in n if '_template' in x]"
  ```
  exits 0.
- [ ] `.github` workflow bundled (filename unchanged, contents not yet renamed):
  ```bash
  python -c "import glob,zipfile; n=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert any('_template/.github/workflows/' in x for x in n), [x for x in n if '.github' in x]"
  ```
  exits 0.
- [ ] Runtime behavior unchanged (still clones): `just check` passes
  (`uv run pytest` suite is unaffected by build config).

---

## Phase 2: Materialize from the bundled template (replaces clone)

Replace the `git clone` block in `init_new_package` with a copy-from-resource +
git re-stage step, and rewrite the unit/e2e tests that asserted the clone flow.
After this phase `modernpackage <name>` scaffolds with zero network access.

### Changes

#### 1. New import
**File**: `modernpackage/main.py`
**Action**: modify (imports block, `main.py:3-11`)

Add `import importlib.resources` alongside the existing stdlib imports (place it
after `import os`, keeping the explicit-import style). `shutil` is already
imported (`main.py:5`). `TimeoutExpired` import stays in this phase (still used
by the probe, removed in Phase 3).

```python
import importlib.resources
import os
import re
import shutil
import sys
import tomllib
```

#### 2. New constants
**File**: `modernpackage/main.py`
**Action**: create (near the existing single-source-of-truth constants, after
`_TEMPLATE_REPOSITORY_URL`, ~`main.py:71`)

```python
# Name of the template subdirectory bundled inside the installed wheel
# (see [tool.hatch.build.targets.wheel.force-include] in pyproject.toml);
# single source of truth for both the build-mapping target and the runtime read.
_BUNDLED_TEMPLATE_DIRECTORY: str = '_template'

# Friendly message surfaced when copying the bundled template or staging the
# git working tree fails at the filesystem/process boundary (no traceback).
_TEMPLATE_COPY_ERROR_MESSAGE: str = (
    'cannot materialize the package template into the destination directory'
    ' — check filesystem permissions'
)
```

#### 3. New `_materialize_template` + `_stage_template_working_tree`
**File**: `modernpackage/main.py`
**Action**: create (place above `init_new_package`, after the preflight helpers
~`main.py:710`)

Both git subprocess steps go through the module-level `Popen` seam so unit tests
can mock them (design "Patterns to Follow"). Copy failures degrade to a friendly
`RuntimeError` (no traceback). `copytree` runs **inside** the `as_file(...)`
context so a zipped-resource extraction (if ever used) is valid for the whole
copy.

```python
def _materialize_template(target_path: Path) -> None:
    """Copy the wheel-bundled template tree into target_path and stage it in git.

    Resolves `modernpackage/_template` via importlib.resources, copies it into
    the not-yet-existing target directory with shutil.copytree, then runs
    `git init -b main` + `git add -A` so `just init`'s `git grep` sees a tracked
    working tree (design Decision 4). Filesystem failures degrade to a friendly
    RuntimeError without a traceback (CLAUDE.md §error handling).
    """
    template_resource = (
        importlib.resources.files('modernpackage') / _BUNDLED_TEMPLATE_DIRECTORY
    )
    try:
        with importlib.resources.as_file(template_resource) as template_directory:
            shutil.copytree(template_directory, target_path)
    except OSError as error:
        raise RuntimeError(_TEMPLATE_COPY_ERROR_MESSAGE) from error
    _stage_template_working_tree(target_path)


def _stage_template_working_tree(target_path: Path) -> None:
    """Run `git init -b main` + `git add -A` in target_path via the Popen seam.

    Reproduces the `.git` working tree the clone used to supply, so `just init`'s
    `git grep` (Justfile:62,65) finds tracked files. A non-zero exit raises a
    friendly RuntimeError carrying the raw stderr for diagnostics.
    """
    for command in (['git', 'init', '-b', 'main'], ['git', 'add', '-A']):
        pipe = Popen(  # noqa: S603
            command,  # noqa: S607
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            cwd=target_path,
        )
        _stdout, stderr = pipe.communicate()
        if pipe.returncode != 0:
            stderr_text = stderr.decode().strip()
            raw = (
                f'{" ".join(command)} failed with exit code'
                f' {pipe.returncode}: {stderr_text}'
            )
            raise RuntimeError(f'{_TEMPLATE_COPY_ERROR_MESSAGE}\n\n{raw}')
```

#### 4. Replace the clone block in `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify (`main.py:740-753`)

Delete the `git clone` `Popen` block **and** its `humanize_git_clone_error`
failure branch (lines 740-753). Call `_materialize_template` before
`_write_package_metadata`. The `just init` / `just check` blocks
(`main.py:764-804`) stay unchanged. Update the docstring (`main.py:722`).

Replace:

```python
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    ...
    pipe = Popen(  # noqa: S603
        ['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    _stdout, stderr = pipe.communicate()
    stderr_text = stderr.decode().strip()

    if pipe.returncode != 0:
        raw = f'git clone failed with exit code {pipe.returncode}: {stderr_text}'
        friendly = humanize_git_clone_error(stderr_text)
        message = f'{friendly}\n\n{raw}' if friendly else raw
        raise RuntimeError(message)

    _write_package_metadata(
```

with:

```python
    """Materialize bundled template files into `package_name`, run `just init`."""
    ...
    _materialize_template(new_package_path)

    _write_package_metadata(
```

(The `dry_run` short-circuit and preflight call ahead of this stay as-is.)

#### 5. Rewrite unit tests for the copy + git-init/add flow
**File**: `tests/test_main.py`
**Action**: modify

The new in-order `Popen` sequence is **4 calls**: `git init`, `git add`,
`just init`, `just check`. Tests that run `init_new_package` to completion must
also no-op the filesystem copy and the resource resolution.

**Shared mock pattern** (add to every test below that previously ran the full
flow). `as_file` is used as a context manager, so configure its
`return_value.__enter__`; `copytree` is patched to a no-op (target dir is never
created, so `_write_package_metadata` hits its existing missing-file branch and
returns quietly, exactly as today):

```python
with (
    patch('modernpackage.main.Popen') as popen_mock,
    patch('modernpackage.main.run') as run_mock,
    patch('modernpackage.main.shutil.copytree'),
    patch('modernpackage.main.importlib.resources.as_file') as as_file_mock,
):
    run_mock.return_value = MagicMock(returncode=0, stderr='')
    as_file_mock.return_value.__enter__.return_value = Path('/tmp/fake_template')  # noqa: S108
    popen_mock.return_value.returncode = 0
    popen_mock.return_value.communicate.return_value = (b'', b'')
    init_new_package('mypackage')
```

Concrete edits:

- `test_init_new_package` (`:288-297`): apply the shared mock pattern; change
  `assert popen_mock.call_count == 3` → `== 4`.
- `test_init_new_package_normalizes_name` (`:300-316`): apply mocks. Replace the
  clone-target assertion (`call_args_list[0]`) with the `git init` target and
  the `just init` call now at **index 2**:
  ```python
  git_init_call = popen_mock.call_args_list[0]
  assert git_init_call.args[0] == ['git', 'init', '-b', 'main']
  assert git_init_call.kwargs['cwd'] == Path.cwd() / 'my_cool_package'

  init_call = popen_mock.call_args_list[2]
  assert init_call.args[0] == ['just', 'init', 'my_cool_package']
  assert init_call.kwargs['cwd'] == Path.cwd() / 'my_cool_package'
  ```
- `test_init_new_package_runs_just_check` (`:319-330`): apply mocks; `just check`
  is now the **4th** call → `third_call = popen_mock.call_args_list[3]`.
- `test_init_new_package_git_clone_failure` (`:333-342`): **replace** with a
  copy-failure test:
  ```python
  def test_init_new_package_template_copy_failure() -> None:
      with (
          patch('modernpackage.main.Popen') as popen_mock,
          patch('modernpackage.main.run') as run_mock,
          patch('modernpackage.main.importlib.resources.as_file') as as_file_mock,
          patch(
              'modernpackage.main.shutil.copytree',
              side_effect=PermissionError('denied'),
          ),
      ):
          run_mock.return_value = MagicMock(returncode=0, stderr='')
          as_file_mock.return_value.__enter__.return_value = Path('/tmp/fake')  # noqa: S108
          with pytest.raises(RuntimeError, match='check filesystem permissions'):
              init_new_package('mypackage')
      assert popen_mock.call_count == 0
  ```
- `test_init_new_package_just_not_installed` (`:345-356`): the `Popen`
  side-effect list gains the two git steps before `just init` raises
  `FileNotFoundError`:
  ```python
  git_init_mock = MagicMock(returncode=0)
  git_init_mock.communicate.return_value = (b'', b'')
  git_add_mock = MagicMock(returncode=0)
  git_add_mock.communicate.return_value = (b'', b'')
  ...
  popen_mock.side_effect = [git_init_mock, git_add_mock, FileNotFoundError('just not found')]
  ```
  (add `shutil.copytree` + `as_file` mocks; keep the `match=r'just.*install'`).
- `test_init_new_package_just_init_failure` (`:359-373`): same prefix; sequence
  `[git_init_mock, git_add_mock, just_init_mock(returncode=1)]`; keep the
  `match='just init failed with exit code 1'`.
- `test_init_new_package_reports_check_passed` (`:631-643`): add `copytree`/
  `as_file` mocks; behavior assertions unchanged.
- `test_init_new_package_prints_summary_on_success` (`:661-678`): add mocks;
  change `assert popen_mock.call_count == 3` → `== 4`.
- `test_init_new_package_reports_check_failed` (`:708-729`): sequence becomes
  `[git_init_mock, git_add_mock, just_init_mock, just_check_mock(returncode=1)]`;
  add `copytree`/`as_file` mocks.
- `test_run_preflight_checks_prints_full_checklist_on_clean_run` (`:681-705`):
  add `copytree`/`as_file` mocks so the full run does not touch the filesystem.
  Checklist assertions stay 4-line in this phase (the `template remote reachable`
  line is removed in Phase 3).

The remaining preflight-failure tests (`test_verify_required_tools_missing_*`,
`:376-418`, `:429-445`) abort before scaffolding (`popen_mock.call_count == 0`)
and need **no** copy mocks — leave unchanged.

#### 6. Rewrite the e2e test to exercise the real bundled template
**File**: `tests/test_e2e.py`
**Action**: modify

Switch from cloning `REPO_ROOT` to building+installing the wheel and scaffolding
offline. Keep the post-scaffold assertions (`test_e2e.py:82-103`) intact. Update
the module docstring to drop the clone-deviation note.

Replace the clone step (`test_e2e.py:63-64`) with a build → install-into-venv →
materialize flow. The simplest faithful rewrite materializes the bundled
`_template` directly from the built wheel into `destination`, then continues with
the existing metadata + `just init` + `just check` assertions:

```python
import zipfile

def _build_wheel(tmp_path: Path) -> Path:
    out = tmp_path / 'wheel'
    build = _run(['uv', 'build', '--wheel', '--out-dir', str(out)], cwd=REPO_ROOT)
    assert build.returncode == 0, f'uv build failed:\n{build.stdout}\n{build.stderr}'
    wheels = sorted(out.glob('*.whl'))
    assert wheels, 'no wheel produced'
    return wheels[-1]


def _extract_template(wheel_path: Path, destination: Path) -> None:
    prefix = 'modernpackage/_template/'
    with zipfile.ZipFile(wheel_path) as archive:
        members = [n for n in archive.namelist() if n.startswith(prefix) and not n.endswith('/')]
        assert members, 'wheel has no bundled _template tree'
        for name in members:
            relative = name[len(prefix):]
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
```

In `test_scaffolded_package_passes_check`, replace the `git clone` with:

```python
    wheel_path = _build_wheel(tmp_path)
    destination.mkdir()
    _extract_template(wheel_path, destination)
    init_git = _run(['git', 'init', '-b', 'main'], cwd=destination, env=os.environ | _GIT_IDENTITY_ENV)
    assert init_git.returncode == 0, f'git init failed:\n{init_git.stderr}'
    add = _run(['git', 'add', '-A'], cwd=destination, env=os.environ | _GIT_IDENTITY_ENV)
    assert add.returncode == 0, f'git add failed:\n{add.stderr}'
```

Everything from `main._write_package_metadata(...)` onward (`:66-103`) stays
unchanged. The `git`/`just`/`uv` skip guard (`:55-57`) stays.

> Note: this e2e exercises the **bundled** template extracted from a real wheel
> (the design's "verify against the built wheel, not just the editable install"
> risk). It does not invoke `init_new_package` through `importlib.resources`
> against an installed wheel because that would require a throwaway venv install;
> the wheel-extraction path validates the same bundled bytes. The fully-offline
> `init_new_package` path is covered by the manual verification below.

### Verification
#### Automated
- [ ] `just check` passes (unit suite green for the copy + git-init/add +
  init/check sequence): `just check`.
- [ ] No `git clone` / `ls-remote` left in the scaffolding code path:
  ```bash
  ! rg -n "git', 'clone|git clone|ls-remote" modernpackage/main.py
  ```
  exits 0.

#### Manual
- [ ] Offline e2e (network namespace removed) — scaffold from the installed
  wheel and confirm substituted metadata + renamed source dir:
  ```bash
  uv build && python -m venv /tmp/mp && /tmp/mp/bin/pip install dist/*.whl && cd /tmp && unshare -rn /tmp/mp/bin/modernpackage demopkg && test -d /tmp/demopkg/demopkg && grep -q "0.0.1" /tmp/demopkg/demopkg/__init__.py && ! grep -q "email@example.com" /tmp/demopkg/pyproject.toml
  ```
  exits 0. (Scaffold built with networking disabled; `just check` inside the
  scaffold still needs network for `uv sync`/`pip-audit`, so this checks the
  scaffold materialization, not the inner `just check`.) Clean up with
  `rm -rf /tmp/demopkg /tmp/mp`.
- [ ] If `unshare` is unavailable, run the same command **without** `unshare -rn`
  and additionally assert the code has no network template fetch:
  ```bash
  ! rg -n "git clone|ls-remote" modernpackage/main.py
  ```
  exits 0.
- [ ] Full e2e suite (network + tools required): `just test-e2e` → `1 passed`.

---

## Phase 3: Retire dead network machinery, dry-run text, and docs

Remove the now-unreachable remote-probe and clone-error code, fix the dry-run
plan wording, drop the corresponding tests, and update the in-scope docs. Pure
cleanup — if it slips, Phases 1–2 still deliver offline scaffolding.

### Changes

#### 1. Delete dead network code in `main.py`
**File**: `modernpackage/main.py`
**Action**: delete / modify

- Delete `_GIT_CLONE_ERROR_MESSAGES` list (`main.py:19-52`) — every branch was
  clone/network-specific and is now unreferenced.
- Delete `humanize_git_clone_error` (`main.py:78-84`) — unused after Phase 2.
- Delete `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`main.py:73-75`).
- Delete `_verify_template_remote_reachable` (`main.py:647-680`).
- Delete its registry entry in `_run_preflight_checks`
  (`main.py:700`): `PreflightCheck('template remote reachable', _verify_template_remote_reachable),`.
  The remaining 3 checks (name valid, required tools, target dir absent) stay.
- Remove `TimeoutExpired` from the subprocess import (`main.py:11`) → 
  `from subprocess import PIPE, Popen, run`. (`run` stays — used by
  `_git_config_default`, `main.py:241`.)
- Update the `_TEMPLATE_REPOSITORY_URL` comment (`main.py:69-71`, Decision 6) to
  note it is **metadata-only** now:
  ```python
  # Template repository homepage URL — retained only as the metadata-replacement
  # target in `_write_package_metadata` (no longer cloned or probed).
  _TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'
  ```
- `git` stays in `_REQUIRED_TOOLS` (`main.py:56`) — the re-stage step and
  `just init` need it.

#### 2. Fix the dry-run plan wording
**File**: `modernpackage/main.py`
**Action**: modify (`_format_dry_run_plan`, `main.py:537-551`)

Replace the clone line and update the docstring:

```python
    Reports the actions a real run would take at the level the code knows:
    target directory, the bundled-template copy, pyproject.toml metadata
    substitutions (None fields keep the template default), and the documented
    `just init` outcomes (directory rename, version reset).
    """
    ...
    lines = [
        _DRY_RUN_HEADER,
        f'  copy bundled template into {target_path}',
        '  update pyproject.toml metadata:',
    ]
```

(`_TEMPLATE_REPOSITORY_URL` is no longer referenced by the dry-run plan; it
remains used only in `_write_package_metadata`.)

#### 3. Remove obsolete tests; fix preflight/dry-run assertions
**File**: `tests/test_main.py`
**Action**: delete / modify

- Remove from the import block (`:10-33`): `_verify_template_remote_reachable`
  and `humanize_git_clone_error`; remove `from subprocess import TimeoutExpired`
  (`:4`) — only the deleted probe tests used it.
- Delete tests for deleted symbols:
  - `test_humanize_git_clone_error_network` / `_repo_not_found` / `_auth` /
    `_directory_exists` / `_unknown_returns_none` (`:595-628`).
  - `test_verify_template_remote_reachable_returns_none_when_reachable` /
    `_raises_on_resolve_host` / `_raises_on_repo_not_found` / `_raises_on_timeout`
    (`:1288-1326`).
  - `test_init_new_package_aborts_when_remote_unreachable` (`:751-761`) and
    `test_init_new_package_git_clone_network_failure` (`:732-748`) — both depend
    on the removed clone/probe path.
  - `test_run_preflight_checks_marks_failing_check_and_aborts` (`:764-783`) —
    asserts `[FAIL] template remote reachable`, which no longer exists.
- `test_run_preflight_checks_prints_full_checklist_on_clean_run` (`:681-705`):
  drop the `'  [ok]   template remote reachable'` entry from `expected` (now 3
  `[ok]` lines).
- `test_run_preflight_checks_aborts_on_earlier_check_without_later_lines`
  (`:786-806`): remove the now-vacuous
  `assert 'template remote reachable' not in out` line (`:805`); keep the rest.
- `test_format_dry_run_plan_reports_known_actions` (`:1382-1397`): replace
  `assert 'https://github.com/albertas/modernpackage' in plan` with
  `assert 'copy bundled template into' in plan`; keep the other assertions
  (`/tmp/foo`, `Ada Lovelace`, `keeps template default`, `modernpackage/ -> foo/`,
  `0.0.1`).
- `test_main_surfaces_stderr_on_failure` (`:557`) and
  `test_main_returns_one_on_failure` (`:574`): the `RuntimeError('git clone
  failed with exit code 1: boom')` side-effect string is arbitrary mock text;
  update to `RuntimeError('cannot materialize the package template ...: boom')`
  so tests don't reference removed wording. Assertions (`'boom'` present, result
  `== 1`) stay.

#### 4. Update in-scope docs
**File**: `docs/invocation.md`, `docs/specification.md`, `docs/overview.md`
**Action**: modify

`docs/invocation.md`:
- `:19` — exit-code-1 cause: replace `git clone` with `template copy`.
- `:54` — dry-run bullet: "The template URL that would be cloned" → "The bundled
  template that would be copied".
- `:58` — "no clone occurs" → "no copy occurs".
- `:72`, `:196` — remove the `  [ok]   template remote reachable` line from both
  checklist examples.
- `:74` — `clone https://...modernpackage into ...` → `copy bundled template into
  /home/user/my_package`.
- `:87` — remove "(including a network probe to verify the template repository is
  reachable)".
- `:147` — "All source files cloned from `https://...`" → "All source files
  copied from the wheel-bundled template".
- `:199` — "proceeds to clone, initialize, and validate" → "proceeds to copy,
  initialize, and validate".
- `:203-208` — "four checks" → "three checks"; delete check #4
  ("Template remote reachable …").
- `:212`, `:257` — drop "before attempting to clone"/"any clone or filesystem
  operation" → "before any filesystem operation".
- `:259-283` — delete the entire "Example: Template remote unreachable" block.
- `:285-340` — rewrite the "Failure path" clone section: the failure now comes
  from copy/`git init` (friendly `cannot materialize the package template …
  check filesystem permissions`); delete the five `git clone failed …` example
  blocks (network/not-found/auth/dir-exists/permission) and the unknown-error
  fallback paragraph.
- `:348`, `:356`, `:383`, `:397`, `:580` — replace remaining "clone"/"cloned"
  phrasing with copy/materialize wording (e2e step 1 `:397` → "the bundled
  template is materialized and produces a copy").

`docs/specification.md`:
- `:15` — "`init_new_package()` clones and initializes" → "materializes the
  bundled template and initializes".
- `:27` — ASCII diagram: `├─▶ git clone albertas/modernpackage  ./<name>` →
  `├─▶ copy bundled _template/ → ./<name>  (+ git init/add)`.
- `:57` — flow step 2: "Spawns first `subprocess.Popen`: `git clone …`" →
  "Copies the wheel-bundled `_template/` into the target via
  `shutil.copytree`, then runs `git init -b main` + `git add -A`".
- `:63`, `:140`, `:144` — replace "cloned repository"/"clones this very
  repository"/"`git clone` … fail" with copy/materialize equivalents.

`docs/overview.md`:
- `:7` — "clones itself to a new directory" → "copies the bundled template to a
  new directory".
- `:10` — drop "and verify the template remote is reachable (via a `git
  ls-remote` probe with a timeout)"; "before any git clone" → "before any copy".
- `:55` — "proceeds to the clone step" → "proceeds to the copy step".
- `:57` — "prevents git clone from failing" → "prevents the copy from failing".
- `:58` — delete check #4 ("Template remote reachability …") entirely.
- `:59` — "Before cloning and initialization" → "Before copying and
  initialization"; "clone directory" → "target directory".
- `:62` — rewrite the "Single-file CLI" paragraph: "orchestrates `git clone` +
  `just init` + `just check`" → "orchestrates a bundled-template copy +
  `just init` + `just check`"; drop the clone-error pattern sentence and replace
  with the copy-failure message ("cannot materialize the package template …").

### Verification
#### Automated
- [ ] `just check` passes (suite green after deletions): `just check`.
- [ ] No dead network symbols remain in code:
  ```bash
  ! rg -n "_verify_template_remote_reachable|_REMOTE_REACHABILITY_TIMEOUT_SECONDS|humanize_git_clone_error|_GIT_CLONE_ERROR_MESSAGES|ls-remote" modernpackage/
  ```
  exits 0.
- [ ] No clone/probe wording in the **in-scope** docs:
  ```bash
  ! rg -n "git clone|ls-remote|reachab" docs/invocation.md docs/specification.md docs/overview.md
  ```
  exits 0.

#### Manual
- [ ] Dry run describes a copy, not a clone (after `pip install -e .` or via
  `uv run`):
  ```bash
  cd /tmp && uv run --project /home/niekas/tools/modernpackage modernpackage --dry-run demopkg | grep -qi copy && ! (uv run --project /home/niekas/tools/modernpackage modernpackage --dry-run demopkg | grep -qi clone)
  ```
  exits 0.
- [ ] Preflight prints exactly 3 `[ok]` lines (no "template remote reachable"):
  ```bash
  cd /tmp && uv run --project /home/niekas/tools/modernpackage modernpackage --dry-run demopkg | grep -c '\[ok\]'
  ```
  prints `3`.

---

## Resolved decisions / assumptions

1. **Inherited `force-include` block in the scaffolded `pyproject.toml`**
   (structure "Open decision"): **leave as-is** (default). The scaffold never
   runs `uv build` during `just check`, so the inert block cannot break the
   scaffold; pruning it would be unrequested scope. The e2e `just check` passing
   confirms inertness.
2. **`humanize_git_clone_error` / `_GIT_CLONE_ERROR_MESSAGES`** (structure Phase
   3 "decide during impl"): **remove entirely** — both are fully unreferenced
   after Phase 2; copy failures use the single `_TEMPLATE_COPY_ERROR_MESSAGE`.
3. **`.gitlab-ci.yml`** not in the curated bundle (see Phase 1 assumption) —
   excluded by omission, consistent with `structure.md`'s explicit list.
4. **Docs scope** — see deviation below.

## Deviations from the structure outline

- **Phase 3 docs verification narrowed.** `structure.md` lists only
  `docs/invocation.md`, `docs/specification.md`, `docs/overview.md` as the docs
  to edit, but its stated verify command `! rg -n "git clone|ls-remote|reachab"
  docs/` greps **all** of `docs/`. `docs/architecture.md`, `docs/data_flows.md`,
  and `docs/vision.md` also contain those patterns and are **not** in the design's
  documented scope ("Docs drift" risk lists only the three files). Per
  CLAUDE.md §3 (surgical changes / only what's described), I edit exactly the
  three in-scope files and **scope the verify grep to those three files**.
  `docs/architecture.md` and `docs/data_flows.md` will retain stale references to
  the deleted `_verify_template_remote_reachable` / `humanize_git_clone_error` /
  clone flow, and `docs/vision.md` keeps its (intentionally aspirational) offline
  narrative. **Flag for the human**: a follow-up pass over
  `architecture.md`/`data_flows.md` is advisable but out of this task's scope.
- **E2E strategy** (Phase 2 #6): exercises the bundled template by extracting it
  from a freshly built wheel rather than installing the wheel into a venv and
  calling `init_new_package`. This validates the same bundled bytes against a
  real wheel (the design's stated risk) without a venv-install dependency in the
  test; the installed-wheel offline path is covered by the Phase 2 manual
  `unshare` check.
