# Design Discussion

## Current State

`parse_args()` (`main.py:206-285`) resolves the five metadata fields
(author_name, author_email, description, license, repository_url) from an
ordered set of sources, implemented as imperative `if … is None:` guards rather
than any data structure:

1. Flags declared with `default=None` so an omitted flag yields `None`
   (`main.py:222-263`). Email/URL flags carry `type=` validators
   (`main.py:244,261`).
2. Environment defaults applied for all five fields via
   `_environment_default(name)` (`main.py:164-166`, applied `main.py:265-274`).
   A missing or set-but-empty var coalesces to `None`.
3. Git-config defaults applied **only** for author_name/author_email via
   `_git_config_default(key)` (`main.py:169-189`, applied `main.py:275-278`).
   Degrades silently to `None` when git is missing, key unset, or value empty.
4. Non-flag email/URL re-validated via `_validated_or_error(parser, value,
   validator)` (`main.py:192-203`, applied `main.py:279-284`), converting an
   `ArgumentTypeError` into `parser.error(...)` (exit code 2).

Effective precedence today: `flag > env > git config > None` (author_name,
author_email); `flag > env > None` (description, license, repository_url).

There is **no structured-file reading anywhere in the source** (research Q4).
`requires-python >= 3.14` (`pyproject.toml:8`) so stdlib `tomllib` is available,
but is not imported. Runtime `dependencies = []` (`pyproject.toml:18`).
README (`README.md:79-100`) and `docs/overview.md:55` document the source
precedence; `docs/vision.md:44` describes this per-user config file as planned.

## Desired End State

A per-user TOML config file supplies metadata defaults as the **weakest**
source, consulted only after flag, env, and git config all yield `None` (per
task: "supplies defaults when the … flag, environment variable, and git-config
sources do not provide a value"). New effective precedence:

- author_name / author_email: `flag > env > git config > config file > None`
- description / license / repository_url: `flag > env > config file > None`

Verify via `tests/test_main.py`: config file fills each field when higher
sources absent; flag/env/git config each override config file; malformed file
degrades to no defaults without aborting; empty/non-string TOML values treated
as unset; email/URL sourced from the file are validated (invalid → exit 2).

## Patterns to Follow

- **Source-reader shape**: model the file reader on `_environment_default`
  (`main.py:164-166`) and `_git_config_default` (`main.py:169-189`) — a
  module-private `_`-prefixed function returning `str | None`, coalescing
  empty to `None`, never raising on an absent source.
- **Guard insertion**: add `if … is None:` blocks after the git-config blocks
  (`main.py:278`) and **before** validation (`main.py:279`) so file-sourced
  email/URL flow through the existing `_validated_or_error` calls unchanged.
- **Constants**: module-level, `_`-prefixed, typed, comment-documented with a
  precedence note, matching the env/git constant block (`main.py:84-96`).
- **Graceful degradation at the boundary**: a malformed/unreadable file prints
  a notice to `sys.stderr` and continues — consistent with existing
  `print(..., file=sys.stderr)  # noqa: T201` usage (`main.py:353,379`) and the
  "degrade gracefully at external boundaries" rule in Code Best Practices.
- **Docs**: extend the README per-flag precedence chains and "Precedence"
  summary (`README.md:83-96`) and `docs/overview.md:55`, mirroring the existing
  `$ENV → git config → None` wording.
- **Tests**: `monkeypatch.setenv`/`delenv` (`test_main.py:163,217`), `sys.argv`
  patching (`test_main.py:99`), patch the reader seam on the module object like
  `_git_config_default` (`test_main.py:539-545`), use `tmp_path` for the file.

### Patterns to NOT follow
- Do not introduce a config-object / list-of-callables abstraction to "unify"
  sources — precedence is deliberately imperative `if … is None:` guards
  (research Cross-Cutting). Match that; one more guard block per field.

## Design Decisions

1. **Precedence slot — weakest source**: config file is consulted last (after
   git config). The task lists it as filling in when flag/env/git all miss, so
   it ranks below git config rather than above it. Recorded because intuition
   often places a user config above git config.
2. **Format = TOML via stdlib `tomllib`**: TOML is the project's config idiom
   (`pyproject.toml`), and `tomllib` ships in stdlib for Python ≥ 3.14
   (`pyproject.toml:8`), so no new dependency (`dependencies = []`).
3. **Location = `$XDG_CONFIG_HOME/modernpackage/config.toml`** falling back to
   `~/.config/modernpackage/config.toml`. Standard XDG convention; resolved with
   the already-imported `os` and `pathlib.Path` (`main.py:3,7`). No `--config`
   flag (not requested).
4. **Schema = flat top-level keys** named by the namespace dest:
   `author_name`, `author_email`, `description`, `license`, `repository_url`.
   Only metadata exists today, so a flat layout keeps parsing trivial; a future
   nested section can be added without breaking these keys.
5. **Value coercion**: a key is treated as set only if its value is a non-empty
   `str`; empty strings and non-string TOML values (int/bool/array/table)
   coalesce to `None`, matching the empty-as-unset convention of the env/git
   readers and protecting the regex validators from non-str input.
6. **Malformed/unreadable file → notice + continue**: on
   `tomllib.TOMLDecodeError` (or `OSError`), print a one-line `sys.stderr`
   notice and proceed with no file-sourced defaults. Unlike an absent git
   default, a corrupt config is a likely user mistake worth surfacing, but it
   should not abort scaffolding. (Open risk below.)
7. **Single load per invocation**: parse the file once into a mapping, then read
   per-field, rather than re-opening it five times. Load it unconditionally in
   the fallback section for simplicity; the cost is one file read.
8. **`--help` unchanged; document in README/docs**: git config is already not
   advertised in `--help` (research Q5), so the file source follows that
   precedent. Discoverability lives in README + docs to avoid cluttering all
   five `help=` strings.

## What We're NOT Doing

- No `--config` / `-c` flag or `$MODERNPACKAGE_CONFIG` path override.
- No writing/creating the config file; the tool only reads it.
- No nested TOML sections, profiles, or per-project config files.
- No new runtime dependency (no `tomli` backport — stdlib only).
- No change to git-config-only-for-two-fields rule (file supplies all five).
- No changes to `init_new_package`/`main` plumbing (`main.py:288-382`); only
  the resolution stage of `parse_args()` changes.
- No writing metadata into `pyproject.toml` (still deferred V4 work,
  `main.py:298`).

## Open Risks

- **Malformed-file policy** (Decision 6): notice-and-continue vs. `parser.error`
  abort is a judgment call. If reviewers prefer fail-fast, switch to
  `parser.error(...)` (exit 2) — the parser is in scope at the call site.
- **XDG home edge cases**: `XDG_CONFIG_HOME` set but empty, or `Path.home()`
  unresolvable in odd environments. Mitigate by coalescing empty `XDG_CONFIG_HOME`
  to the `~/.config` fallback and treating a missing file as "no defaults".
- **Test isolation of the real user home**: tests must point resolution at
  `tmp_path` (via `monkeypatch.setenv('XDG_CONFIG_HOME', …)` or patching the
  path helper) so a developer's real `~/.config/modernpackage/config.toml` does
  not leak into the suite.
- **Validation ordering**: file blocks must be inserted before `main.py:279` or
  file-sourced email/URL would bypass `_validated_or_error`. Easy to misplace.
