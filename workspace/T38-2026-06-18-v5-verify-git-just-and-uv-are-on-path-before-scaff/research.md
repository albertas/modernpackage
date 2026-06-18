# Research Findings

Scope: `modernpackage/main.py`, `tests/test_main.py`, `tests/test_e2e.py`,
`Justfile`. All references are to the local committed checkout.

## Q1: Scaffolding control flow in `init_new_package` and `main`

### Findings
- Entry point declared in `pyproject.toml:23-24`
  (`modernpackage = "modernpackage.main:main"`).
- `main` (`main.py:548-569`): calls `parse_args()` (550); `--version` prints and
  returns 0 (552-553); otherwise if `package_name` is truthy (555) it calls
  `init_new_package(...)` inside `try/except RuntimeError` (556-567).
- `init_new_package` (`main.py:470-545`) launches **three** subprocesses, all
  via `Popen` (`main.py:10` imports `PIPE, Popen, run`):
  1. **`git clone`** — `main.py:483-488`,
     `['git','clone','https://github.com/albertas/modernpackage', new_package_path]`.
     This is the **first** subprocess and the **first filesystem change**: the
     clone itself *creates* `new_package_path` (computed at `481` from
     `normalize_module_name`, `480`). `communicate()` at 489; failure check 492.
  2. **`just init <module>`** — `main.py:508-514`, `cwd=new_package_path`. Runs
     **after** `_write_package_metadata` (498-505) has already mutated the cloned
     `pyproject.toml`. Wrapped in `try/except FileNotFoundError` (507-520).
     `communicate()` 521; failure check 524.
  3. **`just check`** — `main.py:528-534`, `cwd=new_package_path`. `communicate()`
     535; returncode 0 → print pass, return 0 (537-539); else print fail to
     stderr, return 1 (540-545).
- Order of executables: `git` → `just init` → `just check`. Filesystem timeline:
  clone creates dir → `_write_package_metadata` edits `pyproject.toml`
  (498-505, in-place between the two `just` calls) → `just init` renames/commits
  → `just check` validates.

## Q2: Indirectly-relied-upon external tools (Justfile recipes)

### Findings
- Recipes live in `Justfile` (repo root); the clone carries an identical copy, so
  the cloned package's own `Justfile` is what `just init`/`just check` execute.
- **`just init`** (`Justfile:62-79`) shells out to: `echo`, `uname`, `git grep`,
  `xargs`, `sed` (GNU/BSD branch on `uname`), `sed` (version bump), `mv`, `rm`,
  `git init`, `git add`, `git commit`. So it depends on **git** + standard shell
  utilities (`sed`, `mv`, `rm`, `xargs`, `uname`, `echo`).
- **`just check`** (`Justfile:46`) = `check-format check-lint check-complexity
  check-typecheck test audit`. Each depends on `sync` (`Justfile:8-10`) which runs
  `uv pip sync` + `uv pip install`. Sub-recipes:
  - `check-format`/`check-lint`/`check-complexity` → `uv run ruff ...`
    (`Justfile:25-37`)
  - `check-typecheck` → `uv run mypy ...` (`Justfile:39-40`)
  - `test` → `uv run pytest -n "$(nproc --ignore=1)"` (`Justfile:12-13`)
  - `audit` → `uv run pip-audit` (`Justfile:42-43`)
- Net indirect dependencies of `just check`: **uv**, **ruff**, **mypy**,
  **pytest**, **pip-audit**, plus **nproc**. (`uv` is the launcher for all.)

## Q3: Missing-executable vs non-zero-exit detection and messages

### Findings — `FileNotFoundError` handlers (missing executable)
- `_git_config_default` `main.py:223-224` → returns `None` silently (git absent
  is expected; design Decision noted in docstring 207-215).
- `_load_config_file` `main.py:263-264` → returns `{}` (missing config file).
- `_write_package_metadata` `main.py:423-428` → prints
  `f'No pyproject.toml at {pyproject_path}; skipping metadata.'` to **stderr**,
  returns (no raise).
- `just init` Popen `main.py:515-520` → raises `RuntimeError`:
  `"'just' command not found — install it to initialize the package. See
  https://github.com/casey/just#installation"`.
- **No `FileNotFoundError` handler** wraps `git clone` (`main.py:483`) or
  `just check` (`main.py:528`). A missing `git` or a `just` that vanishes before
  the check would raise an **uncaught** `FileNotFoundError` (not caught by `main`,
  which only catches `RuntimeError`, `main.py:565`).

### Findings — non-zero exit (executable exists, fails)
- `git clone` `main.py:492-496`: builds
  `f'git clone failed with exit code {pipe.returncode}: {stderr_text}'` (493),
  optionally prefixed by a friendly line as `f'{friendly}\n\n{raw}'` (495), then
  `raise RuntimeError(message)`.
- `_git_config_default` `main.py:225-226`: `returncode != 0` → `None`.
- `just init` `main.py:524-526`:
  `raise RuntimeError(f'just init failed with exit code {pipe.returncode}: {stderr_text}')`.
- `just check` `main.py:537-545`: returncode 0 → `print(f'just check passed —
  {module_name} scaffold is valid.')` (stdout, 538) return 0; else
  `print(f'just check failed with exit code {pipe.returncode} — review the output
  in {module_name}.', file=sys.stderr)` (540-544) return 1.

### Findings — RuntimeError raises and exit-code paths
- RuntimeError raised at `main.py:496`, `520`, `526`. All caught by `main`
  `565-567`, which prints the error to stderr (566) and returns 1.
- `init_new_package` returns: `0` (539), `1` (545). `main` returns: `0`
  (version/no-arg/`init` success), `1` (`init` returned 1, or RuntimeError, 567).

## Q4: Conventions for user-facing error/notice messages

### Findings
- **Humanization**: `humanize_git_clone_error` (`main.py:54-60`) matches lowercased
  stderr against the ordered regex table `_GIT_CLONE_ERROR_MESSAGES`
  (`main.py:19-51`), "most-specific-first" so a precise pattern wins (comment 18).
  Returns `None` when unrecognized; raw text is always preserved and appended
  (`main.py:495`).
- **Wording style**: short lowercase phrases joined by an em-dash, e.g.
  `'repository unreachable — check your network connection'` (`main.py:26`),
  `'authentication failed — check your git credentials or access rights'` (39).
  Validators use `{value!r}` repr + em-dash, e.g.
  `f'Invalid author email: {value!r} — expected name@domain.tld'` (`main.py:189`).
- **stderr vs stdout**: success/informational → stdout (`just check passed` 538,
  version 553). Errors/notices → stderr (`file=sys.stderr` at 268, 426, 544, 566).
- **raise vs print**: hard scaffolding failures `raise RuntimeError` (git clone,
  just init, just-missing) and bubble to `main`'s handler; `just check` failure is
  non-fatal → print + return 1 (540-545); boundary/optional inputs (git config,
  config file, missing pyproject) **degrade silently or with a notice**, never
  raise (`main.py:207-228`, `249-271`, `421-428`). Matches `CLAUDE.md` /
  CODE_BEST_PRACTICES "raise loudly on invariants, degrade at boundaries".
- Messages are defined inline in each function plus the module-level
  `_GIT_CLONE_ERROR_MESSAGES` table (`main.py:19-51`).

## Q5: How tests mock/stub subprocess and assert behavior

### Findings — `Popen` (in `tests/test_main.py`)
- Uniform success: `patch('modernpackage.main.Popen')`,
  `popen_mock.return_value.returncode = 0`,
  `popen_mock.return_value.communicate.return_value = (b'', b'')`
  (`test_main.py:281-285`, also 289-291, 304-306, 472-474).
- Per-call distinct behavior via `popen_mock.side_effect = [mockA, mockB, ...]`
  where each is a `MagicMock` with `.returncode` and
  `.communicate.return_value` set (`test_main.py:331-339`, 481-495).
- Injecting a missing executable: put `FileNotFoundError(...)` in the
  `side_effect` list (`test_main.py:325-326`:
  `[git_clone_mock, FileNotFoundError('just not found')]`).
- Assertions on invocation: `popen_mock.call_count == 3` (`285`);
  `popen_mock.call_args_list[i].args[0]` for argv and `.kwargs['cwd']` for cwd
  (`294-300`, 308-310). Clone target read as `call.args[0][-1]` (`295-296`).
- Failure assertions: `pytest.raises(RuntimeError, match=...)` (`317`, 327, 340,
  510); message content checked via `str(exc_info.value)` (`512-515`).
- Print capture: `patch('modernpackage.main.print')` then inspect
  `print_mock.call_args.args[0]` (`397`) or
  `[str(c) for c in print_mock.call_args_list]` (`476-477`, 497-499).

### Findings — `run` (git config) and helpers
- `_git_config_default` tested via `patch('modernpackage.main.run')`:
  `run_mock.return_value = MagicMock(returncode=0, stdout='...')` (`518-521`);
  `run_mock.side_effect = FileNotFoundError('git not found')` for missing git
  (`536-539`).
- Helper patterns (all `_`-prefixed): `_seed_pyproject` (`846-850`),
  `_write_config` (`638-641`), `_parse_args_with_config` (`644-660`). No shared
  Popen fixture — each test constructs its own `MagicMock`s. Built-in
  `tmp_path`/`monkeypatch`/`capsys` fixtures used throughout.
- E2E (`tests/test_e2e.py`) does **not** mock: real `subprocess.run` via `_run`
  wrapper (`38-50`), asserting on `.returncode`/`.stdout`/`.stderr` (`64,80,93`).

## Q6: Existing PATH-presence check (`shutil.which`)

### Findings
- The **only** `shutil.which` usage is in `tests/test_e2e.py`:
  `REQUIRED_TOOLS = ('git', 'just', 'uv')` (`test_e2e.py:28`); loop
  `for tool in REQUIRED_TOOLS: if shutil.which(tool) is None: pytest.skip(...)`
  (`test_e2e.py:55-57`). Confirmed by repo-wide grep — no other occurrence in
  `modernpackage/` or `tests/`.
- **Production code `modernpackage/main.py` has no `shutil` import and no PATH
  check.** Missing-tool detection is purely reactive (via `FileNotFoundError`
  from `Popen`/`run`) and only partial: handled for `just init` (`515`) and git
  config (`223`), but **not** for `git clone` (`483`) or `just check` (`528`).
  `uv` is never invoked directly by `main.py`; it is only reached transitively
  through `just check` recipes (see Q2), so its absence surfaces as a non-zero
  `just check` exit (not a `FileNotFoundError`).

## Cross-Cutting Observations
- Two-tier error philosophy is consistent: invariant failures `raise
  RuntimeError` and are funneled through `main`'s single `except RuntimeError`
  (`main.py:565`); boundary readers (git config, config file, pyproject) degrade
  to `None`/`{}`/notice (`main.py:207-228`, 249-271, 421-428).
- Tool-presence verification currently lives entirely in test code
  (`test_e2e.py:28,55-57`), not in the shipped scaffolding path.
- The `# noqa: S603`/`S607` markers (`main.py:217,483,508,529`) accompany every
  subprocess call, acknowledging the trusted-argv lint exception.

## Open Areas
- No production-side preflight check exists for `git`/`just`/`uv` on PATH; the
  questions reference `shutil.which` but it is only present in the e2e test.
  Whether such a check *should* exist is out of documentation scope.
