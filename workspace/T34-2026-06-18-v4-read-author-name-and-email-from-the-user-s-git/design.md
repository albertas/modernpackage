# Design Discussion

## Current State

Author name/email defaults are resolved entirely in `parse_args()`
(`main.py:177-252`) from **two** sources only — CLI flags and environment
variables — with documented precedence **flag > env > None**
(`main.py:84-85`):

- Flags `--author-name` (`main.py:193-200`) and `--author-email`
  (`main.py:209-217`) register with `default=None`. `--author-email` also has
  `type=validate_author_email` (`main.py:215`).
- After `parser.parse_args()`, each still-`None` field falls back to its env var
  through `_environment_default(...)` (`main.py:236-245`), keyed by the `_ENV`
  constants `_AUTHOR_NAME_ENV` / `_AUTHOR_EMAIL_ENV` (`main.py:86-87`).
- `_environment_default(variable_name)` returns `os.environ.get(name) or None`,
  so set-but-empty is treated as unset (`main.py:158-160`).
- Post-fallback, `author_email` and `repository_url` are re-validated via
  `_validated_or_error(...)` (`main.py:246-251`) so env-sourced values get the
  same validation as flag-sourced ones.

**Git config is read nowhere.** No `git config` invocation exists; the only git
interaction is `git clone` in `init_new_package()` (`main.py:272-277`). The five
resolved metadata fields are threaded into `init_new_package()`
(`main.py:337-344`) and immediately `del`-eted — consumption is deferred V4 work
(`main.py:265-267`).

External commands today use `subprocess.Popen` (`main.py:8`, `272-315`) with
`communicate()`; only `just init` wraps `Popen` in `try/except FileNotFoundError`
(`main.py:287-300`). The e2e test uses the boundary-friendly
`subprocess.run(..., check=False, capture_output=True, text=True)`
(`test_e2e.py:37-49`). `Code Best Practices` prescribes exactly that `run(...)`
form for graceful degradation at external boundaries.

## Desired End State

When `--author-name`/`--author-email` are omitted **and** the matching env var is
unset, fall back to the user's git config (`user.name` / `user.email`). New
precedence: **flag > env > git config > None**, for these two fields only.

Verify correct when:
- A new `_git_config_default(key)` helper returns the trimmed value of
  `git config <key>`, or `None` when git is missing, the key is unset, or the
  command fails — degrading gracefully (never raising).
- In `parse_args()`, after the env-fallback block, `author_name` and
  `author_email` fall back to git config only while still `None`.
- Flag beats env beats git config beats `None` (precedence preserved).
- A git-config-sourced email flows through the existing
  `_validated_or_error(...)` seam (`main.py:246-248`) like env values do.
- Unit tests cover `_git_config_default` (value / unset / missing-git / failure)
  and the full precedence ladder; `just check` and `just test` pass.

## Patterns to Follow

- **Env-fallback shape** (`main.py:236-245`): mirror it with a sibling git-config
  block — `if arguments.author_name is None: arguments.author_name =
  _git_config_default(_GIT_CONFIG_USER_NAME_KEY)`. Same `if X is None:` guard
  style keeps precedence layering obvious.
- **`_environment_default` helper** (`main.py:158-160`): model
  `_git_config_default` on it — module-private (`_` prefix), one job, returns
  `str | None`, fully annotated. Treat empty output as `None` (`value or None`),
  matching the set-but-empty handling.
- **Boundary subprocess pattern** (`Code Best Practices`; `test_e2e.py:37-49`):
  use `subprocess.run(..., check=False, capture_output=True, text=True)`, inspect
  `returncode`, return `None` on non-zero — instead of `Popen`. Wrap in
  `try/except FileNotFoundError` returning `None`, echoing the missing-executable
  handling at `main.py:287-300` (but degrading silently, not raising — git config
  is an ambient default, not a required step).
- **Constant naming** (`main.py:86-90`): add `_GIT_CONFIG_USER_NAME_KEY: str =
  'user.name'` and `_GIT_CONFIG_USER_EMAIL_KEY: str = 'user.email'`, annotated,
  module-private, mirroring the `_ENV` constants.
- **Validation reuse** (`main.py:246-248`): do not add new validation; the
  existing post-fallback `_validated_or_error` seam already covers `author_email`.
- **`# noqa: S603/S607`** on subprocess calls with partial-path executables
  (`main.py:272-273`, `309`): apply the same suppressions to the `git config`
  call.
- **Test seam patching** (`test_main.py:267`): patch the subprocess seam on the
  module object (`modernpackage.main.run`); for precedence tests patch
  `modernpackage.main._git_config_default` directly. Use `monkeypatch` for env
  vars as existing tests do (`test_main.py:159-160`).

Patterns to **avoid**: do not copy the `Popen` + `communicate()` style for this
read — it is heavier than needed and the project's own Best Practices doc steers
boundary reads to `subprocess.run(check=False, ...)`. Do not add a duplicate
inline email validation; reuse `_validated_or_error`.

## Design Decisions

1. **Scope to author_name + author_email only** — the task names exactly these
   two fields. Description / license / repository_url get no git-config source.
2. **Precedence flag > env > git config > None** — git config is the weakest,
   most ambient source, so it fills last (after env). Implemented as a second
   `if X is None:` block right after the env block (`main.py:236-245`).
3. **Use `subprocess.run(check=False, capture_output=True, text=True)`** for the
   read, not `Popen` — matches the documented boundary policy in
   `Code Best Practices` and the e2e helper (`test_e2e.py:37-49`); cleaner than
   `Popen`/`communicate` for a one-shot capture. Adds `run` to the
   `from subprocess import ...` line (`main.py:8`).
4. **Degrade silently to `None`** on missing git, unset key, or non-zero exit —
   `git config` returns exit code 1 when a key is absent, which is normal, not an
   error. No printed notice (unlike `just check`): an absent default is expected,
   not a failure. Catches `FileNotFoundError` for missing git.
5. **Single helper `_git_config_default(key: str) -> str | None`** parameterized
   by key, rather than two name/email-specific helpers — avoids duplication while
   staying minimal. Two key constants name the two call sites.
6. **Read effective (merged) git config** via plain `git config <key>` (no
   `--global`/`--local` flag) — this is the value a commit would actually use and
   the most intuitive "the user's git config". Local repo overrides global, which
   is git's own resolution.
7. **Git-config email validated through the existing seam** — it reaches
   `_validated_or_error` (`main.py:246-248`) like env values. Malformed git
   emails are rare; consistency with env behavior outweighs the edge case (see
   Open Risks).
8. **Author name still unvalidated** — there is no `validate_author_name`
   (`research.md` Q3); git-config names are accepted as-is, matching current
   flag/env behavior. No new validator added.

## What We're NOT Doing

- Not adding a git-config source for description, license, or repository_url.
- Not consuming the resolved metadata downstream — `init_new_package` still
  `del`s the values (`main.py:265-267`); writing into `pyproject.toml` remains
  deferred V4 work.
- Not adding a `validate_author_name` validator.
- Not adding flags to disable the fallback, not caching git output, not
  distinguishing `--global` vs `--local`, not parsing `.gitconfig` files
  directly.
- Not changing the existing `Popen`-based clone/init/check subprocesses.

## Open Risks

- **Malformed git-config email aborts the run** (Decision 7): if a user's
  `user.email` fails `_EMAIL_RE` (`main.py:79`), `_validated_or_error` calls
  `parser.error` (exit 2). Acceptable given how rare malformed git emails are; if
  this proves annoying, a future change could skip an invalid git-config email
  instead of erroring. Flag the chosen behavior in tests.
- **`run` import collision**: confirm no other `run` name exists in `main.py`
  before adding it to the `subprocess` import (none seen in research).
- **Sandbox/CI without git or without configured identity**: helper must return
  `None` cleanly; covered by the missing-git and unset-key test cases. The e2e
  test sets `GIT_*` identity env (`test_e2e.py:29-34`) but those do not populate
  `git config user.*`, so e2e behavior is unaffected.
