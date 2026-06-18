# Research Findings

All behavior lives in one module, `modernpackage/main.py`, exercised by
`tests/test_main.py`. References below are `file:line`.

## Q1: Pre-scaffolding verification functions & invocation order

### Findings
- Three preflight functions are defined, plus the argparse-time name/email/URL
  validators that run earlier during `parse_args`.
- **Tool availability** — `_verify_required_tools()` (`main.py:484-493`): builds
  `missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]`
  (`main.py:486`); raises if any of `git`, `just`, `uv` is absent from PATH.
- **Target directory** — `_verify_target_directory_absent(target_path)`
  (`main.py:496-503`): raises if `target_path.exists()` (`main.py:498`).
- **Template remote reachability** — `_verify_template_remote_reachable()`
  (`main.py:506-539`): runs `git ls-remote <url>` with a timeout
  (`main.py:515-521`); raises on `TimeoutExpired` or non-zero return code.
- **Name validation** — `validate_package_name(value)` (`main.py:173-186`) runs
  at parse time as the `type=` of the positional arg (`main.py:351`), not inside
  `init_new_package`. Also `validate_author_email` (`main.py:200-205`),
  `validate_repository_url` (`main.py:208-213`).
- **Order inside `init_new_package`** (`main.py:555-557`), all before any
  `Popen`:
  1. `_verify_required_tools()`
  2. `_verify_target_directory_absent(new_package_path)`
  3. `_verify_template_remote_reachable()`
  - `new_package_path = Path.cwd() / module_name` where `module_name =
    normalize_module_name(package_name)` (`main.py:552-553`).

## Q2: How each verification reports success/failure

### Findings
- All three preflight functions return `None` on success and raise
  `RuntimeError` on failure (no booleans, no return values).
- `_verify_required_tools` message (`main.py:488-492`): `'required tool(s) not
  found on PATH: {", ".join(missing)} — install the missing tool(s) before
  scaffolding. See https://github.com/casey/just#installation'`.
- `_verify_target_directory_absent` message (`main.py:499-502`): `'target
  directory already exists: {target_path} — choose a different package name or
  remove the existing directory'`.
- `_verify_template_remote_reachable`:
  - Timeout branch (`main.py:522-529`): friendly `'repository unreachable —
    check your network connection'` + `\n\n` + raw `'template remote unreachable
    (git ls-remote timed out after {N}s)'`, raised `from error`.
  - Non-zero branch (`main.py:531-539`): raw `'template remote unreachable (git
    ls-remote exit code {rc}): {stderr_text}'`; if `humanize_git_clone_error`
    returns a friendly string it is prepended as `f'{friendly}\n\n{raw}'`,
    otherwise just `raw`.
- `humanize_git_clone_error(stderr_text)` (`main.py:68-74`): lowercases input,
  returns the first matching friendly message from `_GIT_CLONE_ERROR_MESSAGES`
  (`main.py:20-52`), else `None`. Five ordered categories: network, repo-not-
  found, auth, destination-exists, filesystem-permission.
- The argparse validators raise `ArgumentTypeError` (`main.py:178, 185, 204,
  211`); via `parser.error` / argparse this becomes `SystemExit` code 2.

## Q3: User-facing output conventions & formatting dependencies

### Findings
- Output is via the builtin `print`; every call carries a `# noqa: T201` marker
  (ruff `flake8-print`): `main.py:280, 438, 614, 616, 629, 642`. No logging
  module, no Rich/Click/colorama.
- **stdout** (default `print`) for success: `'just check passed …'`
  (`main.py:614`) and `'modernpackage {__version__}'` (`main.py:629`).
- **stderr** (`file=sys.stderr`) for failures/notices: malformed config notice
  (`main.py:280-283`), missing pyproject notice (`main.py:438-441`), `just check
  failed …` (`main.py:616-620`), and the top-level error print in `main`
  (`main.py:642`).
- No styling/ANSI codes in Python output. (The only ANSI color is in the
  `Justfile:73` shell `echo`, not in the module.)
- **Dependencies**: runtime `dependencies = []` (`pyproject.toml:18`);
  `requirements.txt` is empty (`requirements.txt:1-2`). Optional `test` extras
  (`pyproject.toml:28-37`): ruff, mypy, pip-audit, deadcode, pytest, pytest-cov,
  pytest-xdist, vupi — no output/formatting library available.
- Module imports are stdlib only (`main.py:1-15`): os, re, shutil, sys,
  tomllib, argparse, dataclasses, pathlib, subprocess, typing.

## Q4: End-of-run success/failure messaging & exit codes

### Findings
- `init_new_package` ends by running `just check` via `Popen` in the new package
  dir (`main.py:604-611`), then branches on `pipe.returncode`:
  - `== 0`: prints `f'just check passed — {module_name} scaffold is valid.'` to
    stdout and `return 0` (`main.py:613-615`).
  - else: prints `f'just check failed with exit code {rc} — review the output in
    {module_name}.'` to stderr and `return 1` (`main.py:616-621`).
- Earlier failures inside `init_new_package` raise `RuntimeError` rather than
  returning: git clone non-zero (`main.py:568-572`), `just` not found
  (`main.py:591-596`), `just init` non-zero (`main.py:600-602`).
- `main()` (`main.py:624-645`) derives the process exit code:
  - `--version`: prints version, falls through to `return 0` (`main.py:628-629,
    645`).
  - package name given: returns whatever `init_new_package` returns
    (`main.py:633-640`); wraps it in `try/except RuntimeError` which prints the
    error to stderr and `return 1` (`main.py:641-643`).
  - no args: `return 0` (`main.py:645`).
- `just check` recipe definition: `Justfile:52` = `check-format check-lint
  check-complexity check-typecheck test audit`.

## Q5: How `tests/test_main.py` tests verification & captured output

### Findings
- **Imports / seams**: private functions imported directly from
  `modernpackage.main` (`test_main.py:10-30`), including `_REQUIRED_TOOLS`,
  `_verify_required_tools`, `_verify_target_directory_absent`,
  `_verify_template_remote_reachable`.
- **Patching seams** (always on the module object `modernpackage.main.*`):
  - `shutil.which` patched with `side_effect` per-tool (`test_main.py:378, 389,
    404, 419, 431`).
  - `run` (the `git ls-remote` / git-config seam) patched and given
    `MagicMock(returncode=0, stderr='')` (`test_main.py:290, 335, 382, …`).
  - `Popen` patched to assert it was never reached when preflight fails:
    `assert popen_mock.call_count == 0` (`test_main.py:385, 400, 415, 442, 637,
    1087`).
- **Tool checks**: `test_verify_required_tools_missing_{git,just,uv}`
  (`test_main.py:373-415`), `_all_present` asserts `which_mock.call_count ==
  len(_REQUIRED_TOOLS)` (`test_main.py:418-423`), `_reports_all_missing`
  (`test_main.py:426-442`).
- **Directory check**: unit tests `test_verify_target_directory_absent_*`
  (`test_main.py:1107-1116`) use `tmp_path`; integration tests
  `test_init_new_package_aborts_when_target_directory_exists` /
  `_proceeds_when…absent` use `monkeypatch.chdir(tmp_path)` (`test_main.py:1074-
  1104`).
- **Remote reachability**: `test_verify_template_remote_reachable_*`
  (`test_main.py:1119-1158`) mock `run.return_value` with various return codes
  / stderr, and `run.side_effect = TimeoutExpired(...)` for the timeout case
  (`test_main.py:1152`). `test_init_new_package_aborts_when_remote_unreachable`
  (`test_main.py:627-637`).
- **Captured console output**: two mechanisms —
  - `patch('modernpackage.main.print')` then inspect `print_mock.call_args_list`
    / `call_args.args[0]` (`test_main.py:36, 489, 572, 597`; assertions at
    `499, 579-581, 602-605`).
  - pytest `capsys` fixture reading `.out` / `.err`
    (`test_main.py:209, 277, 941, 950, 960`).
- **Assertion patterns**: `pytest.raises(RuntimeError, match=…)` for preflight
  failures; `pytest.raises(SystemExit)` + `excinfo.value.code == 2` for argparse
  validation (`test_main.py:208, 222, 752, 917, 926`).
- e2e/real tests are split into `tests/test_e2e.py` under the `e2e` marker;
  default run excludes them (`pyproject.toml:40` `-m 'not e2e'`).

## Q6: Where check constants/data are declared & referenced

### Findings
- `_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')` (`main.py:56`);
  referenced in `_verify_required_tools` (`main.py:486`) and asserted in tests
  (`test_main.py:423`).
- `_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'`
  (`main.py:61`); used by the reachability probe (`main.py:516`), the clone
  (`main.py:560`), and metadata replacement (`main.py:456`).
- `_REMOTE_REACHABILITY_TIMEOUT_SECONDS: int = 10` (`main.py:65`); passed as
  `timeout=` (`main.py:520`) and interpolated into the timeout message
  (`main.py:526`).
- `_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern, str]]` (`main.py:20-52`),
  ordered most-specific-first; consumed by `humanize_git_clone_error`
  (`main.py:71`).
- Regex/validation constants: `_PACKAGE_NAME_RE` (`main.py:79`),
  `_DISALLOWED_CHAR_RE` (`main.py:86`), `_STDLIB_MODULE_NAMES =
  sys.stdlib_module_names` (`main.py:91`), `_EMAIL_RE` (`main.py:95`),
  `_REPOSITORY_URL_RE` (`main.py:98`).
- Metadata-default constants (env var names, git keys, config paths) declared
  `main.py:102-148`, driving `_METADATA_FIELDS` and `_resolve_metadata_defaults`
  — adjacent to but separate from the preflight checks.

## Cross-Cutting Observations
- Two distinct failure idioms: **preflight/internal invariants raise
  `RuntimeError`** (caught in `main`, `main.py:641`); **external boundaries
  degrade gracefully** — `subprocess.run(..., check=False, capture_output=True,
  text=True)` then inspect `returncode` (git config `main.py:231-241`, ls-remote
  `main.py:515-521`), returning `None` or printing a `[stderr]` notice instead
  of raising. Matches CLAUDE.md / Code Best Practices error-handling guidance.
- Friendly+raw message composition (`f'{friendly}\n\n{raw}'`) is reused in three
  places: ls-remote (`main.py:528, 538`) and git clone (`main.py:571`).
- Module-private (`_`-prefixed) symbols are tested by direct import, per the
  documented convention; no re-export hub.
- `# noqa: T201` on every `print`, `# noqa: S603/S607` on every subprocess call —
  consistent suppression markers.

## Open Areas
- No existing "preflight checklist" / summary-of-checks emitter exists today;
  checks run imperatively and only emit output on failure (raise) — there is no
  function that prints the full set of checks/environment as a checklist. The
  questions reference such a concept but the codebase contains only the
  individual verifiers described above.
- `requirements.txt` is empty (only the autogen header); the lock of runtime
  deps is effectively "none" (`requirements.txt:1-2`, `pyproject.toml:18`).
