# Structure Outline

## Approach

Add git config as a fourth, weakest default source for `author_name` and
`author_email` only, establishing the precedence **flag > env > git config >
None**. Introduce one module-private helper `_git_config_default(key)` that reads
effective `git config <key>` via `subprocess.run(check=False, ...)` and degrades
silently to `None`, then wire two `if X is None:` fallback blocks into
`parse_args()` right after the existing env-fallback block. No downstream
consumption, no new validators, no description/license/repository_url change.

Because the whole change lives in one module and one function, the work splits
into two thin vertical slices: (1) the boundary helper + its constants, fully
unit-testable on its own; (2) wiring it into the precedence ladder, testable via
`parse_args()` end-to-end. Phase 1 is independently valuable (a working,
tested git-config reader) even if Phase 2 never lands.

---

## Phase 1: `_git_config_default` helper + constants

Add the git-config reader and its two key constants. The helper returns the
trimmed value of `git config <key>`, or `None` when git is missing, the key is
unset, output is empty, or the command exits non-zero — never raising. This is
the full external-boundary slice (subprocess call + graceful degradation),
verifiable in isolation before any wiring.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `from subprocess import PIPE, Popen, run` — add `run` to the existing import
  (`main.py:8`); confirm no other `run` symbol collides.
- `_GIT_CONFIG_USER_NAME_KEY: str = 'user.name'` — new module-private constant
  (near the `_ENV` constants, `main.py:86-90`).
- `_GIT_CONFIG_USER_EMAIL_KEY: str = 'user.email'` — new constant.
- `_git_config_default(key: str) -> str | None` — new helper. Calls
  `run(['git', 'config', key], check=False, capture_output=True, text=True)`
  with `# noqa: S603 S607`; returns `result.stdout.strip() or None` when
  `returncode == 0`, else `None`; wraps the call in
  `try/except FileNotFoundError` returning `None`. Modeled on
  `_environment_default` (`main.py:158-160`): one job, `str | None`, annotated,
  empty-output treated as unset.

**Verify**: `just check` and `just test` pass. New unit tests patch the seam on
the module object (`patch.object(modernpackage.main, 'run', ...)`) and assert
four cases:
- value present → `returncode=0`, `stdout='Ada Lovelace\n'` → returns
  `'Ada Lovelace'` (trimmed).
- key unset → `returncode=1`, `stdout=''` → returns `None`.
- empty value → `returncode=0`, `stdout='\n'` → returns `None`.
- missing git → `run` `side_effect=FileNotFoundError` → returns `None` (no raise).

Agent-executable check: `just test` green; additionally
`python -c "from unittest.mock import patch; import modernpackage.main as m;
print(patch.object(m,'run',side_effect=FileNotFoundError).__enter__() or
m._git_config_default('user.name'))"` prints `None` without traceback.

---

## Phase 2: Wire git-config fallback into `parse_args()` precedence ladder

Consume the Phase 1 helper so omitted `--author-name`/`--author-email` with
unset env vars resolve from git config, while flag and env still win. The
git-config email reaches the existing `_validated_or_error` seam unchanged. This
is the user-facing end-to-end slice: running the CLI without flags/env now picks
up the user's git identity.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- In `parse_args()`, immediately after the env-fallback block
  (`main.py:236-245`) and **before** the `_validated_or_error` calls
  (`main.py:246-248`), add two guards mirroring the env shape:
  - `if arguments.author_name is None: arguments.author_name =
    _git_config_default(_GIT_CONFIG_USER_NAME_KEY)`
  - `if arguments.author_email is None: arguments.author_email =
    _git_config_default(_GIT_CONFIG_USER_EMAIL_KEY)`
- No change to validation: the existing
  `_validated_or_error(parser, arguments.author_email, validate_author_email)`
  now also covers git-config emails (Decision 7). Author name stays unvalidated.

**Verify**: `just check` and `just test` pass. New `parse_args()` tests
(`sys.argv` patched to bare `['modernpackage', 'pkg']`, env vars `delenv`'d via
`monkeypatch`, `_git_config_default` patched on the module) assert the full
precedence ladder:
- flag wins: `--author-name X` + git config set → result is `X`,
  `_git_config_default` not consulted for name.
- env beats git config: `MODERNPACKAGE_AUTHOR_NAME` set + git config set →
  result is the env value; `_git_config_default` not called for name.
- git config fills when flag+env absent: both unset, helper returns
  `'Ada Lovelace'` / `'ada@example.com'` → resolved values match.
- all sources absent: helper returns `None` → resolved values stay `None`.
- malformed git-config email (helper returns `'bad'`) flows through
  `_validated_or_error` → `parser.error` / `SystemExit` code 2 (documents
  Decision 7 / Open Risk).

Agent-executable check: `just test` green; the precedence tests above encode
every manual scenario as assertions, no human inspection needed.

---

## Testing Checkpoints

- **After Phase 1**: `_git_config_default` exists and is fully unit-tested for
  value / unset / empty / missing-git. `run` is imported, `just check`
  (lint+typecheck) and `just test` pass. The helper is not yet called by any
  production path — safe to stop here with a working, tested boundary reader.
- **After Phase 2**: `parse_args()` resolves `author_name`/`author_email` with
  precedence **flag > env > git config > None**; only these two fields gain the
  git-config source. Git-config email is validated through the existing seam;
  malformed email exits 2. `just check` and `just test` pass. No downstream
  consumption added (`init_new_package` still `del`s the values — out of scope).

> Note: This design slices cleanly into two phases despite its small size. There
> is no database/API/UI surface — the "layers" here are the external boundary
> (Phase 1: subprocess helper) and the resolution logic (Phase 2: precedence
> wiring). Both phases cross from implementation to test in `main.py` +
> `test_main.py`.
