# Implementation Plan

## Overview

A freshly scaffolded package ships without the self-replicating CLI
(`<module>/main.py`), its tests, its docs, or its `[project.scripts]` entry
points, and still passes `just check`. This is achieved by adding a single
`_strip_scaffolding(package_path)` step that mutates the clone between
`_write_package_metadata` and the `just init` subprocess, so the rename `sed`
and the lone `git commit` capture an already-clean tree. The template repo's own
files are untouched.

## Context (verified against the live tree)

- `modernpackage/main.py` already imports `shutil` (`main.py:5`) and `Path`
  (`main.py:10`) — no new imports needed for `_strip_scaffolding`. Add `import re`
  only if a regex approach is used; the line-based helper below avoids it (`re`
  is already imported at `main.py:4` regardless).
- `_write_package_metadata` is called at `main.py:755-762`; the `just init`
  `Popen` is built at `main.py:764-771`. The strip call goes strictly between
  these two.
- `pyproject.toml` `[project.scripts]` table is `pyproject.toml:23-25`, bracketed
  by a blank line above (`:22`) and the `[project.optional-dependencies]` header
  below (`:27`).
- Default `pytest` addopts (`pyproject.toml:40`) include
  `--cov-fail-under=95.0 -m 'not e2e'`. **Any `-k`-filtered subset run must add
  `--no-cov`**, otherwise the partial selection trips the 95% gate and exits
  non-zero. This is a deviation from the exact commands in `structure.md`, which
  omit `--no-cov`; the underlying intent (subset exits 0) is preserved.

---

## Phase 1: `_strip_scaffolding` core + unit tests

Implement the strip function and its helpers; cover behavior directly with
`tmp_path` tests that seed a fake clone tree. No clone/subprocess needed.

### Changes

#### 1. New constants + helpers in `modernpackage/main.py`
**File**: `modernpackage/main.py`
**Action**: modify (add new constants and two functions)

Place the constants near `_write_package_metadata` / `_apply_license` (after
`_apply_license`, before `class PreflightCheck` at `main.py:500`), and the
functions immediately after them. Mirror the constant-driven loop style of
`_METADATA_FIELDS`.

```python
# Clone-relative paths removed wholesale from a generated package. Looped over
# like _METADATA_FIELDS; absent entries are tolerated (clone-shape-agnostic).
_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...] = (
    'modernpackage/main.py',
    'tests/test_e2e.py',
    'docs',
    'BACKLOG.md',
)

# Stub tests/test_main.py: pytest needs >=1 collected test (empty collection
# exits non-zero), and importing the package keeps --cov-fail-under=95.0 happy
# (after main.py is deleted the only package code is __version__, run on import).
# Written with the literal `modernpackage` token so `just init`'s rename sed
# (Justfile:61-66) rewrites the import to the new module name.
_TEST_MAIN_STUB: str = """\
from modernpackage import __version__


def test_version() -> None:
    assert __version__ == '0.0.1'
"""

# Minimal generic README (pyproject.toml:7 requires `readme = "README.md"`).
# The `modernpackage` token is renamed by `just init` to the new module name.
_README_STUB: str = """\
# modernpackage

A Python package.
"""


def _remove_project_scripts(pyproject_path: Path) -> None:
    """Remove the [project.scripts] table from the cloned pyproject.toml.

    Deletes the header line, its entries, and the trailing blank line, leaving
    surrounding tables ([project.urls], [project.optional-dependencies], the
    e2e marker, the vupi dep, [tool.deadcode]) intact. No-op if the table or the
    file is absent (graceful boundary degradation, like _write_package_metadata).
    """
    try:
        lines = pyproject_path.read_text().splitlines(keepends=True)
    except FileNotFoundError:
        return
    try:
        start = lines.index('[project.scripts]\n')
    except ValueError:
        return
    end = start + 1
    while end < len(lines) and not lines[end].startswith('['):
        end += 1
    del lines[start:end]
    pyproject_path.write_text(''.join(lines))


def _strip_scaffolding(package_path: Path) -> None:
    """Remove the scaffolder's own CLI, tests, docs, and entry points from a clone.

    Mutates the cloned tree in place. Run before `just init` so the rename sed
    (Justfile:61-66) and the single git commit (Justfile:72) capture an already
    -clean tree. Deletes tolerate absent paths; the stub writes assume the clone
    root and tests/ exist (always true for a real clone). Stubs retain the
    literal `modernpackage` token so the rename sed rewrites their imports.
    """
    for relative_path in _SCAFFOLDING_PATHS_TO_DELETE:
        target = package_path / relative_path
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
    (package_path / 'tests' / 'test_main.py').write_text(_TEST_MAIN_STUB)
    (package_path / 'README.md').write_text(_README_STUB)
    _remove_project_scripts(package_path / 'pyproject.toml')
```

Notes / resolved decisions:
- **Deletes**: `docs` (a directory) uses `shutil.rmtree(..., ignore_errors=True)`;
  `modernpackage/main.py`, `tests/test_e2e.py`, `BACKLOG.md` (files) use
  `unlink(missing_ok=True)`. The `is_dir()` branch dispatches correctly and a
  missing path is simply skipped.
- **Complexity**: `_strip_scaffolding` = 1 loop + 1 if/else (mccabe ≈ 3);
  `_remove_project_scripts` = 2 try/except + 1 while + conditions (mccabe ≈ 5).
  Both ≤ 8 (`pyproject.toml:78-79`). No `# noqa: C901` needed.
- **README/stub token**: `# modernpackage` in `_README_STUB` is intentional — the
  rename sed turns it into `# <module>`. Same for `from modernpackage import` in
  `_TEST_MAIN_STUB`.
- **No `mkdir`**: stub writes assume `tests/` and the clone root exist (guaranteed
  by `git clone`). Unit tests that exercise tolerance seed an empty `tests/` dir.

#### 2. Unit tests in `tests/test_main.py`
**File**: `tests/test_main.py`
**Action**: modify (extend the import block + add tests)

Add to the `from modernpackage.main import (...)` block (`test_main.py:10-33`),
keeping alphabetical-ish grouping with existing private imports:

```python
    _remove_project_scripts,
    _strip_scaffolding,
```

Add a seed helper and tests (place near `_seed_pyproject` at
`test_main.py:1137`, e.g. after the metadata-write tests):

```python
def _seed_clone(tmp_path: Path) -> Path:
    """Seed a fake clone tree with all scaffolding files; return the root."""
    (tmp_path / 'modernpackage').mkdir()
    (tmp_path / 'modernpackage' / 'main.py').write_text('# cli\n')
    (tmp_path / 'modernpackage' / '__init__.py').write_text("__version__ = '0.0.1'\n")
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_e2e.py').write_text('# e2e\n')
    (tmp_path / 'tests' / 'test_main.py').write_text('# old tests\n')
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'overview.md').write_text('# docs\n')
    (tmp_path / 'BACKLOG.md').write_text('# backlog\n')
    (tmp_path / 'README.md').write_text('# scaffolder readme\n')
    source = Path(__file__).resolve().parent.parent / 'pyproject.toml'
    (tmp_path / 'pyproject.toml').write_text(source.read_text())
    return tmp_path


def test_strip_scaffolding_removes_cli_tests_docs(tmp_path: Path) -> None:
    _strip_scaffolding(_seed_clone(tmp_path))
    assert not (tmp_path / 'modernpackage' / 'main.py').exists()
    assert not (tmp_path / 'tests' / 'test_e2e.py').exists()
    assert not (tmp_path / 'docs').exists()
    assert not (tmp_path / 'BACKLOG.md').exists()
    assert (tmp_path / 'modernpackage' / '__init__.py').exists()  # marker kept


def test_strip_scaffolding_writes_test_main_stub(tmp_path: Path) -> None:
    _strip_scaffolding(_seed_clone(tmp_path))
    stub = (tmp_path / 'tests' / 'test_main.py').read_text()
    assert 'modernpackage' in stub  # token preserved for rename sed
    assert '0.0.1' in stub
    assert 'def test_version' in stub


def test_strip_scaffolding_writes_readme_stub(tmp_path: Path) -> None:
    _strip_scaffolding(_seed_clone(tmp_path))
    readme = (tmp_path / 'README.md').read_text()
    assert readme  # non-empty
    assert 'scaffolder readme' not in readme  # original replaced


def test_strip_scaffolding_removes_project_scripts(tmp_path: Path) -> None:
    _strip_scaffolding(_seed_clone(tmp_path))
    pyproject = (tmp_path / 'pyproject.toml').read_text()
    assert '[project.scripts]' not in pyproject
    assert 'modernpackage.main:main' not in pyproject
    assert '[project.optional-dependencies]' in pyproject  # neighbour intact
    assert 'vupi' in pyproject  # test dep intact
    assert tomllib.loads(pyproject)  # still valid TOML


def test_strip_scaffolding_tolerates_absent_paths(tmp_path: Path) -> None:
    # Only tests/ and pyproject.toml present; delete targets all absent.
    (tmp_path / 'tests').mkdir()
    source = Path(__file__).resolve().parent.parent / 'pyproject.toml'
    (tmp_path / 'pyproject.toml').write_text(source.read_text())
    _strip_scaffolding(tmp_path)  # must not raise
    assert (tmp_path / 'tests' / 'test_main.py').exists()
    assert (tmp_path / 'README.md').exists()


def test_remove_project_scripts_missing_file(tmp_path: Path) -> None:
    _remove_project_scripts(tmp_path / 'pyproject.toml')  # must not raise


def test_remove_project_scripts_no_table(tmp_path: Path) -> None:
    path = tmp_path / 'pyproject.toml'
    path.write_text('[project]\nname = "x"\n')
    _remove_project_scripts(path)  # no-op, must not raise
    assert path.read_text() == '[project]\nname = "x"\n'
```

`tomllib` is already imported at `test_main.py:1`.

### Verification
#### Automated
- [x] `just check` passes (ruff format + lint + complexity C901 + mypy strict +
  pytest with cov ≥ 95% + pip-audit).
- [x] `python -m pytest tests/test_main.py -k strip_scaffolding -q --no-cov`
  exits 0 (`--no-cov` required so the partial selection does not trip the 95%
  gate — see Context).
- [x] `python -m pytest tests/test_main.py -k remove_project_scripts -q --no-cov`
  exits 0.

#### Manual
- [x] `rg -n '_SCAFFOLDING_PATHS_TO_DELETE|_TEST_MAIN_STUB|_README_STUB|def _strip_scaffolding|def _remove_project_scripts' modernpackage/main.py`
  prints 5 definition lines.
- [x] `python -c "import shutil,tempfile,pathlib; from modernpackage import main; d=pathlib.Path(tempfile.mkdtemp()); (d/'modernpackage').mkdir(); (d/'modernpackage'/'main.py').write_text('x'); (d/'modernpackage'/'__init__.py').write_text(\"__version__='0.0.1'\"); (d/'tests').mkdir(); (d/'docs').mkdir(); (d/'BACKLOG.md').write_text('x'); (d/'README.md').write_text('x'); (d/'pyproject.toml').write_text(open('pyproject.toml').read()); main._strip_scaffolding(d); print(not (d/'modernpackage'/'main.py').exists() and not (d/'docs').exists() and '[project.scripts]' not in (d/'pyproject.toml').read_text())"`
  prints `True`.

---

## Phase 2: Wire into `init_new_package` + orchestration tests

Call `_strip_scaffolding` from `init_new_package` between the metadata write and
the `just init` `Popen`, and update the happy-path / failure-path orchestration
tests to patch the new seam.

### Changes

#### 1. Insert the strip call in `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify

Insert immediately after the `_write_package_metadata(...)` call
(`main.py:755-762`) and before the `try:`/`Popen(['just', 'init', ...])` block
(`main.py:764`):

```python
    _write_package_metadata(
        new_package_path,
        author_name=author_name,
        author_email=author_email,
        description=description,
        package_license=package_license,
        repository_url=repository_url,
    )

    _strip_scaffolding(new_package_path)

    try:
        pipe = Popen(  # noqa: S603
            ['just', 'init', module_name],  # noqa: S607
```

Signature of `init_new_package` is unchanged.

#### 2. Patch the seam in existing orchestration tests
**File**: `tests/test_main.py`
**Action**: modify

These tests reach the strip call with no real clone dir, so `_strip_scaffolding`
must be patched on `modernpackage.main` (design Decision 8). Add
`patch('modernpackage.main._strip_scaffolding')` to the `with` block of:
- `test_init_new_package` (`:288`)
- `test_init_new_package_normalizes_name` (`:300`)
- `test_init_new_package_runs_just_check` (`:319`)
- `test_init_new_package_just_not_installed` (`:345`)
- `test_init_new_package_just_init_failure` (`:359`)

`test_init_new_package_git_clone_failure` (`:333`) raises before the strip call,
so it needs **no** change.

Example for `test_init_new_package`:

```python
def test_init_new_package() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding') as strip_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    assert popen_mock.call_count == 3  # noqa: PLR2004
    strip_mock.assert_called_once_with(Path.cwd() / 'mypackage')
```

For `test_init_new_package_normalizes_name` and
`test_init_new_package_runs_just_check`, add the `strip_mock` patch line
(assertion optional; keep their existing assertions). For
`test_init_new_package_just_not_installed` and
`test_init_new_package_just_init_failure`, add the patch line so the strip call
is a no-op and execution reaches the `Popen` side-effect under test.

#### 3. New ordering test
**File**: `tests/test_main.py`
**Action**: modify (add one test after `test_init_new_package_runs_just_check`)

```python
def test_init_new_package_strips_before_just_init() -> None:
    calls: list[str] = []
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._write_package_metadata') as metadata_mock,
        patch('modernpackage.main._strip_scaffolding') as strip_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        metadata_mock.side_effect = lambda *a, **k: calls.append('metadata')
        strip_mock.side_effect = lambda *a, **k: calls.append('strip')
        popen_mock.side_effect = lambda *a, **k: (
            calls.append('init') if a[0][:2] == ['just', 'init'] else None,
            MagicMock(returncode=0, communicate=lambda: (b'', b'')),
        )[1]
        init_new_package('mypackage')
    assert calls.index('metadata') < calls.index('strip') < calls.index('init')
    strip_mock.assert_called_once_with(Path.cwd() / 'mypackage')
```

Resolved assumption: the ordering test stubs `Popen` with a `side_effect` that
appends `'init'` only for the `just init` invocation, so the relative order of
`metadata` → `strip` → `just init` is asserted without a real filesystem. If
this side-effect proves awkward under mypy/ruff, fall back to a simpler check:
assert `metadata_mock` and `strip_mock` are both called once and rely on the
per-test `strip_mock.assert_called_once_with(...)` plus the existing
`popen_mock.call_count == 3` from `test_init_new_package` — but prefer the
ordering assertion above.

### Verification
#### Automated
- [x] `just check` passes on the template repo.
- [x] `python -m pytest tests/test_main.py -k init_new_package -q --no-cov`
  exits 0.

#### Manual
- [x] `rg -n '_strip_scaffolding\(new_package_path\)' modernpackage/main.py`
  prints exactly one line, and its line number is greater than the
  `_write_package_metadata(` call and less than the `['just', 'init', module_name]`
  line. Confirm with:
  `python -c "import re,pathlib; s=pathlib.Path('modernpackage/main.py').read_text().splitlines(); meta=[i for i,l in enumerate(s) if '_write_package_metadata(' in l and 'def ' not in l]; strip=[i for i,l in enumerate(s) if '_strip_scaffolding(new_package_path)' in l]; init=[i for i,l in enumerate(s) if \"'just', 'init', module_name\" in l]; print(meta[0] < strip[0] < init[0])"`
  prints `True`.
- [x] `rg -c 'modernpackage.main._strip_scaffolding' tests/test_main.py` prints
  `11` (5 listed + 6 additional tests that also call `init_new_package` — plan
  expected `6` but the live test file had more orchestration tests than the plan
  anticipated; all needed the patch and now pass).

---

## Phase 3: Extend e2e test to assert a clean generated package

Drive the new strip step in the e2e flow and assert the generated package is
scaffolding-free and still passes `just check`.

### Changes

#### 1. Call the strip step + add assertions
**File**: `tests/test_e2e.py`
**Action**: modify

After the `main._write_package_metadata(destination, ...)` call
(`test_e2e.py:66-73`), add the strip step (mirroring how the e2e test calls
`_write_package_metadata` directly, design Decision 1):

```python
    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e generated package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )

    main._strip_scaffolding(destination)  # noqa: SLF001
```

After the existing `just check` assertion (`test_e2e.py:92-93`), and reusing the
existing `source_dir` (the renamed module dir, defined at `test_e2e.py:82`) and
`pyproject` (read at `:95`), add:

```python
    # Scaffolding removed from the generated package.
    assert not (source_dir / 'main.py').exists()  # self-replicating CLI gone
    assert not (destination / 'tests' / 'test_e2e.py').exists()
    assert not (destination / 'docs').exists()
    assert not (destination / 'BACKLOG.md').exists()
    assert '[project.scripts]' not in pyproject  # no dangling entry point
    assert 'modernpackage.main:main' not in pyproject
    # __init__.py version 0.0.1 already asserted at lines 88-90; check stub test.
    stub = (destination / 'tests' / 'test_main.py').read_text()
    assert '0.0.1' in stub
```

Resolved details:
- The deleted CLI lives at `source_dir / 'main.py'` (the renamed module dir,
  e.g. `scaffold_check_pkg/main.py`), not `destination / 'main.py'`. `structure.md`
  wrote `source_dir / 'main.py'` — confirmed correct here.
- The stub `tests/test_main.py` import was `from modernpackage import __version__`
  but `just init`'s rename sed rewrites `modernpackage` → `<module>`, so the stub
  imports the renamed package and the inner `just check` (run at `:92`) collects
  and passes it. The `0.0.1` assertion checks the version literal, which is not
  renamed.
- Coverage inside the generated package: after `main.py` is deleted, the only
  package module is `__init__.py` (its `__version__` line runs on import via the
  stub test), so the inner `--cov-fail-under=95.0` is satisfied. The fact that
  the inner `just check` returns 0 (existing assertion at `:93`) is the proof.

### Verification
#### Automated
- [ ] `just test-e2e` exits 0 (runs `pytest -m e2e --no-cov`). **Requires
  network + `git`/`just`/`uv` on PATH**; the inner `just check` runs `uv sync`
  and a networked `pip-audit`, so this is minutes-long and fails offline
  (`test_e2e.py:7-15`). Run in an online environment.

#### Manual
- [x] `rg -n 'main._strip_scaffolding\(destination\)' tests/test_e2e.py` prints
  one line, located after the `main._write_package_metadata(` call and before the
  `['just', 'init', module_name]` `_run` call. Confirm with:
  `python -c "import pathlib; s=pathlib.Path('tests/test_e2e.py').read_text().splitlines(); meta=[i for i,l in enumerate(s) if 'main._write_package_metadata(' in l]; strip=[i for i,l in enumerate(s) if 'main._strip_scaffolding(destination)' in l]; init=[i for i,l in enumerate(s) if \"'just', 'init', module_name\" in l]; print(meta[0] < strip[0] < init[0])"`
  prints `True`.
- [x] `rg -n "assert '\[project.scripts\]' not in pyproject|not \(source_dir / 'main.py'\).exists\(\)|not \(destination / 'docs'\).exists\(\)" tests/test_e2e.py`
  prints the three new assertion lines.

---

## Testing Checkpoints

- **After Phase 1**: `python -m pytest tests/test_main.py -k 'strip_scaffolding or remove_project_scripts' -q --no-cov` green; `just check` green
  (function ruff-clean, mypy-strict, mccabe ≤ 8, covered by the new tests).
- **After Phase 2**: `just check` green; `python -m pytest tests/test_main.py -q`
  green. The strip is invoked between metadata write and `just init`; the
  template's own files are untouched and its scripts remain (removal is on the
  clone at runtime).
- **After Phase 3**: `just test-e2e` green (online). A really-scaffolded package
  has no `main.py`, no `test_e2e.py`, no `docs/`, no `BACKLOG.md`, no
  `[project.scripts]`; `__init__.py` is `0.0.1`; the stub `tests/test_main.py`
  collects; inner `just check` returns 0.

## Notes / Deviations

- **`--no-cov` on subset runs** (Context + Phase 1/2 verification): `structure.md`'s
  `-k ... -q` commands omit it, but the live `--cov-fail-under=95.0` in
  `pyproject.toml:40` fails any partial selection. Added `--no-cov` to all
  subset commands; full-suite `just check` is unaffected.
- **No static `pyproject.toml` edit** (design Decisions 3 & 9): `[project.scripts]`
  is removed from the **clone** at runtime by `_remove_project_scripts`, so the
  template keeps its working `modernpackage`/`mp` console scripts. A reviewer
  expecting a static diff in the template `pyproject.toml` will not find one — by
  design.
- **Generated `Justfile` retains inert scaffolding recipes** (`init`, `test-e2e`,
  `vision`, `lifecycle`) per design "What We're NOT Doing": `just init` cannot
  cleanly delete itself mid-run. Out of scope; flagged as follow-up.
- **Ordering guarantee** (design "Open Risks"): the strip runs strictly before
  `just init` (Phase 2), so deletions are deleted-but-tracked until `just init`'s
  `git add .` stages them, `git grep` skips the deleted files, and the stubs
  retaining the `modernpackage` token are renamed correctly by the rename sed.
- **No `mkdir` in `_strip_scaffolding`**: stub writes assume the clone root and
  `tests/` exist (guaranteed by `git clone`); the tolerance unit test seeds an
  empty `tests/` dir to exercise the absent-delete-targets path.
