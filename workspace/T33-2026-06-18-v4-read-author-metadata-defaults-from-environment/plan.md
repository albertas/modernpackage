# Implementation Plan

## Overview

When a metadata flag is omitted, resolve its value from a dedicated
`MODERNPACKAGE_*` environment variable (precedence: flag > env > `None`),
validating env-sourced email and repository URL with the existing validators and
surfacing failures as clean CLI errors. All changes live in
`modernpackage/main.py` and `tests/test_main.py`; `main`, `init_new_package`,
the validators, and the e2e test are untouched.

### Resolved assumptions / deviations from `structure.md`

- **Deviation (complexity):** `structure.md` says the resolution lives in a
  "post-parse block in `parse_args`". Inlining all five `None`-checks plus two
  `try/except` validation blocks would raise `parse_args`' McCabe complexity to
  ~10, over the project limit of 8 (`pyproject.toml:79`, ruff `C901`). To stay
  under the limit, the email/URL validation-with-`parser.error` is extracted into
  a private helper `_validated_or_error`. The env-default substitution itself
  stays inline in `parse_args` as the structure describes. Net `parse_args`
  complexity ≈ 6.
- **Helper count:** two private helpers total — `_environment_default`
  (Phase 1) and `_validated_or_error` (Phase 2). The second is the
  complexity-driven addition above.
- **Help probe:** there is no `modernpackage/__main__.py`, so `python -m
  modernpackage` will not run. The package exposes console scripts
  `modernpackage` and `mp` (`pyproject.toml:23-25`). Phase 3 manual probe uses
  `uv run modernpackage --help`.
- **`Callable` import:** `_validated_or_error` takes the validator as an
  argument, requiring `from collections.abc import Callable` (added in Phase 2).
- **Fixture type annotations:** mypy strict + ruff `ALL` require annotated
  params. New tests annotate `monkeypatch: pytest.MonkeyPatch` and
  `capsys: pytest.CaptureFixture[str]`.

---

## Phase 1: Env fallback for unvalidated fields (name, description, license)

Introduces the env-default machinery end to end and applies it to the three
fields with no validator. Proves precedence (flag > env > None) and
empty-string-as-unset without validation noise.

### Changes

#### 1. Import `os`
**File**: `modernpackage/main.py`
**Action**: modify (imports block, `main.py:3-7`)

Add `import os` in alphabetical order among the stdlib imports:

```python
import os
import re
import sys
```

#### 2. Env-var name constants (Phase 1 subset)
**File**: `modernpackage/main.py`
**Action**: modify — add after `_REPOSITORY_URL_RE` (`main.py:77`), before
`_explain_invalid_package_name` (`main.py:80`)

```python
# Environment variables consulted as metadata defaults when the matching flag
# is omitted (precedence: flag > env > None).
_AUTHOR_NAME_ENV: str = 'MODERNPACKAGE_AUTHOR_NAME'
_DESCRIPTION_ENV: str = 'MODERNPACKAGE_DESCRIPTION'
_LICENSE_ENV: str = 'MODERNPACKAGE_LICENSE'
```

(The two validated-field constants are added in Phase 2 to keep the slice tight;
final ordering is cosmetic.)

#### 3. `_environment_default` helper
**File**: `modernpackage/main.py`
**Action**: modify — add immediately above `parse_args` (`main.py:145`)

```python
def _environment_default(variable_name: str) -> str | None:
    """Return the env var value, treating a set-but-empty value as unset."""
    return os.environ.get(variable_name) or None
```

`value or None` collapses both missing (`None`) and empty-string env vars to
`None` (design Decision 6).

#### 4. Post-parse substitution in `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify — replace the final line `return parser.parse_args()`
(`main.py:188`)

```python
    arguments = parser.parse_args()
    if arguments.author_name is None:
        arguments.author_name = _environment_default(_AUTHOR_NAME_ENV)
    if arguments.description is None:
        arguments.description = _environment_default(_DESCRIPTION_ENV)
    if arguments.license is None:
        arguments.license = _environment_default(_LICENSE_ENV)
    return arguments
```

A `None` post-parse value means the flag was absent, so env may fill it; a
present flag is non-`None` and is left untouched (design Decision 3). The
namespace attribute for `--license` is `license` (research Q1).

#### 5. Tests — Phase 1
**File**: `tests/test_main.py`
**Action**: modify

(a) Add new tests (place near the existing `parse_args` tests, after
`test_parse_args_license`, `test_main.py:117-120`):

```python
def test_parse_args_description_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_DESCRIPTION', 'from-env')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.description == 'from-env'


def test_parse_args_flag_overrides_env_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_DESCRIPTION', 'from-env')
    with patch('sys.argv', ['modernpackage', 'mypackage', '--description', 'cli']):
        result = parse_args()
    assert result.description == 'cli'


def test_parse_args_empty_env_license_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_LICENSE', '')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.license is None
```

(b) Modify `test_parse_args_metadata_defaults_none` (`test_main.py:157-164`) to
isolate the environment so a developer's real `MODERNPACKAGE_*` vars cannot leak
in (design Open Risk):

```python
def test_parse_args_metadata_defaults_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable_name in (
        'MODERNPACKAGE_AUTHOR_NAME',
        'MODERNPACKAGE_AUTHOR_EMAIL',
        'MODERNPACKAGE_DESCRIPTION',
        'MODERNPACKAGE_LICENSE',
        'MODERNPACKAGE_REPOSITORY_URL',
    ):
        monkeypatch.delenv(variable_name, raising=False)
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.author_name is None
    assert result.author_email is None
    assert result.description is None
    assert result.license is None
    assert result.repository_url is None
```

### Verification
#### Automated
- [x] `just test tests/test_main.py` passes (fast inner loop)
- [x] `just check` passes (format-check, lint, complexity `C901`, mypy strict,
      full test suite, audit)
- [x] Complexity gate clean: `uv run ruff check --select C901 modernpackage` →
      no `parse_args` violation

#### Manual
- [x] Env fallback works:
      `MODERNPACKAGE_DESCRIPTION=hi uv run python -c "from unittest.mock import patch; from modernpackage.main import parse_args;
      __import__('sys').argv=['m','mypackage'];
      print(parse_args().description)"` → prints `hi`
- [x] `import os` is actually used (otherwise ruff `F401`): covered by `just
      check`; spot check `grep -n "os.environ" modernpackage/main.py` returns a hit

---

## Phase 2: Validated env fallback (author-email, repository-url)

Extends the Phase 1 mechanism to the two validated fields and routes invalid env
values through `parser.error` so they exit cleanly (code 2) instead of raising a
raw `ArgumentTypeError` traceback.

### Changes

#### 1. `Callable` import
**File**: `modernpackage/main.py`
**Action**: modify — add to imports (`main.py:3-9` block), before stdlib `re`:

```python
from collections.abc import Callable
```

(`from`-imports are grouped after plain `import` statements per the existing
order; ruff `I` will fix exact placement — run `just fix-lint` if it reorders.)

#### 2. Env-var name constants (validated subset)
**File**: `modernpackage/main.py`
**Action**: modify — extend the constant block from Phase 1

```python
_AUTHOR_EMAIL_ENV: str = 'MODERNPACKAGE_AUTHOR_EMAIL'
_REPOSITORY_URL_ENV: str = 'MODERNPACKAGE_REPOSITORY_URL'
```

#### 3. `_validated_or_error` helper
**File**: `modernpackage/main.py`
**Action**: modify — add immediately below `_environment_default`

```python
def _validated_or_error(
    parser: ArgumentParser,
    value: str | None,
    validator: Callable[[str], str],
) -> str | None:
    """Validate a non-None value, converting ArgumentTypeError to parser.error."""
    if value is None:
        return None
    try:
        return validator(value)
    except ArgumentTypeError as error:
        parser.error(str(error))
```

`ArgumentParser.error` is typed `NoReturn` (it prints to stderr and raises
`SystemExit(2)`), so no explicit return is needed after it and mypy/ruff
(`RET503`) stay clean. Re-validating a flag-supplied value is idempotent and
harmless (design Decision 4).

#### 4. Extend the post-parse pass in `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify — insert the two env substitutions before `return arguments`,
then validate both fields

```python
    if arguments.author_email is None:
        arguments.author_email = _environment_default(_AUTHOR_EMAIL_ENV)
    if arguments.repository_url is None:
        arguments.repository_url = _environment_default(_REPOSITORY_URL_ENV)
    arguments.author_email = _validated_or_error(
        parser, arguments.author_email, validate_author_email
    )
    arguments.repository_url = _validated_or_error(
        parser, arguments.repository_url, validate_repository_url
    )
    return arguments
```

Final `parse_args` body (full post-parse block) for reference:

```python
    arguments = parser.parse_args()
    if arguments.author_name is None:
        arguments.author_name = _environment_default(_AUTHOR_NAME_ENV)
    if arguments.description is None:
        arguments.description = _environment_default(_DESCRIPTION_ENV)
    if arguments.license is None:
        arguments.license = _environment_default(_LICENSE_ENV)
    if arguments.author_email is None:
        arguments.author_email = _environment_default(_AUTHOR_EMAIL_ENV)
    if arguments.repository_url is None:
        arguments.repository_url = _environment_default(_REPOSITORY_URL_ENV)
    arguments.author_email = _validated_or_error(
        parser, arguments.author_email, validate_author_email
    )
    arguments.repository_url = _validated_or_error(
        parser, arguments.repository_url, validate_repository_url
    )
    return arguments
```

McCabe count: 5 `if` + 1 base = 6 ≤ 8. Validation `try/except` complexity lives
in the helper (≈3).

#### 5. Tests — Phase 2
**File**: `tests/test_main.py`
**Action**: modify — add after the Phase 1 tests / existing
`test_parse_args_repository_url` (`test_main.py:148-154`)

```python
def test_parse_args_author_email_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'a@b.co')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.author_email == 'a@b.co'


def test_parse_args_flag_overrides_env_author_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'env@b.co')
    with patch(
        'sys.argv',
        ['modernpackage', 'mypackage', '--author-email', 'cli@b.co'],
    ):
        result = parse_args()
    assert result.author_email == 'cli@b.co'


def test_parse_args_repository_url_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_REPOSITORY_URL', 'https://x.com/r')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.repository_url == 'https://x.com/r'


def test_parse_args_invalid_env_author_email_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'nope')
    with (
        patch('sys.argv', ['modernpackage', 'mypackage']),
        pytest.raises(SystemExit) as excinfo,
    ):
        parse_args()
    assert excinfo.value.code == 2  # noqa: PLR2004
    assert 'Invalid author email' in capsys.readouterr().err


def test_parse_args_invalid_env_repository_url_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_REPOSITORY_URL', 'not-a-url')
    with (
        patch('sys.argv', ['modernpackage', 'mypackage']),
        pytest.raises(SystemExit) as excinfo,
    ):
        parse_args()
    assert excinfo.value.code == 2  # noqa: PLR2004
    assert 'Invalid repository URL' in capsys.readouterr().err
```

`# noqa: PLR2004` on the literal `2` matches the existing convention for magic
values in this suite (`test_main.py:172`).

### Verification
#### Automated
- [x] `just test tests/test_main.py` passes (all new + existing tests)
- [x] `just check` passes (including complexity `C901` on `parse_args`)
- [x] `main` / `init_new_package` tests unchanged and green:
      `uv run pytest tests/test_main.py -k "main or init_new_package"`

#### Manual
- [x] Valid env URL flows through:
      `MODERNPACKAGE_REPOSITORY_URL=https://x.com/r uv run python -c "from unittest.mock import patch; from modernpackage.main import parse_args;
      __import__('sys').argv=['m','mypackage'];
      print(parse_args().repository_url)"` → prints `https://x.com/r`
- [x] Invalid env email exits 2 with CLI-style stderr (no traceback):
      `MODERNPACKAGE_AUTHOR_EMAIL=nope uv run modernpackage mypackage;
      echo "exit=$?"` → stderr contains `Invalid author email`, prints
      `exit=2`, and output contains no `Traceback`

---

## Phase 3: Help-text discoverability

Append a short note to each of the five options' `help=` strings naming the
fallback env var, so `--help` documents the behaviour. Pure interface polish; no
logic change.

### Changes

#### 1. Append env-var notes to help strings
**File**: `modernpackage/main.py`
**Action**: modify — the five `add_argument` calls (`main.py:161-187`)

Each note pushes the line past the 88-char limit, so use implicit string
concatenation (single quotes, matching style):

```python
    parser.add_argument(
        '--author-name',
        help=(
            'Author name to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_NAME.'
        ),
        default=None,
    )
    parser.add_argument(
        '--description',
        help=(
            'Short description of the new package.'
            ' Defaults to $MODERNPACKAGE_DESCRIPTION.'
        ),
        default=None,
    )
    parser.add_argument(
        '--author-email',
        help=(
            'Author email to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_EMAIL.'
        ),
        type=validate_author_email,
        default=None,
    )
    parser.add_argument(
        '--license',
        help=(
            'License identifier for the new package.'
            ' Defaults to $MODERNPACKAGE_LICENSE.'
        ),
        default=None,
    )
    parser.add_argument(
        '--repository-url',
        help=(
            'Repository URL to record in the new package.'
            ' Defaults to $MODERNPACKAGE_REPOSITORY_URL.'
        ),
        type=validate_repository_url,
        default=None,
    )
```

#### 2. Help-text assertion test (optional but cheap)
**File**: `tests/test_main.py`
**Action**: modify — add one test

```python
def test_parse_args_help_advertises_env_vars(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch('sys.argv', ['modernpackage', '--help']), pytest.raises(SystemExit):
        parse_args()
    help_text = capsys.readouterr().out
    assert 'MODERNPACKAGE_AUTHOR_NAME' in help_text
    assert 'MODERNPACKAGE_REPOSITORY_URL' in help_text
```

`--help` triggers `SystemExit(0)`; the help body is written to stdout.

### Verification
#### Automated
- [x] `just check` passes (format, lint, complexity, typecheck, full suite, audit)

#### Manual
- [x] `uv run modernpackage --help | grep MODERNPACKAGE_` exits 0 and lists all
      five vars, including `MODERNPACKAGE_AUTHOR_NAME` and
      `MODERNPACKAGE_REPOSITORY_URL`

---

## Testing Checkpoints

- **After Phase 1**: `import os` used; `_environment_default` exists; env
  fallback works for name/description/license; flag beats env; empty string
  treated as unset; `test_parse_args_metadata_defaults_none` still passes with
  env isolated. `just check && just test` green.
- **After Phase 2**: env fallback works for all five fields; invalid env email or
  URL exits with code 2 and a CLI-style stderr message (no traceback); valid env
  values pass through; flag still authoritative; `main` / `init_new_package` and
  the e2e test remain unmodified. `parse_args` complexity ≤ 8.
- **After Phase 3**: `--help` advertises every `MODERNPACKAGE_*` var; full suite
  and lint/type/complexity gates pass.

**Resumption note**: all production changes live in `modernpackage/main.py`
(`import os` + `from collections.abc import Callable`; five `MODERNPACKAGE_*`
constants; `_environment_default` + `_validated_or_error` helpers; post-parse
block in `parse_args`; help-string notes). All test changes live in
`tests/test_main.py` (new `monkeypatch`/`capsys` tests + the env-isolated
defaults-none test). Nothing outside these two files should change.
