# Implementation Plan

## Overview

Add five optional long-only metadata flags (`--author-name`, `--author-email`,
`--description`, `--license`, `--repository-url`) to the CLI and thread their
parsed values through `parse_args → main → init_new_package` as keyword
arguments defaulting to `None`. Values reach `init_new_package`'s signature but
are **not** written to `pyproject.toml` (deferred V4 work). Email and URL get
parse-time `type=` validators; the other three are free strings.

All work is in `modernpackage/main.py` and `tests/test_main.py`. The authoritative
per-phase gate is `just check` (format-check + lint + complexity + typecheck +
test + audit; `Justfile:52`). Lint is `select = ["ALL"]` (`pyproject.toml:67`),
line-length 88 (`pyproject.toml:57`), mccabe ≤ 8 (`pyproject.toml:79`).

### Two cross-cutting constraints honored throughout

- **`A002` builtin-argument-shadowing**: a function param named `license` shadows
  the `license` builtin and `select=["ALL"]` flags it. The `init_new_package`
  param is named `package_license`; `main` forwards
  `package_license=parsed_args.license` (the argparse Namespace attribute stays
  `.license`, which is fine — A002 targets function params, not attribute access).
- **`ARG001` unused-argument**: the five new params are accepted but unconsumed.
  Acknowledge them with a single `del …` statement at the top of the function body
  (referencing a name in a `del` counts as a use, satisfying `ARG001`). **Fallback**:
  if `just check` still reports `ARG001` after adding `del`, replace it with a
  scoped `# noqa: ARG001` on each parameter line. Confirm via `just check`.

---

## Phase 1: Free-string flags + threading foundation

Adds `--author-name`, `--description`, `--license` (no validation) and
establishes the full vertical wiring: parse → forward → accept. After this phase
users can pass these three flags and they land on the `init_new_package`
signature.

### Changes

#### 1. New free-string arguments in `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify

Add three `add_argument` calls after the `package_name` positional (`main.py:132-137`,
i.e. before `return parser.parse_args()` at `main.py:138`). Mirror the existing
style: long `--kebab-case` option, short imperative help ending with a period,
explicit `default=None`.

```python
parser.add_argument(
    '--author-name',
    help='Author name to record in the new package.',
    default=None,
)
parser.add_argument(
    '--description',
    help='Short description of the new package.',
    default=None,
)
parser.add_argument(
    '--license',
    help='License identifier for the new package.',
    default=None,
)
```

`--license` maps to Namespace attribute `.license` (no `dest` override needed).

#### 2. Additive keyword-only params on `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify

Change the signature (`main.py:141`) to add a keyword-only block, and add a `del`
acknowledgement as the first statement of the body (after the docstring,
`main.py:142`, before `module_name = …` at `main.py:143`):

```python
def init_new_package(
    package_name: str,
    *,
    author_name: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    # Threaded for later V4 work (writing metadata into pyproject.toml); not yet
    # consumed. The `del` documents intent and satisfies ruff ARG001.
    del author_name, description, package_license

    module_name = normalize_module_name(package_name)
    ...  # rest unchanged
```

#### 3. Forward the new values in `main`
**File**: `modernpackage/main.py`
**Action**: modify

Extend the call at `main.py:211`:

```python
return init_new_package(
    package_name=parsed_args.package_name,
    author_name=parsed_args.author_name,
    description=parsed_args.description,
    package_license=parsed_args.license,
)
```

#### 4. Tests
**File**: `tests/test_main.py`
**Action**: modify

Add new `parse_args` tests (alongside `test_parse_args_package_name`,
`test_main.py:97-100`):

```python
def test_parse_args_author_name() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--author-name', 'Ada']):
        result = parse_args()
    assert result.author_name == 'Ada'


def test_parse_args_description() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--description', 'A tool']):
        result = parse_args()
    assert result.description == 'A tool'


def test_parse_args_license() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--license', 'MIT']):
        result = parse_args()
    assert result.license == 'MIT'


def test_parse_args_metadata_defaults_none() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.author_name is None
    assert result.description is None
    assert result.license is None
```

Update `test_main_with_package_name` (`test_main.py:167-177`) so the mocked
Namespace carries the new attributes and the assertion includes the new kwargs:

```python
def test_main_with_package_name() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        argparse_mock().parse_args().author_name = None
        argparse_mock().parse_args().description = None
        argparse_mock().parse_args().license = None
        init_mock.return_value = 0
        result = main()
    init_mock.assert_called_once_with(
        package_name='mypackage',
        author_name=None,
        description=None,
        package_license=None,
    )
    assert result == 0
```

The other `main` tests (`test_main.py:180-217`) do not assert call args and rely on
MagicMock auto-attributes for the new fields, so they need no change.

### Verification
#### Automated
- [x] `just test` passes (new + existing tests green; coverage ≥ 95%, `pyproject.toml:40`).
- [x] `just lint` passes (no `A002`/`ARG001`/other `ALL` violations).
- [x] `just check-complexity` passes (`init_new_package` mccabe ≤ 8 unchanged).
- [x] `just check` exits 0.

#### Manual
- [x] `uv run mp --help 2>&1 | grep -- '--author-name'` → prints the `--author-name` line.
- [x] `uv run mp --help 2>&1 | grep -e '--description' -e '--license'` → both lines present.
- [x] `uv run python -c "import sys; sys.argv=['m','mypkg','--author-name','Ada','--description','d','--license','MIT']; from modernpackage.main import parse_args; a=parse_args(); print(a.author_name, a.description, a.license)"` → prints `Ada d MIT`.

---

## Phase 2: Validated `--author-email` flag

Adds `--author-email` with parse-time email-shape validation, threaded like
Phase 1. Invalid emails are rejected with `ArgumentTypeError` (exit 2) before any
cloning occurs.

### Changes

#### 1. Email regex constant + validator
**File**: `modernpackage/main.py`
**Action**: modify

Add the `_EMAIL_RE` constant after the `_STDLIB_MODULE_NAMES` block (`main.py:70`),
with an explanatory comment (matches the `_RE`-suffix convention of
`_PACKAGE_NAME_RE`/`_DISALLOWED_CHAR_RE`):

```python
# Permissive email shape: non-whitespace, '@', non-whitespace, '.',
# non-whitespace. Full RFC 5322 validation is out of scope (design Decision 4).
_EMAIL_RE: re.Pattern[str] = re.compile(r'^\S+@\S+\.\S+$')
```

Add the validator near `validate_package_name`/`normalize_module_name`
(after `main.py:119`), mirroring the `validate_package_name` shape:

```python
def validate_author_email(value: str) -> str:
    """Validate value has a basic email shape; raise ArgumentTypeError otherwise."""
    if not _EMAIL_RE.match(value):
        message = f'Invalid author email: {value!r} — expected name@domain.tld'
        raise ArgumentTypeError(message)
    return value
```

#### 2. New validated argument in `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify

Add (alongside the Phase 1 flags, before `return parser.parse_args()`):

```python
parser.add_argument(
    '--author-email',
    help='Author email to record in the new package.',
    type=validate_author_email,
    default=None,
)
```

#### 3. Thread `author_email` through `init_new_package` + `main`
**File**: `modernpackage/main.py`
**Action**: modify

Add `author_email: str | None = None` to the keyword-only block of
`init_new_package` and extend the `del` statement:

```python
def init_new_package(
    package_name: str,
    *,
    author_name: str | None = None,
    author_email: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    del author_name, author_email, description, package_license
    ...
```

Extend the `main` call:

```python
return init_new_package(
    package_name=parsed_args.package_name,
    author_name=parsed_args.author_name,
    author_email=parsed_args.author_email,
    description=parsed_args.description,
    package_license=parsed_args.license,
)
```

#### 4. Tests
**File**: `tests/test_main.py`
**Action**: modify

Add `validate_author_email` to the import block (`test_main.py:8-15`). Add tests:

```python
def test_validate_author_email_accepts() -> None:
    assert validate_author_email('a@b.co') == 'a@b.co'


def test_validate_author_email_rejects() -> None:
    with pytest.raises(ArgumentTypeError, match='Invalid author email'):
        validate_author_email('not-an-email')


def test_parse_args_author_email() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--author-email', 'a@b.co']):
        result = parse_args()
    assert result.author_email == 'a@b.co'
```

Extend `test_main_with_package_name` to set and assert the new kwarg:
add `argparse_mock().parse_args().author_email = None` to the setup and
`author_email=None,` to the `init_mock.assert_called_once_with(...)`. Also add
`author_email is None` to `test_parse_args_metadata_defaults_none`.

### Verification
#### Automated
- [x] `just test` passes.
- [x] `just lint` passes.
- [x] `just check` exits 0.

#### Manual
- [x] `uv run mp --help 2>&1 | grep -- '--author-email'` → prints the flag line.
- [x] `uv run mp mypkg --author-email not-an-email; echo "exit=$?"` → stderr contains `Invalid author email` and prints `exit=2` (parse-time rejection; no clone occurs).
- [x] `uv run python -c "from modernpackage.main import validate_author_email as v; print(v('a@b.co'))"` → prints `a@b.co`.

---

## Phase 3: Validated `--repository-url` flag

Adds `--repository-url` requiring an `http(s)://` scheme (no network call),
threaded identically. Completes the five-flag set.

### Changes

#### 1. URL regex constant + validator
**File**: `modernpackage/main.py`
**Action**: modify

Add the `_REPOSITORY_URL_RE` constant next to `_EMAIL_RE` (after `main.py:70`
block):

```python
# Require an http(s):// scheme; no network/reachability check (design Decision 5).
_REPOSITORY_URL_RE: re.Pattern[str] = re.compile(r'^https?://\S+$')
```

Add the validator next to `validate_author_email`:

```python
def validate_repository_url(value: str) -> str:
    """Validate value is an http(s) URL; raise ArgumentTypeError otherwise."""
    if not _REPOSITORY_URL_RE.match(value):
        message = f'Invalid repository URL: {value!r} — expected http(s)://…'
        raise ArgumentTypeError(message)
    return value
```

#### 2. New validated argument in `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify

```python
parser.add_argument(
    '--repository-url',
    help='Repository URL to record in the new package.',
    type=validate_repository_url,
    default=None,
)
```

Namespace attribute is `.repository_url` (argparse dash→underscore mapping).

#### 3. Thread `repository_url` through `init_new_package` + `main`
**File**: `modernpackage/main.py`
**Action**: modify

Add `repository_url: str | None = None` as the final keyword-only param and extend
the `del`:

```python
def init_new_package(
    package_name: str,
    *,
    author_name: str | None = None,
    author_email: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
    repository_url: str | None = None,
) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    del author_name, author_email, description, package_license, repository_url
    ...
```

Extend the `main` call with `repository_url=parsed_args.repository_url`.

#### 4. Tests
**File**: `tests/test_main.py`
**Action**: modify

Add `validate_repository_url` to the import block. Add tests:

```python
def test_validate_repository_url_accepts() -> None:
    assert validate_repository_url('https://x.com/r') == 'https://x.com/r'


def test_validate_repository_url_rejects() -> None:
    for bad_url in ('ftp://x', 'x.com'):
        with pytest.raises(ArgumentTypeError, match='Invalid repository URL'):
            validate_repository_url(bad_url)


def test_parse_args_repository_url() -> None:
    with patch(
        'sys.argv', ['modernpackage', 'mypackage', '--repository-url', 'https://x.com/r']
    ):
        result = parse_args()
    assert result.repository_url == 'https://x.com/r'
```

Finalize `test_main_with_package_name`: add
`argparse_mock().parse_args().repository_url = None` to the setup and
`repository_url=None,` to the assertion so it covers all five kwargs. Add
`repository_url is None` to `test_parse_args_metadata_defaults_none`.

### Verification
#### Automated
- [x] `just test` passes.
- [x] `just lint` passes.
- [x] `just check-complexity` passes.
- [x] `just check` exits 0.

#### Manual
- [x] `uv run mp --help 2>&1 | grep -- '--repository-url'` → prints the flag line.
- [x] `uv run mp mypkg --repository-url x.com; echo "exit=$?"` → stderr contains `Invalid repository URL` and prints `exit=2`.
- [x] `uv run mp mypkg --repository-url ftp://x; echo "exit=$?"` → stderr contains `Invalid repository URL` and prints `exit=2`.
- [x] `uv run python -c "from modernpackage.main import validate_repository_url as v; print(v('https://x.com/r'))"` → prints `https://x.com/r`.

---

## Testing Checkpoints

- **After Phase 1**: `parse_args` returns `author_name`/`description`/`license`
  (default `None`); `init_new_package` signature accepts them keyword-only; `main`
  forwards them; the `del`/`ARG001` and `package_license` builtin-shadow decisions
  are settled here and reused unchanged in later phases; `just check` green.
- **After Phase 2**: `--author-email` parses; bad emails exit 2 with
  `ArgumentTypeError` before any clone; value threaded; `just check` green.
- **After Phase 3**: all five flags parse; bad email/URL exit 2; `main` calls
  `init_new_package` with all five new kwargs (verifiable via the single extended
  `init_mock.assert_called_once_with(...)`); `just check` green.
- **Resume aid**: each phase is purely additive and independently valuable — if
  Phase 3 stalls, Phases 1-2 ship working flags. No `pyproject.toml`, `Justfile`,
  or `just init` changes in any phase (design "What We're NOT Doing").

## Assumptions Resolved

- **`del` satisfies `ARG001`**: referencing the params in a `del` statement marks
  them used. If ruff disagrees, fall back to per-line `# noqa: ARG001` (documented
  in the cross-cutting constraints above).
- **Regex constant placement**: `_EMAIL_RE` (Phase 2) and `_REPOSITORY_URL_RE`
  (Phase 3) are added after the `_STDLIB_MODULE_NAMES` block (`main.py:70`),
  keeping all module-level `_RE` constants grouped; their validators sit next to
  `validate_package_name`.
- **`audit` step network dependency**: `just check` includes `audit` (pip-audit,
  `Justfile:40-41`) which needs network. If audit is unavailable offline, run the
  remaining gates individually (`just check-format check-lint check-complexity
  check-typecheck test`) and note the skipped audit; the metadata-flag changes add
  no dependencies, so audit results are unaffected.
