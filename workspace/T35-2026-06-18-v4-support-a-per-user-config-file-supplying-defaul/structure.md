# Structure Outline

## Approach

Add a per-user TOML config file as the **weakest** metadata default source,
consulted only after flag/env/git-config all yield `None`. Mirror the existing
source-reader shape (`_environment_default`, `_git_config_default`): module-
private `_`-prefixed helpers returning `str | None`, coalescing empty/non-string
to `None`, never raising on an absent source. Load the file **once** per
invocation into a mapping, then insert one `if … is None:` guard block per field
in `parse_args()` — placed **after** the git-config blocks (`main.py:278`) and
**before** validation (`main.py:279`) so file-sourced email/URL flow through the
existing `_validated_or_error` calls. Stdlib `tomllib` only; no new dependency.

New constants (module-level, `_`-prefixed, typed, comment-documented, matching
`main.py:84-96`):
- `_CONFIG_DIR_NAME: str = 'modernpackage'`
- `_CONFIG_FILE_NAME: str = 'config.toml'`
- `_XDG_CONFIG_HOME_ENV: str = 'XDG_CONFIG_HOME'`

The TOML schema is flat top-level keys named by the namespace dest:
`author_name`, `author_email`, `description`, `license`, `repository_url`.

---

## Phase 1: Config-file reader + free-string fields

Add path resolution, single-load TOML parsing, and per-field coercion; wire the
three fields with no validator (`author_name`, `description`, `license`) into the
fallback chain. Malformed/unreadable files degrade **silently** to no defaults in
this phase (the stderr notice is added in Phase 3).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_user_config_path() -> Path | None` — new. Resolve `$XDG_CONFIG_HOME` (empty →
  fallback) else `Path.home() / '.config'`; return `<base>/modernpackage/config.toml`.
  Return `None` if home unresolvable.
- `_load_config_file() -> dict[str, object]` — new. Read+parse the file with
  `tomllib.load`; missing file (`None` path / `FileNotFoundError`) → `{}`;
  `tomllib.TOMLDecodeError`/`OSError` → `{}` (silent here, refined in Phase 3).
- `_config_file_default(config: Mapping[str, object], key: str) -> str | None` —
  new. Return the value only if it is a non-empty `str`; else `None`.
- `parse_args()` — after git-config blocks, before validation: load once via
  `config_file = _load_config_file()`; add `if … is None:` guards reading
  `_config_file_default(config_file, '<dest>')` for `author_name`, `description`,
  `license`.
- `import tomllib`; `from collections.abc import Mapping` (if needed for annotation).

**Verify**: `just test` passes new tests (file fills each free-string field;
env/git override file; empty-string and non-string TOML values → `None`; absent
file → `None`). Manual:
```
mkdir -p /tmp/cfg/modernpackage
printf 'description = "from file"\nlicense = "MIT"\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION -u MODERNPACKAGE_LICENSE XDG_CONFIG_HOME=/tmp/cfg \
  python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; n=parse_args(); print(n.description, n.license)"
```
prints `from file MIT`.

---

## Phase 2: Validated fields (email + repository URL)

Wire `author_email` and `repository_url` file fallbacks. Because the new guards
sit before `main.py:279`, file-sourced values pass through the existing
`_validated_or_error` calls unchanged — invalid values exit 2.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `parse_args()` — add `if … is None:` guards for `author_email` and
  `repository_url` reading `_config_file_default(config_file, '<dest>')`,
  positioned after the git-config blocks and **before** the two
  `_validated_or_error(...)` calls (`main.py:279-284`). No change to the
  validators or `_validated_or_error`.

**Verify**: `just test` passes new tests (file fills email/URL when higher
sources absent; flag/env/git override; invalid file email and invalid file URL
each exit 2). Manual:
```
printf 'author_email = "nope"\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_AUTHOR_EMAIL XDG_CONFIG_HOME=/tmp/cfg \
  python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; parse_args()"; echo "exit=$?"
```
prints an `Invalid author email` error and `exit=2`.

---

## Phase 3: Malformed-file notice (graceful degradation)

Upgrade `_load_config_file()` from silent-on-error to a one-line `sys.stderr`
notice on `tomllib.TOMLDecodeError`/`OSError`, then continue with no defaults
(design Decision 6). Consistent with existing `print(..., file=sys.stderr)
# noqa: T201` usage (`main.py:353,379`).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_load_config_file()` — on parse/read error, `print('<notice>', file=sys.stderr)
  # noqa: T201` and `return {}`. Missing file stays silent (absent default is
  expected, not an error). Notice text names the config path.

**Verify**: `just test` passes new tests (malformed TOML → stderr notice captured
via `capsys`, scaffolding continues, all metadata `None`; absent file → no
notice). Manual:
```
printf 'this is = not valid toml =\n' > /tmp/cfg/modernpackage/config.toml
env -u MODERNPACKAGE_DESCRIPTION XDG_CONFIG_HOME=/tmp/cfg \
  python -c "import sys; sys.argv=['modernpackage','pkg']; from modernpackage.main import parse_args; print(parse_args().description)" 2>/tmp/err
cat /tmp/err   # contains config-file notice
```
stdout prints `None`; `/tmp/err` contains the notice.

---

## Phase 4: Documentation

Extend the per-flag precedence chains and the "Precedence" summary to include the
config file as the weakest source.

**Files**: `README.md` (79-100), `docs/overview.md` (55)

**Key changes**:
- Per-flag bullets: append `→ config file` before `→ None`, e.g.
  `$MODERNPACKAGE_AUTHOR_NAME → git config user.name → config file → None`.
- "Precedence" summary: `flag > env > git config > config file > None`
  (author_name/email) and `flag > env > config file > None` (the other three).
- Note config-file location (`$XDG_CONFIG_HOME/modernpackage/config.toml`,
  fallback `~/.config/...`), flat TOML keys, empty/non-string-as-unset, and
  malformed-file notice-and-continue. `--help` unchanged (matches git-config
  precedent).

**Verify**: `just check` passes (lint/format/typecheck/docs). Manual:
```
grep -c 'config file' README.md docs/overview.md   # each > 0
```
both files report a non-zero count.

---

## Testing Checkpoints

- **After Phase 1**: `_user_config_path`/`_load_config_file`/`_config_file_default`
  exist; config file supplies `author_name`/`description`/`license` when higher
  sources absent; env/git override it; empty/non-string values → `None`; absent
  file → `None`; tests isolate `XDG_CONFIG_HOME` to `tmp_path` so the real
  `~/.config` never leaks. Email/URL file fallback not yet wired.
- **After Phase 2**: all five fields fill from the file; file-sourced email/URL
  validated through `_validated_or_error` (invalid → exit 2); flag/env/git still
  win. Precedence is now `flag > env > git > file > None` (name/email) and
  `flag > env > file > None` (description/license/url).
- **After Phase 3**: malformed/unreadable file prints one stderr notice and
  continues with no file defaults; absent file stays silent.
- **After Phase 4**: README + docs document the file source and full precedence;
  `just check` green.

If context resets: confirm `tomllib` import, that the file guard blocks sit
between `main.py:278` (last git block) and `main.py:279` (first validation), and
that all new tests patch `XDG_CONFIG_HOME`/`tmp_path` rather than touching the
real home.
