# Design Discussion

## Current State

The metadata CLI plumbing is fully wired but reads nothing from the environment.

- `parse_args` (`main.py:145-188`) defines five metadata options, all with
  `default=None`: `--author-name` (`161-165`), `--description` (`166-170`),
  `--author-email` (`171-176`, `type=validate_author_email`), `--license`
  (`177-181`, namespace attr `license`), `--repository-url` (`182-187`,
  `type=validate_repository_url`).
- Validators `validate_author_email` (`main.py:129-134`) and
  `validate_repository_url` (`main.py:137-142`) raise `ArgumentTypeError` against
  `_EMAIL_RE` (`main.py:74`) / `_REPOSITORY_URL_RE` (`main.py:77`).
- **Validation lifecycle gap**: argparse runs a `type=` callable only on a string
  actually supplied on the command line. With `default=None` the default bypasses
  the validator (research Q2). Any value sourced from the environment must
  therefore be validated explicitly — it will *not* pass through `type=`.
- `main` (`main.py:264-285`) maps the namespace to `init_new_package` keyword
  args (`273-280`), including `package_license=parsed_args.license`.
- `init_new_package` (`main.py:191-199`) accepts all five as keyword-only
  `str | None` params, then immediately `del`s them (`main.py:201-203`):
  consumption (writing into `pyproject.toml`) is deferred V4 work.
- **No source code reads environment variables today.** `main.py` does not import
  `os` (`main.py:1-9`); no `os.environ`/`os.getenv` anywhere in `modernpackage/`
  (research Q4). The only precedent is the e2e test's `_GIT_IDENTITY_ENV`
  constant (`test_e2e.py:29-34`), using `GIT_AUTHOR_*`/`GIT_COMMITTER_*`. There is
  no established project convention for project-specific env-var names.

## Desired End State

When a metadata flag is omitted, its value falls back to a dedicated environment
variable; when the flag is present, the flag wins; when both are absent, the
value stays `None` (unchanged behaviour). Env-sourced email and repository URL
values are validated with the same rules as flag-supplied ones.

Verify by:
- `parse_args` with no flags but env vars set → namespace carries the env values.
- `parse_args` with a flag *and* the env var set → namespace carries the flag
  value (flag authoritative).
- `parse_args` with neither → all five attrs remain `None`
  (`test_parse_args_metadata_defaults_none`, `test_main.py:157-164`, still passes).
- An invalid env email / repository URL → clean CLI error exit (SystemExit), not
  a silently-propagated value or raw traceback.
- `just check` and `just test` pass.

## Patterns to Follow

- **Env-var name constants**: SCREAMING_SNAKE_CASE, `_`-prefixed module
  constants, annotated — mirror `_GIT_IDENTITY_ENV` (`test_e2e.py:29-34`) and the
  module-constant style at `main.py:12`, `main.py:70`. Use a `MODERNPACKAGE_`
  prefix to namespace cleanly.
- **Validators stay public, return-or-raise**: reuse `validate_author_email`
  /`validate_repository_url` (`main.py:129-142`) unchanged for env values; do not
  duplicate regex logic.
- **Single quotes, full annotations, one-line imperative docstrings** on any new
  helper (research Q6; `pyproject.toml:56-95`).
- **Test patterns**: `parse_args` tests patch `sys.argv` and assert on the
  namespace (`test_main.py:105-164`); add env via the built-in `monkeypatch`
  fixture (`monkeypatch.setenv`). `monkeypatch` is not yet used in
  `test_main.py` but is a built-in fixture and matches CLAUDE.md guidance.
- **`pattern NOT to follow`**: do not push env-fallback logic into `main` by
  passing env values into `init_new_package` from there — keep `main`'s mapping
  (`main.py:273-280`) untouched so the resolved namespace is the single source of
  truth and the existing `main` tests (which patch `ArgumentParser`,
  `test_main.py:231-253`) need no env setup.

## Design Decisions

1. **Where the fallback lives**: inside `parse_args`, after
   `parser.parse_args()`, not in `main`. — Keeps the returned `Namespace` fully
   resolved, leaves `main`/`init_new_package` and their tests unchanged, and lets
   the existing `parse_args` test style cover the new behaviour directly.

2. **Fallback mechanism**: keep each option's `default=None`; after parsing, for
   each of the five fields that is `None`, substitute the env value. — Avoids
   embedding `os.environ.get(...)` calls inside `add_argument` (which would read
   the environment at parse time regardless and scatter the logic). A small
   helper `_environment_default(variable_name)` returns `os.environ.get(name) or
   None` so set-but-empty env vars are treated as unset.

3. **Precedence = flag > env > None**: implemented naturally because all flags
   default to `None`; a `None` post-parse value means "flag absent", so env may
   fill it. A present flag is non-`None` and is left untouched.

4. **Validation of env values**: explicitly call `validate_author_email` /
   `validate_repository_url` on env-sourced email/URL before returning. On
   `ArgumentTypeError`, convert to `parser.error(message)` so the failure looks
   like any other CLI validation error (stderr + exit code 2) instead of a raw
   traceback. Re-validating a flag-supplied value is harmless and idempotent, so
   validation may be applied uniformly to the final non-`None` value.

5. **Env-var names** (dedicated, project-namespaced):
   `MODERNPACKAGE_AUTHOR_NAME`, `MODERNPACKAGE_AUTHOR_EMAIL`,
   `MODERNPACKAGE_DESCRIPTION`, `MODERNPACKAGE_LICENSE`,
   `MODERNPACKAGE_REPOSITORY_URL`. — Explicit and collision-free. Rejected
   reusing `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`: it conflates git commit identity
   with package metadata and would surprise users (see Open Risks).

6. **Empty string = unset**: `value or None` so `export MODERNPACKAGE_LICENSE=`
   behaves as "not set" rather than writing an empty license. — Matches the
   intent that env vars provide *defaults*, and avoids validating empty strings.

7. **`init_new_package` unchanged**: it continues to `del` the five params
   (`main.py:201-203`). This task only sources defaults; writing metadata into
   `pyproject.toml` remains the separate deferred V4 work.

## What We're NOT Doing

- Not consuming the metadata (no writes into `pyproject.toml`); the `del` at
  `main.py:201-203` stays.
- Not changing the validators, regex constants, help text, or the
  `license` → `package_license` mapping.
- Not reusing or reading `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env vars.
- Not adding a config-file layer, `.env` loading, or interactive prompts.
- Not validating `--author-name`, `--description`, or `--license` (they have no
  validator today; env values for them pass through as-is).
- Not modifying `main`'s namespace→keyword mapping or the e2e test.

## Open Risks

- **Validating env defaults vs. argparse contract**: argparse normally never
  validates defaults; calling `parser.error` from within `parse_args` after
  `parse_args()` is slightly unconventional but standard-library-safe. Confirm
  `parser.error` is reachable (parser is in scope) and exits 2.
- **Help-text discoverability**: env-var fallbacks are invisible in `--help`
  unless mentioned. Decision: append a brief note to each affected option's help
  string (low cost, improves discoverability) — confirm during planning.
- **`monkeypatch` first use in `test_main.py`**: introducing it is fine, but
  ensure env isolation so a developer's real `MODERNPACKAGE_*` vars cannot leak
  into the default-`None` test (`test_main.py:157-164`) — that test should
  `monkeypatch.delenv(..., raising=False)` or set nothing while the harness
  guarantees a clean env.
- **mypy strict / ruff ALL** (`pyproject.toml:56-95`): new helper needs full
  annotations and a docstring; `import os` must be used.
```

Next: run `/lifecycle:4_structure workspace/T33-2026-06-18-v4-read-author-metadata-defaults-from-environment/`
