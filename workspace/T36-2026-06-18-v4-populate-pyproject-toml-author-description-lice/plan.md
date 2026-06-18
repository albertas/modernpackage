# Implementation Plan

## Overview

Populate the generated package's `pyproject.toml` with the supplied
author/email/description/license/repository values by adding a module-private
`_write_package_metadata` writer that applies targeted, TOML-escaped
`str.replace` substitutions on known template literals, called inside
`init_new_package` after the clone and before `just init`.

## Notes on deviations from `structure.md`

- **Notice style**: the codebase has no `rich`/`console`; existing boundary
  notices (`_load_config_file`, `main.py:236`) use plain `print(..., file=sys.stderr)`.
  The missing-`pyproject.toml` notice mirrors that (plain stderr), not literal
  `[dim]` markup. (structure.md said `[dim]`.)
- **License anchor**: the `license = "<value>"` key is inserted after the stable
  `readme = "README.md"` line (independent of `description`, which may be `None`),
  not after the `description` line. Keeps both keys inside `[project]`.
- **License helper split**: license handling lives in a separate `_apply_license`
  helper so `_write_package_metadata` stays under the McCabe max-complexity of 8
  (`pyproject.toml:79`).
- **e2e recipe**: the project exposes `just test-e2e` (`Justfile:16-17`), not
  `just test -- -m e2e`. Phase 3 uses `just test-e2e`.
- **Targeted-test invocation**: `just test -k <expr>` (the `test` recipe forwards
  `*args` to pytest, `Justfile:13-14`).

---

## Phase 1: Writer foundation + plain-string fields

### Changes

#### 1. Escape helper + writer

**File**: `modernpackage/main.py`
**Action**: modify (add two module-private helpers above `init_new_package`,
which starts at `main.py:373`)

```python
def _toml_escape(value: str) -> str:
    """Escape backslashes then double-quotes for safe TOML basic-string insertion."""
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _write_package_metadata(
    package_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
) -> None:
    """Replace template placeholders in the cloned pyproject.toml with supplied values.

    Each non-None field is applied as a targeted, TOML-escaped str.replace of a
    known template literal; None fields are skipped (design Decision 7). A missing
    pyproject.toml prints a notice and returns without raising (graceful boundary
    degradation, design Decision 8 — also lets the Popen-mocked unit tests, which
    never create a real clone, pass unchanged). The file is rewritten only if a
    substitution changed it.
    """
    pyproject_path = package_path / 'pyproject.toml'
    try:
        original = pyproject_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No pyproject.toml at {pyproject_path}; skipping metadata.',
            file=sys.stderr,
        )
        return

    updated = original
    if author_name is not None:
        updated = updated.replace('Name Surname', _toml_escape(author_name))
    if author_email is not None:
        updated = updated.replace('email@example.com', _toml_escape(author_email))
    if description is not None:
        updated = updated.replace(
            'Package configuration example using bleeding edge toolset.',
            _toml_escape(description),
        )
    if repository_url is not None:
        updated = updated.replace(
            'https://github.com/albertas/modernpackage',
            _toml_escape(repository_url),
        )
    # package_license handled in Phase 2 via _apply_license.

    if updated != original:
        pyproject_path.write_text(updated)
```

Placeholder literals (verified against the template `pyproject.toml`):
- `Name Surname` (`pyproject.toml:4`)
- `email@example.com` (`pyproject.toml:4`)
- `Package configuration example using bleeding edge toolset.` (`pyproject.toml:6`)
- `https://github.com/albertas/modernpackage` (`pyproject.toml:21`)

#### 2. Wire writer into `init_new_package`

**File**: `modernpackage/main.py`
**Action**: modify (`init_new_package`, `main.py:373-443`)

Remove the discard comment + `del` (`main.py:383-385`):

```python
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    # Threaded for later V4 work (writing metadata into pyproject.toml); not yet
    # consumed. The `del` documents intent and satisfies ruff ARG001.
    del author_name, author_email, description, package_license, repository_url
```

becomes just:

```python
    """Clone modernpackage files into `package_name` and run `just init` in it."""
```

Then insert the writer call after the clone `returncode` check (`main.py:399-403`)
and before the `try:` that runs `just init` (`main.py:405`):

```python
    if pipe.returncode != 0:
        raw = f'git clone failed with exit code {pipe.returncode}: {stderr_text}'
        friendly = humanize_git_clone_error(stderr_text)
        message = f'{friendly}\n\n{raw}' if friendly else raw
        raise RuntimeError(message)

    _write_package_metadata(
        new_package_path,
        author_name=author_name,
        author_email=author_email,
        description=description,
        package_license=package_license,
        repository_url=repository_url,
    )

    try:
        pipe = Popen(  # noqa: S603
            ['just', 'init', module_name],  # noqa: S607
```

#### 3. Unit tests

**File**: `tests/test_main.py`
**Action**: modify (add seed helper + tests; import `from modernpackage import main`)

```python
def _seed_pyproject(tmp_path: Path) -> Path:
    """Copy the real template pyproject.toml into tmp_path; return tmp_path."""
    source = Path(__file__).resolve().parent.parent / 'pyproject.toml'
    (tmp_path / 'pyproject.toml').write_text(source.read_text())
    return tmp_path


def test_write_package_metadata_replaces_all_fields(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    main._write_package_metadata(
        package_path,
        author_name='Jane Doe',
        author_email='jane@example.org',
        description='A real package.',
        package_license=None,
        repository_url='https://example.org/repo',
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'Jane Doe' in result
    assert 'jane@example.org' in result
    assert 'A real package.' in result
    assert 'https://example.org/repo' in result
    assert 'Name Surname' not in result
    assert 'email@example.com' not in result
    assert 'Package configuration example using bleeding edge toolset.' not in result
    assert 'https://github.com/albertas/modernpackage' not in result


def test_write_package_metadata_none_is_noop(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    original = (package_path / 'pyproject.toml').read_text()
    main._write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert (package_path / 'pyproject.toml').read_text() == original


def test_write_package_metadata_missing_file(tmp_path: Path) -> None:
    # No pyproject.toml seeded: must return without raising.
    main._write_package_metadata(
        tmp_path,
        author_name='Jane Doe',
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )


def test_write_package_metadata_escapes_quotes(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    main._write_package_metadata(
        package_path,
        author_name='Acme "Inc"',
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'Acme \\"Inc\\"' in result
    assert tomllib.loads(result)  # parses cleanly
```

(Add `import tomllib` to `tests/test_main.py` if not already imported.)

### Verification

#### Automated
- [x] `just test` passes (all unit tests green; 95% coverage gate met,
      `pyproject.toml:40`).
- [x] `just test -k write_package_metadata` passes (4 new Phase-1 tests).
- [x] `just test -k init_new_package` passes — the 3-`Popen`-call assertion
      (`tests/test_main.py:280`) is unchanged; the writer hits the missing-file
      branch (no real clone) and returns.
- [x] `just check-complexity` passes (`_write_package_metadata` ≤ 8).

#### Manual
- [x] `grep -n 'del author_name' modernpackage/main.py` → no output (the discard
      line is removed).
- [x] `grep -n '_write_package_metadata(' modernpackage/main.py` → 2 hits (the
      `def` and the call inside `init_new_package`).

#### Deviations from plan
- Tests use `_write_package_metadata(...)` directly (imported from `modernpackage.main`)
  instead of `main._write_package_metadata(...)`, because importing the module as `main`
  would conflict with the existing `main` function import. Semantically identical.
- Added `# noqa: PLR0913` (>5 args) and `# noqa: ARG001` (`package_license` unused in Phase 1)
  to `_write_package_metadata` to satisfy the ruff linter.

---

## Phase 2: License field + classifier removal

### Changes

#### 1. License helper

**File**: `modernpackage/main.py`
**Action**: modify (add `_apply_license` next to `_write_package_metadata`)

```python
def _apply_license(content: str, package_license: str) -> str:
    """Insert a PEP 639 license key and drop the hardcoded MIT trove classifier.

    Adds `license = "<value>"` to [project] after the stable `readme` key, and
    removes the `License :: OSI Approved :: MIT License` classifier line so the
    scaffold does not carry a contradictory hardcoded license (design Decision 5).
    """
    license_line = f'license = "{_toml_escape(package_license)}"'
    content = content.replace(
        'readme = "README.md"',
        f'readme = "README.md"\n{license_line}',
    )
    return content.replace(
        '    "License :: OSI Approved :: MIT License",\n',
        '',
    )
```

The classifier literal is `    "License :: OSI Approved :: MIT License",`
(4-space indent, trailing comma, `pyproject.toml:11`) plus its newline.

#### 2. Wire license into the writer

**File**: `modernpackage/main.py`
**Action**: modify (`_write_package_metadata`, replace the Phase-1 placeholder
comment `# package_license handled in Phase 2 ...`)

```python
    if package_license is not None:
        updated = _apply_license(updated, package_license)
```

#### 3. License unit tests

**File**: `tests/test_main.py`
**Action**: modify (add tests; reuse `_seed_pyproject`)

```python
def test_write_package_metadata_writes_license(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    main._write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license='Apache-2.0',
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'license = "Apache-2.0"' in result
    assert 'License :: OSI Approved :: MIT License' not in result
    assert 'Natural Language :: English' in result  # other classifiers intact
    assert tomllib.loads(result)


def test_write_package_metadata_none_license_keeps_classifier(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    main._write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'License :: OSI Approved :: MIT License' in result
    assert 'license = "' not in result
```

### Verification

#### Automated
- [x] `just test` passes.
- [x] `just test -k write_package_metadata` passes (Phase-1 + Phase-2 tests).
- [x] `just check-complexity` passes (`_write_package_metadata` still ≤ 8;
      license logic lives in `_apply_license`).

#### Manual
- [x] `python -c "import tomllib,pathlib; p=pathlib.Path('/tmp/lic.toml'); p.write_text(pathlib.Path('pyproject.toml').read_text().replace('readme = \"README.md\"','readme = \"README.md\"\nlicense = \"Apache-2.0\"').replace('    \"License :: OSI Approved :: MIT License\",\n','')); print('license' in tomllib.loads(p.read_text())['project'])"`
      → prints `True` (proves the transform yields valid TOML with a `license` key).

---

## Phase 3: e2e assertion of generated contents

### Changes

#### 1. Apply + assert metadata in the e2e flow

**File**: `tests/test_e2e.py`
**Action**: modify `test_scaffolded_package_passes_check` (`tests/test_e2e.py:52-83`)

Add the import:

```python
from modernpackage.main import normalize_module_name
from modernpackage import main
```

After the successful clone assertion (`test_e2e.py:63`) and before the `just init`
call (`test_e2e.py:65`), invoke the writer at the same hook point used in
`init_new_package`:

```python
    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e generated package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
```

After the existing `just check` assertion (`test_e2e.py:82-83`), assert the
on-disk generated metadata:

```python
    pyproject = (destination / 'pyproject.toml').read_text()
    assert 'Test Author' in pyproject
    assert 'test@example.org' in pyproject
    assert 'An e2e generated package.' in pyproject
    assert 'license = "Apache-2.0"' in pyproject
    assert 'License :: OSI Approved :: MIT License' not in pyproject
    assert 'Name Surname' not in pyproject
    assert 'email@example.com' not in pyproject
    assert 'Package configuration example using bleeding edge toolset.' not in pyproject
```

Note: `repository_url='https://example.org/repo'` contains no `modernpackage`
token, so `just init`'s sed pass leaves it intact (avoids the Open Risk while
still exercising the URL substitution). The existing `just check` exit-0
assertion is kept.

### Verification

#### Automated
- [ ] `just test-e2e` passes on a host with `git`/`just`/`uv` on PATH
      (`Justfile:16-17`; the test self-skips otherwise, `tests/test_e2e.py:54-56`).
      (Not yet run — requires network access and takes several minutes.)

#### Manual
- [ ] `just test-e2e -k scaffolded_package_passes_check` → exits 0; the run
      both asserts the generated `pyproject.toml` contains `Test Author`,
      `test@example.org`, `license = "Apache-2.0"` and that `just check` returns 0.
      (Not yet run — requires network access and takes several minutes.)

#### Confirmed passing (no e2e)
- `just check` (unit tests + lint + typecheck + complexity + audit + deadcode) → all green.
- `noqa: SLF001` added to `main._write_package_metadata(...)` call in `test_e2e.py`
  to satisfy ruff's private-member-access rule (consistent with unit test approach).

#### Deviations from plan
- `main._write_package_metadata(  # noqa: SLF001` — added the noqa suppressor
  because ruff SLF001 fires on private-member access. The unit tests avoided this by
  importing `_write_package_metadata` directly; the e2e test uses the `main` module
  object per the plan's instruction, so the inline suppressor is the right fix.

---

## Testing Checkpoints

- **After Phase 1**: `_toml_escape` and `_write_package_metadata` exist;
  author/email/description/URL substitutions work and are unit-tested; the writer
  is wired into `init_new_package` (no `del`); existing `Popen`-mocked tests still
  green (missing-file branch); `just check` passes (95% coverage on new branches
  via `tmp_path` tests).
- **After Phase 2**: `license = "<value>"` written and MIT classifier removed
  when supplied, both untouched when `None`; result parses as valid TOML; both
  license branches unit-tested.
- **After Phase 3**: real clone → write → `just init` produces correct on-disk
  metadata and the scaffold still passes `just check`.

### Risks carried from design.md
- `repository_url` containing the literal `modernpackage` would be rewritten by
  `just init`'s sed (Open Risk). Accepted; not handled this iteration (the e2e
  test deliberately uses a token-free URL).
- Placeholder literals are matched exactly — template drift silently no-ops
  (mitigated by the Phase 3 e2e content assertions).
