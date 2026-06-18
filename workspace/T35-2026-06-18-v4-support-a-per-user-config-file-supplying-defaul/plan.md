# Implementation Plan

## Overview

Add a per-user TOML config file (`$XDG_CONFIG_HOME/modernpackage/config.toml`,
fallback `~/.config/modernpackage/config.toml`) as the **weakest** metadata
default source, consulted only after flag, env, and git config all yield `None`.
New precedence: `flag > env > git config > config file > None` for
author_name/author_email, and `flag > env > config file > None` for
description/license/repository_url.

All line references below are to `modernpackage/main.py` as it stands today
(read before editing — earlier phases shift line numbers).

---

## Phase 1: Config-file reader + free-string fields

Add `tomllib` import, three module constants, path resolution + single-load TOML
parsing + per-field coercion helpers, and wire the three no-validator fields
(`author_name`, `description`, `license`) into the fallback chain. Malformed /
unreadable files degrade **silently** to `{}` in this phase (the stderr notice
is added in Phase 3).

### Changes

#### 1. Imports
**File**: `modernpackage/main.py`
**Action**: modify

Add `import tomllib` to the stdlib import block (keep alphabetical: after
`import sys`, line 5). Add `Mapping` to the existing `TYPE_CHECKING` block
(line 11-12) — it is used only in an annotation, and Python 3.14 lazily
evaluates annotations (PEP 649), so a `TYPE_CHECKING`-only import is correct
here, exactly as `Callable` already is:

```python
import sys
import tomllib
...
if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
```

#### 2. Module constants
**File**: `modernpackage/main.py`
**Action**: modify — append after the git-config key constants (after line 96)

```python
# Per-user TOML config file consulted as the weakest metadata default for all
# five fields when the matching flag, env var, and git config are all absent
# (precedence: flag > env > git config > config file > None).
_CONFIG_DIR_NAME: str = 'modernpackage'
_CONFIG_FILE_NAME: str = 'config.toml'
_XDG_CONFIG_HOME_ENV: str = 'XDG_CONFIG_HOME'
```

#### 3. Source-reader helpers
**File**: `modernpackage/main.py`
**Action**: modify — insert the three functions after `_git_config_default`
(after line 189), before `_validated_or_error`

```python
def _user_config_path() -> Path | None:
    """Return the per-user config file path, or None if home is unresolvable.

    Resolves `$XDG_CONFIG_HOME` (a set-but-empty value coalesces to the
    `~/.config` fallback, matching the empty-as-unset convention of the env
    reader), else `~/.config`. Returns None when the home directory cannot be
    determined (design Open Risk: `Path.home()` raises in odd environments).
    """
    xdg_config_home = os.environ.get(_XDG_CONFIG_HOME_ENV) or None
    if xdg_config_home is not None:
        base = Path(xdg_config_home)
    else:
        try:
            base = Path.home() / '.config'
        except RuntimeError:
            return None
    return base / _CONFIG_DIR_NAME / _CONFIG_FILE_NAME


def _load_config_file() -> dict[str, object]:
    """Parse the per-user TOML config file into a mapping, or return {}.

    A missing file (no resolvable path or FileNotFoundError) returns {} silently
    — an absent config is expected, not an error. Malformed or unreadable files
    (TOMLDecodeError / OSError) also return {} silently in this phase; a stderr
    notice is added in Phase 3 (design Decision 6).
    """
    path = _user_config_path()
    if path is None:
        return {}
    try:
        with path.open('rb') as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _config_file_default(config: Mapping[str, object], key: str) -> str | None:
    """Return config[key] only if it is a non-empty str; else None.

    Empty strings and non-string TOML values (int/bool/array/table) coalesce to
    None, matching the empty-as-unset convention of the env/git readers and
    protecting the regex validators from non-str input (design Decision 5).
    """
    value = config.get(key)
    if isinstance(value, str) and value:
        return value
    return None
```

Note: `FileNotFoundError` is a subclass of `OSError`, so it is caught by the
first `except`; the order keeps a missing file silent while letting Phase 3
distinguish the malformed/unreadable branch.

#### 4. Wire free-string fields into `parse_args()`
**File**: `modernpackage/main.py`
**Action**: modify — insert **after** the git-config blocks (after line 278)
and **before** the first `_validated_or_error` call (line 279)

```python
    config_file = _load_config_file()
    if arguments.author_name is None:
        arguments.author_name = _config_file_default(config_file, 'author_name')
    if arguments.description is None:
        arguments.description = _config_file_default(config_file, 'description')
    if arguments.license is None:
        arguments.license = _config_file_default(config_file, 'license')
```

The TOML keys are the argparse dests verbatim (`--license` → dest `license`,
`--author-name` → dest `author_name`). `author_email` / `repository_url` are
wired in Phase 2; the single `config_file = _load_config_file()` load added here
serves them too.

#### 5. Tests
**File**: `tests/test_main.py`
**Action**: modify — add imports and a seed helper near the top (after the
existing import block, line 20), then the tests below

Extend the `from modernpackage.main import (...)` block with the new symbols:

```python
from modernpackage.main import (
    ...
    _config_file_default,
    _load_config_file,
    _user_config_path,
    ...
)
```

Seed helper (prefix `_`, per testing conventions):

```python
def _write_config(tmp_path: Path, body: str) -> None:
    config_dir = tmp_path / 'modernpackage'
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / 'config.toml').write_text(body)
```

A `parse_args()` helper that isolates **every** higher source so the file is
reached (delete all five env vars, point XDG at `tmp_path`, force git config to
`None`):

```python
def _parse_args_with_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> Namespace:
    for env in (
        'MODERNPACKAGE_AUTHOR_NAME', 'MODERNPACKAGE_AUTHOR_EMAIL',
        'MODERNPACKAGE_DESCRIPTION', 'MODERNPACKAGE_LICENSE',
        'MODERNPACKAGE_REPOSITORY_URL',
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with (
        patch('sys.argv', argv),
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        return parse_args()
```

(`Namespace` import from `argparse` may be added to the test imports for the
annotation, or annotate the return as a string — match the file's existing
style; the file currently imports only `ArgumentTypeError` and `Path`.)

Tests:

```python
def test_user_config_path_uses_xdg_config_home(monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', '/tmp/xdg')
    assert _user_config_path() == Path('/tmp/xdg/modernpackage/config.toml')

def test_user_config_path_falls_back_to_home_config(monkeypatch):
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    with patch('modernpackage.main.Path.home', return_value=Path('/home/x')):
        assert _user_config_path() == Path('/home/x/.config/modernpackage/config.toml')

def test_user_config_path_empty_xdg_falls_back_to_home(monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', '')
    with patch('modernpackage.main.Path.home', return_value=Path('/home/x')):
        assert _user_config_path() == Path('/home/x/.config/modernpackage/config.toml')

def test_config_file_default_returns_non_empty_str():
    assert _config_file_default({'license': 'MIT'}, 'license') == 'MIT'

def test_config_file_default_empty_string_is_none():
    assert _config_file_default({'license': ''}, 'license') is None

def test_config_file_default_non_string_is_none():
    assert _config_file_default({'license': 42}, 'license') is None

def test_config_file_default_missing_key_is_none():
    assert _config_file_default({}, 'license') is None

def test_load_config_file_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))  # no file written
    assert _load_config_file() == {}

def test_parse_args_config_file_fills_free_string_fields(tmp_path, monkeypatch):
    _write_config(tmp_path,
        'author_name = "Ada"\ndescription = "desc"\nlicense = "MIT"\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.author_name == 'Ada'
    assert arguments.description == 'desc'
    assert arguments.license == 'MIT'

def test_parse_args_env_beats_config_file(tmp_path, monkeypatch):
    _write_config(tmp_path, 'license = "MIT"\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.setenv('MODERNPACKAGE_LICENSE', 'Apache-2.0')
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        arguments = parse_args()
    assert arguments.license == 'Apache-2.0'

def test_parse_args_git_config_beats_config_file(tmp_path, monkeypatch):
    _write_config(tmp_path, 'author_name = "File Name"\n')
    for env in ('MODERNPACKAGE_AUTHOR_NAME', 'MODERNPACKAGE_AUTHOR_EMAIL'):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: (
            'Git Name' if key == _GIT_CONFIG_USER_NAME_KEY else None
        )
        arguments = parse_args()
    assert arguments.author_name == 'Git Name'

def test_parse_args_empty_config_value_stays_none(tmp_path, monkeypatch):
    _write_config(tmp_path, 'license = ""\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.license is None
```

### Verification
#### Automated
- [x] `just test` passes (all new Phase 1 tests green; existing suite unchanged)
- [x] `just check-typecheck` passes (mypy accepts the `Mapping` annotation and
      `dict[str, object]` return)
- [x] `just check-lint` passes (no unused-import / style violations)

#### Manual
- [x] File fills free-string fields when higher sources absent:
```bash
mkdir -p /tmp/cfg/modernpackage
printf 'description = "from file"\nlicense = "MIT"\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION -u MODERNPACKAGE_LICENSE XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; n=parse_args(); print(n.description, n.license)"
```
expected stdout: `from file MIT`
- [x] Empty / non-string values are treated as unset:
```bash
printf 'description = ""\nlicense = 42\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION -u MODERNPACKAGE_LICENSE XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; n=parse_args(); print(n.description, n.license)"
```
expected stdout: `None None`

---

## Phase 2: Validated fields (email + repository URL)

Wire `author_email` and `repository_url` file fallbacks. Because the new guards
sit before the `_validated_or_error` calls (line 279-284), file-sourced values
flow through the existing validators unchanged — invalid values exit 2.

### Changes

#### 1. Wire validated fields into `parse_args()`
**File**: `modernpackage/main.py`
**Action**: modify — append to the config-file guard block from Phase 1
(immediately after the `license` guard, still **before** the first
`_validated_or_error` call)

```python
    if arguments.author_email is None:
        arguments.author_email = _config_file_default(config_file, 'author_email')
    if arguments.repository_url is None:
        arguments.repository_url = _config_file_default(config_file, 'repository_url')
```

No change to the validators or `_validated_or_error`.

#### 2. Tests
**File**: `tests/test_main.py`
**Action**: modify — add tests (reuse the `_write_config` /
`_parse_args_with_config` helpers from Phase 1)

```python
def test_parse_args_config_file_fills_email_and_url(tmp_path, monkeypatch):
    _write_config(tmp_path,
        'author_email = "ada@example.com"\n'
        'repository_url = "https://example.com/repo"\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.author_email == 'ada@example.com'
    assert arguments.repository_url == 'https://example.com/repo'

def test_parse_args_flag_beats_config_file_email(tmp_path, monkeypatch):
    _write_config(tmp_path, 'author_email = "file@example.com"\n')
    arguments = _parse_args_with_config(
        tmp_path, monkeypatch,
        ['modernpackage', 'pkg', '--author-email', 'flag@example.com'])
    assert arguments.author_email == 'flag@example.com'

def test_parse_args_invalid_config_email_exits_two(tmp_path, monkeypatch):
    _write_config(tmp_path, 'author_email = "nope"\n')
    with pytest.raises(SystemExit) as exit_info:
        _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert exit_info.value.code == 2  # noqa: PLR2004

def test_parse_args_invalid_config_url_exits_two(tmp_path, monkeypatch):
    _write_config(tmp_path, 'repository_url = "ftp://nope"\n')
    with pytest.raises(SystemExit) as exit_info:
        _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert exit_info.value.code == 2  # noqa: PLR2004
```

### Verification
#### Automated
- [x] `just test` passes (Phase 2 tests green)

#### Manual
- [x] File fills email/URL when higher sources absent (git config neutralized so
      it can't pre-empt the file):
```bash
printf 'author_email = "ada@example.com"\nrepository_url = "https://example.com/r"\n' \
  > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_AUTHOR_EMAIL -u MODERNPACKAGE_REPOSITORY_URL \
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; n=parse_args(); print(n.author_email, n.repository_url)"
```
expected stdout: `ada@example.com https://example.com/r`
- [x] Invalid file email exits 2:
```bash
printf 'author_email = "nope"\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_AUTHOR_EMAIL \
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; parse_args()"; echo "exit=$?"
```
expected: stderr contains `Invalid author email`; final line `exit=2`

---

## Phase 3: Malformed-file notice (graceful degradation)

Upgrade `_load_config_file()` from silent-on-error to a one-line `sys.stderr`
notice on `TOMLDecodeError` / `OSError`, then continue with no defaults (design
Decision 6). A missing file stays silent.

### Changes

#### 1. Refine `_load_config_file()`
**File**: `modernpackage/main.py`
**Action**: modify — replace the silent `except (tomllib.TOMLDecodeError, OSError)`
branch (added in Phase 1) with a notice-emitting one. Update the docstring's
"silently in this phase" sentence to state the notice behavior.

```python
    try:
        with path.open('rb') as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as error:
        print(  # noqa: T201
            f'Ignoring unreadable config file {path}: {error}',
            file=sys.stderr,
        )
        return {}
```

Consistent with the existing `print(..., file=sys.stderr)  # noqa: T201` usage
(lines 353, 356, 379). The missing-file branch stays a silent `return {}`.

#### 2. Tests
**File**: `tests/test_main.py`
**Action**: modify — add tests using `capsys` to capture the notice

```python
def test_load_config_file_malformed_prints_notice(tmp_path, monkeypatch, capsys):
    _write_config(tmp_path, 'this is = not valid toml =\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert _load_config_file() == {}
    captured = capsys.readouterr()
    assert 'config file' in captured.err
    assert 'config.toml' in captured.err

def test_load_config_file_missing_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))  # no file
    assert _load_config_file() == {}
    assert capsys.readouterr().err == ''

def test_parse_args_malformed_config_continues_with_none(tmp_path, monkeypatch, capsys):
    _write_config(tmp_path, 'this is = not valid toml =\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.description is None
    assert arguments.license is None
    assert 'config.toml' in capsys.readouterr().err
```

### Verification
#### Automated
- [x] `just test` passes (Phase 3 tests green)

#### Manual
- [x] Malformed TOML prints a notice and scaffolding continues with `None`:
```bash
printf 'this is = not valid toml =\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; print(parse_args().description)" 2>/tmp/err
cat /tmp/err
```
expected: stdout prints `None`; `/tmp/err` contains `config file` and `config.toml`
- [x] Absent file emits no notice:
```bash
rm -f /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION XDG_CONFIG_HOME=/tmp/cfg \
  uv run python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; print(parse_args().description)" 2>/tmp/err
test ! -s /tmp/err && echo "no-notice-OK"
```
expected: stdout `None`; final line `no-notice-OK` (empty stderr)

---

## Phase 4: Documentation

Extend the per-flag precedence chains and the "Precedence" summary to include the
config file as the weakest source.

### Changes

#### 1. README per-flag bullets + precedence summary
**File**: `README.md`
**Action**: modify — lines 83-98

- `--author-name` (line 83): append `→ config file` before `→ None`:
  `$MODERNPACKAGE_AUTHOR_NAME → git config user.name → config file → None`.
- `--author-email` (line 84): `$MODERNPACKAGE_AUTHOR_EMAIL → git config user.email → config file → None`.
- `--description` (line 85): `Defaults in order: $MODERNPACKAGE_DESCRIPTION → config file → None.`
- `--license` (line 86): `Defaults in order: $MODERNPACKAGE_LICENSE → config file → None.`
- `--repository-url` (line 87): `Defaults in order: $MODERNPACKAGE_REPOSITORY_URL → config file → None.`
- Precedence summary (lines 91-94):
  - `author_name` / `author_email`: **flag > env > git config > config file > None**
  - other fields: **flag > env > config file > None**
- Add a paragraph after line 98 documenting: the config-file location
  (`$XDG_CONFIG_HOME/modernpackage/config.toml`, fallback
  `~/.config/modernpackage/config.toml`), the flat TOML keys (`author_name`,
  `author_email`, `description`, `license`, `repository_url`),
  empty/non-string-as-unset, and that a malformed/unreadable file prints a
  notice to stderr and continues with no defaults. Note `--help` is unchanged
  (matches the git-config precedent).

#### 2. docs/overview.md
**File**: `docs/overview.md`
**Action**: modify — line 55 ("Optional metadata flags" bullet)

Append a sentence: file-sourced values rank below git config as the weakest
source (`flag > env > git config > config file > None` for name/email,
`flag > env > config file > None` for the rest), read from a flat-key TOML file
at `$XDG_CONFIG_HOME/modernpackage/config.toml` (fallback `~/.config/...`);
malformed files print a notice and continue.

### Verification
#### Automated
- [x] `just check` passes (full gate: format, lint, complexity, typecheck, test, audit)

#### Manual
- [x] Both docs mention the new source:
```bash
grep -c 'config file' README.md docs/overview.md
```
expected: each path reports a count `> 0`
- [x] Full precedence string present in README:
```bash
grep -q 'flag > env > git config > config file > None' README.md && echo "precedence-OK"
```
expected: `precedence-OK`

---

## Assumptions & Resolutions

- **`Mapping` import placement**: under `TYPE_CHECKING` (PEP 649 lazy
  annotations on Python ≥ 3.14), mirroring the existing `Callable` import. No
  runtime import needed.
- **Notice text**: `Ignoring unreadable config file {path}: {error}` — names the
  resolved path (satisfies the "notice names the config path" requirement) and
  the underlying error. Single line, stderr, `# noqa: T201`.
- **`Namespace` annotation in test helper**: import `Namespace` from `argparse`
  in the test file if annotating `_parse_args_with_config`'s return; otherwise
  drop the annotation. Either matches the existing test-style minimalism.
- **Manual commands use `uv run python`** because the project runs under `uv`
  (per Justfile); plain `python` may not have the package importable.
- **Git neutralization in Phase 2 manual checks**: `GIT_CONFIG_GLOBAL=/dev/null
  GIT_CONFIG_SYSTEM=/dev/null` prevents a developer's real `git config
  user.email` (which outranks the file) from masking the file-sourced value.
- **No schema migration / codegen**: this feature touches no versioned schema or
  generated files, so those plan sections are not applicable.

## Deviations from `structure.md`

- Added a `test_user_config_path_empty_xdg_falls_back_to_home` case and a
  shared `_parse_args_with_config` helper not spelled out in the structure, to
  exercise the empty-`XDG_CONFIG_HOME` Open Risk and keep the new tests DRY.
- Phase 2/3 manual commands add `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM=/dev/null`
  so the email/URL checks are deterministic regardless of the developer's git
  config (the bare structure command could be masked by a real `user.email`).
