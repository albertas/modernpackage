# Design Discussion

## Current State

`modernpackage/main.py` is a single-file CLI. `parse_args` (`main.py:122-138`)
builds a bare `ArgumentParser()` and defines exactly two arguments: the
`-v/--version` flag (`main.py:125-131`) and the optional positional
`package_name` (`main.py:132-137`, `nargs='?'`, `type=validate_package_name`).

`main` (`main.py:202-216`) branches on the Namespace: `--version` prints the
version; a truthy `package_name` calls
`init_new_package(package_name=parsed_args.package_name)` inside a
`try/except RuntimeError` (`main.py:209-214`). `init_new_package(package_name)`
(`main.py:141-199`) normalizes the name, clones the template, and runs
`just init <module_name>` then `just check` via three `Popen` calls.

Validation today is parse-time only, wired through argparse's `type=` hook:
`validate_package_name` (`main.py:95-108`) raises `ArgumentTypeError` (argparse
prints to stderr, exits 2) for invalid names, with precise reasons from
`_explain_invalid_package_name` (`main.py:73-92`). Runtime/external failures use
the second tier: `RuntimeError` surfaced by `main` to stderr with exit code 1.

The template `pyproject.toml` holds static placeholders: `authors` with
`Name Surname` / `email@example.com` (`pyproject.toml:3-5`), `description`
(`pyproject.toml:6`), an MIT license **classifier** (`pyproject.toml:11`, no
`license` key), and `[project.urls] homepage` (`pyproject.toml:20-21`, no
`repository` key). **No code path reads or rewrites author/email/description
today** — only `name` and version are transformed by `just init`
(`Justfile:59-73`). There is no existing CLI flag, `parse_args` argument, or
`init_new_package` parameter for any of the new metadata fields.

## Desired End State

The CLI accepts five new optional flags for package metadata and threads the
parsed values into `init_new_package`:

- `--author-name`, `--author-email`, `--description`, `--license`,
  `--repository-url`

After this task:
- `parse_args` returns a Namespace carrying `author_name`, `author_email`,
  `description`, `license`, `repository_url` (each defaulting to `None`).
- Invalid `--author-email` and `--repository-url` values are rejected at parse
  time with an `ArgumentTypeError` (exit 2), matching the existing convention.
- `main` forwards all five values as keyword arguments into `init_new_package`.
- `init_new_package` accepts them as optional keyword parameters (default
  `None`). It does **not** yet write them into `pyproject.toml` — that
  substitution is later V4 work (see task.md: "forming the foundation for later
  V4 work").

**Verification:**
- `just check` passes (lint + typecheck + tests).
- New unit tests assert: each flag parses into the expected Namespace attribute;
  invalid email / URL raise `ArgumentTypeError`; `main` calls
  `init_new_package` with the new keyword arguments (extend the existing
  `init_mock.assert_called_once_with(...)` pattern at `test_main.py:167-177`).

## Patterns to Follow

- **Flag definition**: mirror the `add_argument` style in `parse_args`
  (`main.py:125-137`) — long `--kebab-case` option strings, short imperative
  help ending with a period, explicit `default`.
- **Parse-time validation via `type=`**: follow `validate_package_name`
  (`main.py:95-108`) — a top-level `validate_*` function that raises
  `ArgumentTypeError(f'… {value!r} — {reason}')`. New validators:
  `validate_author_email`, `validate_repository_url`.
- **Compiled regex constants**: suffix `_RE`, module-level, with an explanatory
  comment, like `_PACKAGE_NAME_RE` (`main.py:58-61`) and `_DISALLOWED_CHAR_RE`
  (`main.py:65`).
- **Keyword-argument threading**: `main` passes values by keyword
  (`init_new_package(package_name=...)`, `main.py:211`); extend the same call.
- **Two-tier error reporting**: `ArgumentTypeError` for bad CLI input vs
  `RuntimeError` for runtime failures (Cross-Cutting Observations, research).
- **Test seams**: patch on the defining module object
  (`modernpackage.main.ArgumentParser`, `.Popen`), use `sys.argv` patching for
  `parse_args` tests (`test_main.py:91-100`), plain `assert`, top-level
  `def test_*` (Code Best Practices).

**Do NOT** add SPDX validation, URL reachability checks, or rewrite the
`just init` recipe / `pyproject.toml` — research found no such patterns and the
task explicitly defers value-writing to later V4 work.

## Design Decisions

1. **Long-only flag names** (`--author-name`, `--author-email`, `--description`,
   `--license`, `--repository-url`): no single-letter short forms. Only the
   pre-existing `--version` has a short alias; these five are infrequent and
   short letters would collide / read poorly. Matches `--long` convention.

2. **Optional with `default=None`**: all five are optional. `None` (rather than
   `''`) cleanly signals "not supplied" so later V4 work can decide between a
   flag value, a default source, or the template placeholder. Omitting an
   explicit `default` would also yield `None`, but state it explicitly per the
   "annotate where inference is ambiguous" guideline.

3. **Validate only email and URL**; leave `--author-name`, `--description`,
   `--license` as free strings. Names and descriptions are free-form. License is
   left unvalidated this task: a correct SPDX check is non-trivial and the
   template uses a classifier, not a `license` key — out of scope.

4. **`validate_author_email` uses a deliberately permissive regex**
   (`non-whitespace@non-whitespace.non-whitespace`, an `_EMAIL_RE` constant).
   Full RFC 5322 validation is a known rabbit hole; a pragmatic shape check
   matches the project's "reject obviously wrong input loudly" stance without
   over-engineering (CLAUDE.md §2 Simplicity First).

5. **`validate_repository_url` requires an `http(s)://` scheme** via a
   `_REPOSITORY_URL_RE` constant; no network call. Reachability checks belong to
   runtime/external boundaries, not parse-time validation, and the task forbids
   speculative work.

6. **`init_new_package` gains five keyword params, default `None`**, threaded but
   not yet consumed. The function signature documents the foundation for V4. To
   avoid unused-argument lint noise, params are accepted but referenced minimally
   (e.g. via a docstring note); we do not invent substitution logic now.
   *Assumption*: "thread through to the entry point" means reaching
   `init_new_package`'s signature, not writing files — consistent with task.md
   scoping the value-writing to later V4 work.

7. **Namespace attribute names** follow argparse's dash→underscore mapping:
   `author_name`, `author_email`, `repository_url`. Full words, no
   abbreviations (CLAUDE.md §6).

## What We're NOT Doing

- Not modifying `pyproject.toml`, the `just init` recipe, or any `sed`/`git grep`
  substitution — no metadata is written into the scaffold this task.
- Not reading defaults from git config, environment, or any other source (that
  is the "reads defaults from other sources" later-V4 work named in task.md).
- Not adding SPDX license validation or URL reachability/network checks.
- Not adding short flag aliases or argument groups/subparsers.
- Not refactoring `parse_args`, `main`, or `init_new_package` beyond the additive
  changes (CLAUDE.md §3 Surgical Changes).

## Open Risks

- **Unused-parameter lint**: the five new `init_new_package` params are not yet
  consumed. If Ruff's `ARG` rules are enabled in `pyproject.toml`, they may flag;
  confirm during implementation and, if so, prefer a minimal acknowledgement over
  disabling the rule. (Check `pyproject.toml` rather than assuming.)
- **Email/URL regex strictness**: too-strict patterns reject valid inputs;
  too-loose defeats the purpose. Bias permissive (Decision 4/5) and cover both
  accept and reject cases in tests.
- **`main` test fan-out**: existing `main` tests assert the exact
  `init_new_package` call signature (`test_main.py:167-177`); adding kwargs will
  require updating those assertions, not just adding new ones.
