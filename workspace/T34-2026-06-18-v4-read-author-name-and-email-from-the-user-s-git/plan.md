# Implementation Plan

## Overview

Add git config (`user.name` / `user.email`) as a fourth, weakest default source
for `author_name` and `author_email` only, establishing precedence
**flag > env > git config > None**. A single module-private helper
`_git_config_default(key)` reads effective `git config <key>` via
`subprocess.run(check=False, ...)` and degrades silently to `None`; two
`if X is None:` fallback blocks in `parse_args()` wire it in after the existing
env-fallback block. No downstream consumption, no new validators.

All changes are confined to `modernpackage/main.py` and `tests/test_main.py`.

---

## Phase 1: `_git_config_default` helper + constants

Add the git-config reader and its two key constants. The helper returns the
trimmed value of `git config <key>`, or `None` when git is missing, the key is
unset, output is empty, or the command exits non-zero — never raising. This is
the full external-boundary slice (subprocess call + graceful degradation),
verifiable in isolation before any wiring.

### Changes

#### 1. Add `run` to the subprocess import
**File**: `modernpackage/main.py`
**Action**: modify (line 8)

The module currently imports `from subprocess import PIPE, Popen`. Add `run`.
No other `run` symbol exists in the module (confirmed against research /
Open Risks "run import collision"), so there is no collision.

```python
from subprocess import PIPE, Popen, run
```

#### 2. Add the two git-config key constants
**File**: `modernpackage/main.py`
**Action**: modify (after the `_ENV` constants, currently ending at line 90)

Mirror the `_ENV` constant style (UPPER_SNAKE, `_`-prefixed, explicitly
annotated). Add directly after `_REPOSITORY_URL_ENV` (line 90):

```python
# Git config keys consulted as the weakest metadata default for author name /
# email when the matching flag and env var are both absent
# (precedence: flag > env > git config > None).
_GIT_CONFIG_USER_NAME_KEY: str = 'user.name'
_GIT_CONFIG_USER_EMAIL_KEY: str = 'user.email'
```

#### 3. Add the `_git_config_default` helper
**File**: `modernpackage/main.py`
**Action**: modify (add a new module-private helper next to `_environment_default`,
currently lines 158-160)

Modeled on `_environment_default`: one job, `str | None`, fully annotated,
empty output treated as unset (`value or None`). Uses
`subprocess.run(check=False, capture_output=True, text=True)` per the project's
boundary policy (Code Best Practices; `test_e2e.py:37-49`) rather than `Popen`.
Wrap in `try/except FileNotFoundError` to handle missing git silently (design
Decision 4). Apply `# noqa: S603 S607` matching the other subprocess calls
(`main.py:272-273`, `309`).

```python
def _git_config_default(key: str) -> str | None:
    """Return the effective `git config <key>` value, or None.

    Reads the merged (local-over-global) git config the way a commit would
    resolve it (design Decision 6). Degrades silently to None — never raises —
    when git is missing, the key is unset (git exits 1), the value is empty, or
    the command otherwise fails. An absent git default is expected, not an
    error, so no notice is printed (design Decision 4).
    """
    try:
        result = run(  # noqa: S603
            ['git', 'config', key],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
```

### Verification
#### Automated
- [x] `just check` passes (runs check-format, check-lint, check-complexity,
      check-typecheck, test, audit)
- [x] `just test` passes
- [x] New unit tests for `_git_config_default` pass — add to `tests/test_main.py`,
      importing the helper: add `_git_config_default` to the
      `from modernpackage.main import (...)` block (lines 8-17). Patch the
      subprocess seam on the module object (`patch('modernpackage.main.run')`),
      cover four cases:

```python
def test_git_config_default_returns_trimmed_value() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stdout='Ada Lovelace\n')
        assert _git_config_default('user.name') == 'Ada Lovelace'


def test_git_config_default_returns_none_when_key_unset() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=1, stdout='')
        assert _git_config_default('user.name') is None


def test_git_config_default_treats_empty_value_as_none() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stdout='\n')
        assert _git_config_default('user.email') is None


def test_git_config_default_returns_none_when_git_missing() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.side_effect = FileNotFoundError('git not found')
        assert _git_config_default('user.name') is None
```

#### Manual
- [x] Helper is not yet called by any production path; safe to stop here. Confirm
      the missing-git path never raises:
      `cd /home/niekas/tools/modernpackage && uv run python -c "from unittest.mock import patch; import modernpackage.main as m; patch('modernpackage.main.run', side_effect=FileNotFoundError).start(); print(m._git_config_default('user.name'))"`
      → prints `None` with no traceback.
- [x] `uv run python -c "import modernpackage.main as m; print(m._GIT_CONFIG_USER_NAME_KEY, m._GIT_CONFIG_USER_EMAIL_KEY)"`
      → prints `user.name user.email`.

---

## Phase 2: Wire git-config fallback into `parse_args()` precedence ladder

Consume the Phase 1 helper so omitted `--author-name` / `--author-email` with
unset env vars resolve from git config, while flag and env still win. The
git-config email reaches the existing `_validated_or_error` seam unchanged.

### Changes

#### 1. Add two git-config fallback guards in `parse_args()`
**File**: `modernpackage/main.py`
**Action**: modify (insert after the env-fallback block at line 245, before the
`_validated_or_error` calls at line 246)

Mirror the env-fallback `if X is None:` shape (design Decision 2). The guards run
only for fields still `None` after the flag and env layers, preserving precedence
**flag > env > git config > None**. Only `author_name` and `author_email` get
the git-config source (design Decision 1); `description`, `license`,
`repository_url` are untouched.

```python
    if arguments.author_name is None:
        arguments.author_name = _git_config_default(_GIT_CONFIG_USER_NAME_KEY)
    if arguments.author_email is None:
        arguments.author_email = _git_config_default(_GIT_CONFIG_USER_EMAIL_KEY)
```

Resulting order in `parse_args()`:
1. `arguments = parser.parse_args()` (line 235) — flags win
2. env-fallback block (lines 236-245) — env fills remaining `None`s
3. **new** git-config block (above) — git config fills remaining `None`s for the
   two author fields
4. `_validated_or_error(...)` for `author_email` and `repository_url`
   (lines 246-251) — now also validates git-config-sourced emails (Decision 7)

No change to the `_validated_or_error` block: a git-config email flows through it
exactly like an env email. Author name stays unvalidated (no
`validate_author_name` exists; design Decision 8).

### Verification
#### Automated
- [x] `just check` passes
- [x] `just test` passes
- [x] New `parse_args()` precedence tests pass — add to `tests/test_main.py`.
      Patch `sys.argv` to a bare invocation, `delenv` the author env vars via
      `monkeypatch`, and patch `_git_config_default` on the module object. Cover
      the full ladder:

```python
def test_parse_args_flag_beats_git_config(monkeypatch) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg', '--author-name', 'Flag Name']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.return_value = 'Git Name'
        arguments = parse_args()
    assert arguments.author_name == 'Flag Name'
    # name was never None after the flag, so git config is not consulted for it
    assert _GIT_CONFIG_USER_NAME_KEY not in [
        call.args[0] for call in git_mock.call_args_list
    ]


def test_parse_args_env_beats_git_config(monkeypatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_NAME', 'Env Name')
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.return_value = 'Git Name'
        arguments = parse_args()
    assert arguments.author_name == 'Env Name'
    assert _GIT_CONFIG_USER_NAME_KEY not in [
        call.args[0] for call in git_mock.call_args_list
    ]


def test_parse_args_git_config_fills_when_flag_and_env_absent(monkeypatch) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: {
            _GIT_CONFIG_USER_NAME_KEY: 'Ada Lovelace',
            _GIT_CONFIG_USER_EMAIL_KEY: 'ada@example.com',
        }[key]
        arguments = parse_args()
    assert arguments.author_name == 'Ada Lovelace'
    assert arguments.author_email == 'ada@example.com'


def test_parse_args_all_sources_absent_stays_none(monkeypatch) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.return_value = None
        arguments = parse_args()
    assert arguments.author_name is None
    assert arguments.author_email is None


def test_parse_args_malformed_git_config_email_exits_two(monkeypatch) -> None:
    # Documents design Decision 7 / Open Risk: a malformed git-config email
    # flows through _validated_or_error and aborts the run with exit code 2.
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: (
            'bad' if key == _GIT_CONFIG_USER_EMAIL_KEY else None
        )
        with pytest.raises(SystemExit) as exit_info:
            parse_args()
    assert exit_info.value.code == 2
```

Add `_GIT_CONFIG_USER_NAME_KEY` and `_GIT_CONFIG_USER_EMAIL_KEY` to the
`from modernpackage.main import (...)` block alongside `_git_config_default`.

#### Manual
- [x] All five precedence scenarios above encode their expected behavior as
      assertions — run `just test` and confirm the five `test_parse_args_*`
      cases (plus the four Phase 1 helper cases) appear in the passing output:
      `cd /home/niekas/tools/modernpackage && just test 2>&1 | grep -c 'test_parse_args_\(flag_beats\|env_beats\|git_config_fills\|all_sources\|malformed\)'`
      → no human inspection needed.
- [x] Confirm git-config fallback is live end-to-end with a real (mocked) git
      identity and no flags/env:
      `cd /home/niekas/tools/modernpackage && uv run python -c "from unittest.mock import patch; import os; [os.environ.pop(v, None) for v in ('MODERNPACKAGE_AUTHOR_NAME','MODERNPACKAGE_AUTHOR_EMAIL')]; import modernpackage.main as m; patch('modernpackage.main._git_config_default', side_effect=lambda k: {'user.name':'Ada','user.email':'ada@example.com'}[k]).start(); patch('sys.argv', ['modernpackage','pkg']).start(); a=m.parse_args(); print(a.author_name, a.author_email)"`
      → prints `Ada ada@example.com`.

---

## Testing Checkpoints

- **After Phase 1**: `_git_config_default` exists and is fully unit-tested for
  value / unset / empty / missing-git. `run` is imported, `just check`
  (lint+typecheck+test+audit) and `just test` pass. The helper is not yet called
  by any production path — safe to stop here with a working, tested boundary
  reader.
- **After Phase 2**: `parse_args()` resolves `author_name` / `author_email` with
  precedence **flag > env > git config > None**; only these two fields gain the
  git-config source. Git-config email is validated through the existing seam;
  malformed email exits 2. `just check` and `just test` pass. No downstream
  consumption added — `init_new_package` still `del`s the values (out of scope,
  deferred V4 work).

## Implementation Notes (deviations from plan)

**Phase 2 test adaptations:**
1. `test_parse_args_flag_beats_git_config` and `test_parse_args_env_beats_git_config`:
   plan used `git_mock.return_value = 'Git Name'` for all calls, but 'Git Name' is not
   a valid email and flows into `_validated_or_error` for `author_email` (which is None
   after flag/env), causing SystemExit(2). Fixed: use `side_effect` returning 'Git Name'
   for `user.name` and `None` for `user.email` — preserves the test's intent while
   avoiding the unintended email validation failure.
2. `test_main_with_package_name`: patches `ArgumentParser` but not `_git_config_default`,
   so real git config values ('Albertas Gimbutas' / email) leaked into the call assertion.
   Fixed: added `patch('modernpackage.main._git_config_default', return_value=None)`.
3. `test_parse_args_metadata_defaults_none`: already clear env vars but did not patch
   `_git_config_default`; real git config would cause `author_name`/`author_email` to be
   non-None after Phase 2. Fixed: added
   `patch('modernpackage.main._git_config_default', return_value=None)`.

---

## Notes / Assumptions

- **Line/complexity gates**: research reads `pyproject.toml` as ruff
  line-length 88, mccabe max-complexity 8 (Q6). The added helper and guards are
  well within both — the helper is a single linear function and adds no branching
  to `parse_args()` beyond two flat `if` guards. Defer to `pyproject.toml` as the
  source of truth; `just check-complexity` and `just check-format` enforce it.
- **Malformed git-config email aborts the run** (design Decision 7 / Open Risk):
  chosen behavior is to validate git-config emails through the existing seam,
  exiting 2 on failure — same as env emails. `test_parse_args_malformed_git_config_email_exits_two`
  documents this deliberately.
- **e2e unaffected**: `test_e2e.py` sets `GIT_AUTHOR_*` env, not
  `git config user.*`, so `_git_config_default` reads nothing new there
  (design Open Risks). No `test_e2e.py` changes.
