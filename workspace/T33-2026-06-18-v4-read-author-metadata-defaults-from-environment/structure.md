# Structure Outline

## Approach

Resolve metadata defaults from dedicated `MODERNPACKAGE_*` environment variables
*inside* `parse_args`, after `parser.parse_args()`. Each flag keeps
`default=None`; a post-parse pass substitutes the env value for any field still
`None` (flag > env > None). Env-sourced email and repository URL are validated
explicitly via the existing validators, with `ArgumentTypeError` converted to
`parser.error(...)` so failures look like normal CLI errors. `main` and
`init_new_package` (and their tests) stay untouched — the returned `Namespace`
is the single source of truth.

Each phase below is a vertical slice through the same stack: env-var name
constants (data) → resolution logic in `parse_args` (service) → CLI behaviour /
help text (interface) → `tests/test_main.py` (verification). Slices are cut by
*validation concern*, not by layer.

---

## Phase 1: Env fallback for unvalidated fields (name, description, license)

Introduces the env-default machinery end to end and applies it to the three
fields that have no validator. Delivers working env fallback for the simplest
cases and proves precedence (flag > env > None) without validation noise.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `import os` — new (module currently does not import it).
- Module constants (annotated, `_`-prefixed, `SCREAMING_SNAKE_CASE`):
  - `_AUTHOR_NAME_ENV: str = 'MODERNPACKAGE_AUTHOR_NAME'`
  - `_DESCRIPTION_ENV: str = 'MODERNPACKAGE_DESCRIPTION'`
  - `_LICENSE_ENV: str = 'MODERNPACKAGE_LICENSE'`
- `_environment_default(variable_name: str) -> str | None` — new helper;
  returns `os.environ.get(variable_name) or None` (empty string → `None`).
- In `parse_args`, after `parser.parse_args()`: for `author_name`,
  `description`, and `license`, when the namespace attr is `None`, substitute
  `_environment_default(<corresponding constant>)`. Return the mutated namespace.

**Verify**: `just test` passes, including existing
`test_parse_args_metadata_defaults_none` (`test_main.py:157-164`). New
`monkeypatch`-based tests:
- `monkeypatch.setenv('MODERNPACKAGE_DESCRIPTION', 'from-env')` + argv
  `['modernpackage', 'mypackage']` → `parsed.description == 'from-env'`.
- Flag wins: same env set, argv adds `--description cli` →
  `parsed.description == 'cli'`.
- Empty env: `monkeypatch.setenv('MODERNPACKAGE_LICENSE', '')` →
  `parsed.license is None`.
- Defaults-none test still green with the five env vars `delenv(..., raising=False)`.

Run: `just check && just test`.

---

## Phase 2: Validated env fallback (author-email, repository-url)

Extends the Phase 1 mechanism to the two validated fields and routes invalid
env values through `parser.error` so they exit cleanly (code 2) instead of
raising a raw `ArgumentTypeError` traceback.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- Constants: `_AUTHOR_EMAIL_ENV: str = 'MODERNPACKAGE_AUTHOR_EMAIL'`,
  `_REPOSITORY_URL_ENV: str = 'MODERNPACKAGE_REPOSITORY_URL'`.
- Extend the post-parse pass in `parse_args` to fill `author_email` and
  `repository_url` from env when `None`, then validate the resolved (non-`None`)
  value:
  - call `validate_author_email` / `validate_repository_url`; on
    `ArgumentTypeError as error: parser.error(str(error))`.
  - Validation applied to the final non-`None` value (re-validating a
    flag-supplied value is idempotent and harmless — design Decision 4).
- No change to validators or regex constants.

**Verify**: `just test` passes. New tests:
- Valid env: `setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'a@b.co')` →
  `parsed.author_email == 'a@b.co'`.
- Invalid env email: `setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'nope')` + argv
  `['modernpackage', 'mypackage']` → `pytest.raises(SystemExit)` with
  `excinfo.value.code == 2`; capture stderr contains `Invalid author email`.
- Invalid env repository URL: analogous, stderr contains `Invalid repository URL`.
- Flag-overrides-env still holds for both validated fields.

Run: `just check && just test`.

---

## Phase 3: Help-text discoverability

Append a short note to each of the five options' `help=` strings naming the
fallback env var, so `--help` documents the behaviour (Open Risk:
discoverability). Pure interface polish; no logic change.

**Files**: `modernpackage/main.py`, `tests/test_main.py` (optional assertion)

**Key changes**:
- Each affected `add_argument(..., help=...)` gains a suffix such as
  `' Defaults to $MODERNPACKAGE_AUTHOR_NAME.'` (single quotes, matching style).

**Verify**: `just check && just test` pass. Manual probe:
`python -m modernpackage --help` (or the project entrypoint) exits 0 and stdout
contains `MODERNPACKAGE_AUTHOR_NAME` and `MODERNPACKAGE_REPOSITORY_URL`.
Run: `python -m modernpackage --help | grep MODERNPACKAGE_`.

---

## Testing Checkpoints

- **After Phase 1**: `_environment_default` exists; `import os` used (mypy
  strict / ruff ALL clean). Env fallback works for name/description/license;
  flag beats env; empty string treated as unset; the pre-existing
  defaults-none test still passes. `just check && just test` green.
- **After Phase 2**: Env fallback works for all five fields. Invalid env email
  or URL exits with code 2 and a CLI-style stderr message (no traceback); valid
  env values pass through; flag still authoritative. `main` /
  `init_new_package` and the e2e test remain unmodified.
- **After Phase 3**: `--help` advertises every `MODERNPACKAGE_*` var. Full
  suite and lint/type gates pass.

**Resumption note**: all production changes live in `modernpackage/main.py`
(constants block + `_environment_default` + post-parse block in `parse_args`);
all new tests in `tests/test_main.py` using the built-in `monkeypatch` fixture.
Nothing outside these two files should change.
