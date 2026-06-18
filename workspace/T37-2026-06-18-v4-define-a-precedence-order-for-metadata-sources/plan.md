# Implementation Plan

## Overview

Replace the ~14 scattered `if <field> is None:` metadata fill-in lines in
`parse_args()` / `_apply_config_file_defaults()` with one declarative
`_MetadataField` descriptor table plus a single first-non-`None` resolver, then
bring `--help` and the two stale docs in line with the
`flag > env > git config > config file > None` ladder the code implements. This is
a behaviour-preserving refactor: the three readers and the post-resolution
validation are reused verbatim, so the existing `tests/test_main.py` precedence
suite must pass unmodified.

**Project gates (cite `pyproject.toml`, do not hardcode):** `line-length = 88`
(`pyproject.toml:57`), `max-complexity = 8` (`pyproject.toml:79`). The single
resolver loop stays well under the complexity limit (McCabe ≈ 6).

**Test/lint commands (from `Justfile`):** `just test`, `just check`
(= `check-format` + `check-lint` + `check-complexity` + `check-typecheck` +
`test` + `audit`).

---

## Phase 1: Descriptor table + single resolver

Introduce the data-driven precedence model, rewire `parse_args()` to use it, and
delete the per-field `None`-guard ladders. Observable CLI behaviour is identical.

### Changes

#### 1. Add `dataclass` import
**File**: `modernpackage/main.py`
**Action**: modify (`main.py:7`)

The module currently imports from `argparse` and `pathlib` but not
`dataclasses`. Add the import (place it with the other stdlib imports, after the
`argparse` line at `main.py:7`):

```python
from dataclasses import dataclass
```

`Namespace` is already imported at runtime (`main.py:7`); `Mapping` is already in
the `TYPE_CHECKING` block (`main.py:13`) and stays needed by `_config_file_default`
and the new resolver, so no import change is required for those.

#### 2. Field descriptor + table
**File**: `modernpackage/main.py`
**Action**: create — insert immediately after the config-file constants block
(after `main.py:104`, the `_XDG_CONFIG_HOME_ENV` line)

```python
@dataclass(frozen=True)
class _MetadataField:
    """Declares how one metadata field resolves its default, sources in order."""

    attr: str  # Namespace attribute the flag stores to (e.g. 'author_name')
    env_var: str  # Environment variable consulted after the flag
    git_key: str | None  # git config key consulted next; None = no git source
    config_key: str  # Config-file flat key consulted last


# One entry per metadata field. Sources are tried in the canonical order
# env -> git config -> config file; the flag value already in the namespace wins
# implicitly because the resolver only fills attrs still set to None. git_key=None
# encodes the author-only asymmetry: description / license / repository_url have
# no git source (precedence: flag > env > config file > None), while author_name /
# author_email do (flag > env > git config > config file > None).
_METADATA_FIELDS: tuple[_MetadataField, ...] = (
    _MetadataField('author_name', _AUTHOR_NAME_ENV, _GIT_CONFIG_USER_NAME_KEY, 'author_name'),
    _MetadataField('description', _DESCRIPTION_ENV, None, 'description'),
    _MetadataField('license', _LICENSE_ENV, None, 'license'),
    _MetadataField('author_email', _AUTHOR_EMAIL_ENV, _GIT_CONFIG_USER_EMAIL_KEY, 'author_email'),
    _MetadataField('repository_url', _REPOSITORY_URL_ENV, None, 'repository_url'),
)
```

(Per-field order in the tuple is irrelevant to results — each field resolves
independently — but mirroring the original field order keeps diffs legible.)

#### 3. Single resolver — replaces `_apply_config_file_defaults`
**File**: `modernpackage/main.py`
**Action**: delete `_apply_config_file_defaults` (`main.py:256-273`) and create
`_resolve_metadata_defaults` in its place.

```python
def _resolve_metadata_defaults(
    arguments: Namespace, config: Mapping[str, object]
) -> None:
    """Fill each None metadata field from its first available source, in-place.

    Walks `_METADATA_FIELDS`; for a field still None, tries env, then git config
    (only if the descriptor names a git key), then the config file, stopping at
    the first non-None value. Each source is consulted lazily and only when the
    higher-priority sources came back None, so "loser never consulted" assertions
    hold (a stronger source never triggers a weaker reader). The config file is
    passed in pre-loaded so it is read exactly once per `parse_args()` call.
    """
    for field in _METADATA_FIELDS:
        if getattr(arguments, field.attr) is not None:
            continue
        value = _environment_default(field.env_var)
        if value is None and field.git_key is not None:
            value = _git_config_default(field.git_key)
        if value is None:
            value = _config_file_default(config, field.config_key)
        setattr(arguments, field.attr, value)
```

#### 4. Rewire `parse_args()`
**File**: `modernpackage/main.py`
**Action**: modify — delete the env block (`main.py:349-358`), the git block
(`main.py:359-362`), and the `_apply_config_file_defaults(...)` call
(`main.py:363`); replace all of them with a single call. The validation block
(`main.py:364-369`) and `return arguments` (`main.py:370`) are unchanged.

Replace lines `349-363`:

```python
    arguments = parser.parse_args()
    if arguments.author_name is None:
        arguments.author_name = _environment_default(_AUTHOR_NAME_ENV)
    # ... 13 more if-is-None lines ...
    _apply_config_file_defaults(arguments, _load_config_file())
```

with:

```python
    arguments = parser.parse_args()
    _resolve_metadata_defaults(arguments, _load_config_file())
```

`_load_config_file()` is still called exactly once, inline, preserving
single-load semantics.

### Verification
#### Automated
- [x] `just test` passes with **zero edits** to `tests/test_main.py` (precedence
  suite, "loser never consulted" at `test_main.py:553-556`/`:573-575`,
  exit-code-2 tests at `:611-627`/`:786-801`)
- [x] `just check` passes (`check-complexity` confirms the resolver is ≤ 8;
  `check-typecheck` confirms the `Namespace`/`Mapping` annotations type-check)

#### Manual
- [x] No per-field metadata `is None` ladder remains in `parse_args`:
  `grep -n "is None" modernpackage/main.py` shows only `_validated_or_error`'s
  guard (`main.py:282`) and the resolver's own checks — no `arguments.<field> is None`
  fill blocks
- [x] `_apply_config_file_defaults` is gone:
  `grep -c "_apply_config_file_defaults" modernpackage/main.py` returns `0`
- [x] Resolver and table exist:
  `grep -nE "_resolve_metadata_defaults|_METADATA_FIELDS|class _MetadataField" modernpackage/main.py`
  returns 3+ matches
- [x] env wins over git/config (behaviour spot-check):
  `MODERNPACKAGE_AUTHOR_NAME=EnvName python -c "import sys; sys.argv=['mp','pkg']; from modernpackage.main import parse_args; print(parse_args().author_name)"`
  prints `EnvName`

---

## Phase 2: `--help` text states the full ladder

Update each metadata flag's help string so `--help` describes the real source
chain instead of only the env var. Code + the one intended test change.

### Changes

#### 1. Author-name / author-email help strings (4-level ladder)
**File**: `modernpackage/main.py`
**Action**: modify the `help=` strings at `main.py:308-311` (`--author-name`) and
`main.py:324-327` (`--author-email`).

`--author-name`:
```python
        help=(
            'Author name to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_NAME, then git config'
            ' user.name, then the config.toml config file.'
        ),
```

`--author-email`:
```python
        help=(
            'Author email to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_EMAIL, then git config'
            ' user.email, then the config.toml config file.'
        ),
```

#### 2. Description / license / repository-url help strings (3-level ladder)
**File**: `modernpackage/main.py`
**Action**: modify the `help=` strings at `main.py:316-319` (`--description`),
`main.py:333-336` (`--license`), `main.py:341-344` (`--repository-url`). Mention
the env var and the config file (no git config).

`--description`:
```python
        help=(
            'Short description of the new package.'
            ' Defaults to $MODERNPACKAGE_DESCRIPTION, then the config.toml'
            ' config file.'
        ),
```

`--license`:
```python
        help=(
            'License identifier for the new package.'
            ' Defaults to $MODERNPACKAGE_LICENSE, then the config.toml'
            ' config file.'
        ),
```

`--repository-url`:
```python
        help=(
            'Repository URL to record in the new package.'
            ' Defaults to $MODERNPACKAGE_REPOSITORY_URL, then the config.toml'
            ' config file.'
        ),
```

#### 3. Extend the help test
**File**: `tests/test_main.py`
**Action**: modify `test_parse_args_help_advertises_env_vars` (`test_main.py:267-274`)
— keep the existing env-var assertions and add assertions for the new
git-config and config-file mentions. (This is the single intended test change.)

```python
    assert 'MODERNPACKAGE_AUTHOR_NAME' in help_text
    assert 'MODERNPACKAGE_REPOSITORY_URL' in help_text
    assert 'user.name' in help_text
    assert 'user.email' in help_text
    assert 'config.toml' in help_text
```

### Verification
#### Automated
- [x] `just test` passes including the updated `test_parse_args_help_advertises_env_vars`
- [x] `just check` passes (help strings respect `line-length = 88`,
  `pyproject.toml:57`)

#### Manual
- [x] `python -m modernpackage --help` output contains `user.name`, `user.email`,
  and `config.toml`:
  `python -m modernpackage --help | grep -E "user.name|user.email|config.toml"`
  returns matches
- [x] author-name flag advertises the git/config chain:
  `python -m modernpackage --help | grep -A3 -- '--author-name'` shows
  `user.name` and `config.toml`

---

## Phase 3: Documentation brought in line

Fix the two stale prose docs so all written descriptions of the ladder agree
with the code. No code change. Do **not** touch `docs/overview.md` or
`docs/architecture.md` — they already match reality (research Q5).

### Changes

#### 1. `docs/specification.md` — add metadata flags + precedence
**File**: `docs/specification.md`
**Action**: modify the stale `parse_args()` section (`specification.md:44-48`),
which currently documents only `-v` and `package_name`. Add the metadata flags
and the precedence ladder. Append the following bullets after the existing
`package_name` bullet (`specification.md:46`):

```markdown
  - `--author-name`, `--author-email`, `--description`, `--license`, `--repository-url`: optional metadata flags, each `default=None`, resolved through a declarative precedence ladder after parsing.
- **Metadata defaults precedence** (`main.py`, `_resolve_metadata_defaults` over `_METADATA_FIELDS`): when a metadata flag is omitted, its value is resolved first-non-`None` through an ordered source list. For `author_name` / `author_email`: `flag > env > git config > config file > None`. For `description` / `license` / `repository_url` (no git source): `flag > env > config file > None`. Validation (email, URL) runs once on the final resolved value, source-agnostic.
```

(The stale `main.py:18-34` line ref on `specification.md:44` predates the
metadata feature; leave the surrounding prose otherwise as-is — only add the
flags and ladder per CLAUDE.md §3.)

#### 2. `docs/invocation.md` — fix the false "not yet written" note
**File**: `docs/invocation.md`
**Action**: modify — replace the stale paragraph at `invocation.md:421`.

Current:
```markdown
**Note**: The metadata flags are optional and defaulting to `None`. They are currently threaded through the initialization flow but not yet written to `pyproject.toml` (that is deferred to later V4 work). You can provide them to scaffold the package foundation, and they will be available for future use.
```

Replace with:
```markdown
**Note**: The metadata flags are optional and default to `None`. Each resolved (non-`None`) value is written into the new package's `pyproject.toml` by `_write_package_metadata` after the template is cloned and before the initial git commit, so the metadata lands in the first commit. A field left `None` leaves its template placeholder untouched.
```

### Verification
#### Automated
- [x] `just check` passes (no doc-linter regression; docs are not linted by ruff,
  but run it to confirm nothing else broke)

#### Manual
- [x] specification.md now states the ladder:
  `grep -n "flag > env > git config > config file > None" docs/specification.md`
  returns a match
- [x] specification.md lists the metadata flags:
  `grep -n -- "--repository-url" docs/specification.md` returns a match
- [x] the stale invocation.md note is gone:
  `grep -n "not yet written" docs/invocation.md` returns **no** match
- [x] invocation.md now references the writer:
  `grep -n "_write_package_metadata" docs/invocation.md` returns a match
- [x] correct docs left untouched:
  `grep -rn "flag > env" docs/overview.md docs/architecture.md` still returns
  matches (these were not edited)

---

## Testing Checkpoints

- **After Phase 1**: `just test` + `just check` green with an unmodified test
  file; `parse_args()` contains no per-field `if x is None` metadata ladder; one
  resolver walks `_METADATA_FIELDS`; CLI output for every flag/env/git/config
  combination is identical to before. This phase alone delivers the core
  "single, explicit rule".
- **After Phase 2**: `--help` advertises the full ladder; the help test asserts
  git/config mentions. Independently valuable even if Phase 3 is skipped.
- **After Phase 3**: every written description (`--help`, `specification.md`,
  `invocation.md`, `overview.md`, `architecture.md`) agrees with the implemented
  precedence; no stale/contradictory paragraph remains.

If context resets, Phase 1 is the only behaviour-bearing change; Phases 2–3 are
documentation alignment and can be verified independently by the greps above.

## Resolved Assumptions

- **Help-text wording / test substrings.** The structure left the exact help
  phrasing open. Chosen wording embeds the literal substrings `user.name`,
  `user.email`, and `config.toml` so the Phase 2 test can assert them directly
  and the file-config name matches `_CONFIG_FILE_NAME = 'config.toml'`
  (`main.py:103`).
- **Resolver placement.** `_resolve_metadata_defaults` replaces
  `_apply_config_file_defaults` at its location (`main.py:256`); the descriptor
  table sits with the related env/git/config constants (after `main.py:104`).
- **Complexity / line-length numbers.** Taken from this repo's
  `pyproject.toml` (`max-complexity = 8`, `line-length = 88`), not the
  CLAUDE.md general guidance (which cites a different project's ≤10 / 120).
