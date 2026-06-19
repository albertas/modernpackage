# Implementation Plan

## Overview

A package scaffolded with no extra flags provably contains **zero** backend or
frontend code, config, dependencies, recipes, or references, and the test suite
locks this in. The work is **verification only** — one fast mocked unit guard
(`tests/test_main.py`) plus one comprehensive e2e absence test
(`tests/test_e2e.py`), both deriving forbidden markers from the existing
`main.py` injection constants. No production behavior changes unless a test
surfaces a real bug.

Key facts confirmed against the codebase:
- `init_new_package` signature: `init_new_package(package_name, *, ..., backend=False, fullstack=False)` (`modernpackage/main.py:1007-1018`). No-flag call = `init_new_package('mypackage')`.
- The injector gate is `if backend or fullstack:` at `main.py:1065-1066`.
- No-flag mocked path makes exactly **3** `Popen` calls: clone, `just init`, `just check` (`tests/test_main.py:296-307`).
- Constants live at: `_BACKEND_DEPENDENCIES` (`main.py:565-571`), `_BACKEND_DEV_DEPENDENCIES` (`main.py:574`), `_BACKEND_RECIPES` (`main.py:579-588`), `_FRONTEND_RECIPES` (`main.py:595-614`).
- e2e flow to mirror: `tests/test_e2e.py:53-117` (`test_scaffolded_package_passes_check`): `git clone` local repo → `_write_package_metadata` → `_strip_scaffolding` → `just init` → assert on `destination` / `source_dir`.
- Test commands (from `Justfile`): `just test *args` (`Justfile:14-15`, applies `--cov-fail-under=95.0 -m 'not e2e'` from `pyproject.toml:40`), `just test-e2e *args` (`Justfile:17-18`, runs `-m e2e --no-cov`), `just check` (`Justfile:53`).

---

## Phase 1: Mocked no-flag injector guard (fast, no clone)

Pin the gate at `main.py:1065-1066` with a cheap unit test: a no-flag
`init_new_package` must invoke neither `_add_backend` nor `_add_frontend`, and
must make exactly the 3 expected subprocess calls. Complements the existing
positive guards (`test_main.py:1592-1603` backend, `1773-1820` fullstack).
Runs under default `pytest` (no `e2e` marker).

### Changes

#### 1. New mocked unit test
**File**: `tests/test_main.py`
**Action**: modify (append one test function)

Add the following test. Place it directly after
`test_init_new_package_invokes_add_backend_when_flag_set`
(ends `test_main.py:1603`) so it sits with the other gate tests. It follows the
`Popen`/`run`/`_strip_scaffolding` patch style of `test_main.py:296-307` and the
injector-patch style of `test_main.py:1592-1603`.

```python
def test_init_new_package_no_flags_injects_nothing() -> None:
    expected_popen_calls = 3  # clone, just init, just check
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend') as add_backend_mock,
        patch('modernpackage.main._add_frontend') as add_frontend_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    add_backend_mock.assert_not_called()
    add_frontend_mock.assert_not_called()
    assert popen_mock.call_count == expected_popen_calls
```

**Notes / assumptions**:
- `init_new_package`, `patch`, `MagicMock`, `Path` are already imported at the
  top of `tests/test_main.py` (used by the existing tests in this file). Do not
  add new imports.
- `_add_frontend` is patched even on the no-flag path purely to assert it is not
  called; patching a symbol that is never invoked is harmless and mirrors the
  no-call assertion intent.
- The exact 3 `Popen` calls are clone → `just init` → `just check`; `git add -A`
  only appears on the inject path (`test_main.py:1651-1666`), so its absence is
  implied by `call_count == 3`.

### Verification
#### Automated
- [x] `just test -- -k test_init_new_package_no_flags_injects_nothing` exits 0 and reports `1 passed` (proves the test is collected and exercises the guard). Note: ran as `uv run pytest --no-cov -k test_init_new_package_no_flags_injects_nothing` since `just test` with `-k` causes coverage to drop below gate.
- [x] `just test` exits 0 (full default selection still green; new test runs under `-m 'not e2e'`).

#### Manual
- [x] Confirm the test asserts both injectors absent: `grep -q 'add_backend_mock.assert_not_called' tests/test_main.py && grep -q 'add_frontend_mock.assert_not_called' tests/test_main.py` exits 0.
- [ ] Confirm it would fail if the gate regressed: temporarily change `main.py:1065` guard to `if True:`, run `just test -- -k test_init_new_package_no_flags_injects_nothing` and observe a failure (`add_backend_mock.assert_not_called` raises), then revert the edit. (Optional sanity check — revert immediately.)

---

## Phase 2: E2E no-flag absence test (full scaffold pipeline)

Add the primary deliverable: scaffold a no-flag package through the real strip +
`just init` flow and assert the **absence** of every backend/frontend marker.
Mirrors `test_scaffolded_package_passes_check` (`test_e2e.py:53-117`); leaves
that test unchanged.

### Changes

#### 1. New e2e absence test
**File**: `tests/test_e2e.py`
**Action**: modify (append one test function + one module-level `import re`)

Add `import re` to the import block (`test_e2e.py:17-20`, after `import os`).
Then append the test below after `test_scaffolded_backend_package_passes_check`
(ends `test_e2e.py:177`).

```python
import re  # add to the existing import block near test_e2e.py:17


_RECIPE_NAME_RE = re.compile(r'^([a-z][\w-]*)(?: \w+)*:', re.MULTILINE)


def _dependency_tokens() -> set[str]:
    """Bare package names from the backend dependency constants (no version/extras)."""
    deps = main._BACKEND_DEPENDENCIES + main._BACKEND_DEV_DEPENDENCIES  # noqa: SLF001
    return {re.split(r'[<>=\[ ]', dep, maxsplit=1)[0] for dep in deps}


def _recipe_tokens() -> set[str]:
    """Recipe names declared in the backend/frontend recipe constants."""
    recipes = main._BACKEND_RECIPES + main._FRONTEND_RECIPES  # noqa: SLF001
    return set(_RECIPE_NAME_RE.findall(recipes))


@pytest.mark.e2e
def test_scaffolded_package_has_no_backend_or_frontend(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'no-extras.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='A no-extras package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    source_dir = destination / module_name
    assert source_dir.is_dir()

    # 1. Backend/frontend directories never reach the package.
    for directory in ('backend_template', 'frontend_template', 'frontend', 'migrations'):
        assert not (destination / directory).exists(), f'unexpected dir: {directory}'

    # 2. Backend/container config files absent.
    for filename in ('alembic.ini', 'compose.yml', 'Containerfile', '.dockerignore'):
        assert not (destination / filename).exists(), f'unexpected file: {filename}'

    # 3. pyproject.toml carries no backend deps and keeps the empty list.
    pyproject = (destination / 'pyproject.toml').read_text()
    assert 'dependencies = []' in pyproject
    for token in _dependency_tokens():
        assert token not in pyproject, f'unexpected dependency token: {token}'

    # 4. Justfile carries no backend/frontend recipes.
    justfile = (destination / 'Justfile').read_text()
    for token in _recipe_tokens():
        assert token not in justfile, f'unexpected recipe: {token}'

    # 5. Package source dir contains no backend/frontend import tokens
    #    (scoped scan avoids incidental-substring false positives).
    import_tokens = (
        'import fastapi',
        'from fastapi',
        'import sqlalchemy',
        'from sqlalchemy',
        'import asyncpg',
        'import alembic',
        'import uvicorn',
        'from react',
        'vite',
    )
    source_text = '\n'.join(
        path.read_text() for path in source_dir.rglob('*') if path.is_file()
    )
    for token in import_tokens:
        assert token not in source_text, f'unexpected import token: {token}'
```

**Notes / assumptions**:
- `main`, `normalize_module_name`, `REPO_ROOT`, `REQUIRED_TOOLS`, `_run`,
  `_GIT_IDENTITY_ENV`, `os`, `shutil`, `Path`, `pytest` are already available in
  `tests/test_e2e.py` (used by the existing e2e tests). Only `re` is new.
- The test resolves `source_dir = destination / module_name` per
  `test_e2e.py:84` rather than a hardcoded `modernpackage/` path — `just init`
  sed-renames the module dir (Open Risk "`just init` token rename").
- `_dependency_tokens()` yields `{fastapi, sqlalchemy, asyncpg, alembic, uvicorn, httpx}`
  (strips version/extras via the first `<`/`>`/`=`/`[`/space). `_recipe_tokens()`
  yields `{migrate, makemigration, migration-check, frontend-install,
  frontend-build, frontend-test, frontend-lint, generate-client, frontend-check}`.
  Both are confirmed absent from the default `Justfile` (`Justfile:1-81`, no such
  recipes) and default `pyproject.toml` (`dependencies = []`, `pyproject.toml:18`).
- This test does **not** run `just check` (unlike `test_e2e.py:53-117`); the
  existing no-flag test already covers the `just check` pass, and the absence
  assertions do not require a build/sync. This keeps the new test cheaper while
  still exercising clone + strip + `just init`.
- `import_tokens` is the small explicit list permitted by design decision #5; it
  is scoped to `source_dir` (Open Risk "Token false-positives"). For a no-flag
  package `source_dir` contains essentially only `__init__.py`, so the scan is
  expected to be trivially clean — its value is locking the guarantee against
  future leakage.

### Verification
#### Automated
- [x] `just test-e2e -- -k test_scaffolded_package_has_no_backend_or_frontend` exits 0 and reports `1 passed` (not `0 selected` / `skipped` — confirms the `e2e` marker is applied and the test actually ran). Note: ran as `uv run pytest -m e2e --no-cov -k test_scaffolded_package_has_no_backend_or_frontend` since `just test-e2e` doesn't support `-k` flag directly.
- [ ] `just test-e2e` exits 0 (both pre-existing e2e tests plus the new one pass).
- [x] `just test` exits 0 and the new e2e test is **not** collected by the default selection (it carries `@pytest.mark.e2e`, excluded by `-m 'not e2e'`).

#### Manual
- [x] Confirm the test carries the marker and resolves the renamed dir: `grep -q '@pytest.mark.e2e' tests/test_e2e.py && grep -q 'source_dir = destination / module_name' tests/test_e2e.py` exits 0.
- [x] Confirm derived tokens are non-empty (guards against a silently-empty assertion loop): ran `uv run python -c "import re; from modernpackage import main; print(main._BACKEND_DEPENDENCIES, main._BACKEND_RECIPES[:30])"` — both constants are populated (`fastapi>=0.115`, `sqlalchemy[asyncio]>=2.0`, etc. and recipe text starting with `migrate: sync`).

---

## Phase 3: Full-suite + coverage gate confirmation

No new code — a verification checkpoint that the additions keep all gates green
and do not regress coverage below `--cov-fail-under=95.0` (`pyproject.toml:40`).

### Changes

**Files**: none.

### Verification
#### Automated
- [x] `just check` exits 0 (runs `check-format`, `check-lint`, `check-complexity`, `check-typecheck`, `test` with the coverage gate, and `audit` — `Justfile:53`). Coverage reached 98.34%.
- [ ] `just test-e2e` exits 0. NOTE: pre-existing failure in `test_scaffolded_backend_package_passes_check` — `backend_template/tests/test_app.py` and `backend_template/migrations/env.py` have unformatted code that causes the backend e2e test to fail (confirmed via `uv run ruff format --check backend_template/`). The new test `test_scaffolded_package_has_no_backend_or_frontend` passed (`.F.` — test 1 and 3 pass, test 2 is the pre-existing backend failure). Not introduced by Phase 3.

#### Manual
- [x] Confirm coverage did not drop below the gate: `just test` output shows `Required test coverage of 95.0% reached` (total 98.34%) and exits 0.
- [x] Confirm no stray edits beyond the two test files: `git diff --name-only modernpackage/ backend_template/ frontend_template/ Justfile` shows no output — no production code modified. (Docs/lifecycle files modified outside that scope are unrelated to the feature.)

---

## Testing Checkpoints

- **After Phase 1**: `just test` green; a no-flag `init_new_package` provably
  calls neither injector and makes exactly 3 subprocess calls. Fast guard in place.
- **After Phase 2**: `just test-e2e` green; a real no-flag scaffold provably has
  zero backend/frontend dirs, files, deps, recipes, and import tokens. Primary
  guarantee locked.
- **After Phase 3**: `just check` and `just test-e2e` both green; coverage ≥ 95.0.
  Safe to hand off — a future change reintroducing leakage now fails CI.

**Note**: every phase is a self-contained test slice. If Phase 2 or 3 fails,
Phase 1 remains independently valuable. No phase depends on another's code, only
on the shared, unchanged scaffolder.
