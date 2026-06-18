# Research Findings

Scope: `modernpackage/main.py` (the questions say `main.py`; the actual file is
`modernpackage/main.py` — `modernpackage/__init__.py` holds only `__version__`).
All findings come from direct reads of `main.py`, `Justfile`, `tests/test_main.py`,
`tests/test_e2e.py`, `modernpackage/__init__.py`.

## Q1: End of `init_new_package` — stdout vs stderr, order, return codes

### Findings
- Flow tail spans `main.py:700-762`. Three subprocesses run in order: `git clone`
  (`main.py:700-705`), `just init` (`main.py:725-731`), `just check`
  (`main.py:745-751`). All three use `Popen(... stdin=PIPE, stdout=PIPE, stderr=PIPE)`.
- `git clone` failure: decodes/strips stderr, raises `RuntimeError`
  (`main.py:709-713`); message = friendly + `\n\n` + raw when `humanize_git_clone_error`
  matches, else raw only. No print here.
- `just init` not installed: `FileNotFoundError` → `RuntimeError` with install hint
  (`main.py:732-737`).
- `just init` non-zero: raises `RuntimeError` `f'just init failed with exit code {...}: {stderr_text}'`
  (`main.py:741-743`). No print.
- `just check` (`main.py:745-752`): `pipe.communicate()` is called with **no capture
  into variables** — the child's stdout/stderr (piped) are discarded, not forwarded.
- Success branch (`main.py:754-756`): prints to **stdout** `f'just check passed — {module_name} scaffold is valid.'`, returns `0`.
- Failure branch (`main.py:757-762`): prints to **stderr** (`file=sys.stderr`)
  `f'just check failed with exit code {pipe.returncode} — review the output in {module_name}.'`,
  returns `1`.
- Earlier stdout output (always before the above): the preflight checklist printed
  by `_run_preflight_checks` (`main.py:662-669`), and, only in dry-run, the plan
  (`main.py:688-698`, returns `0` before any subprocess).
- `RuntimeError`s raised here are caught by `main()` (`main.py:783-785`) which prints
  the error to **stderr** and returns `1`. So overall return codes: `0` success/dry-run,
  `1` on `just check` failure or any caught `RuntimeError`.

## Q2: Derivation of created path, distribution name, module name; locals in success path

### Findings
- `module_name = normalize_module_name(package_name)` — `main.py:683`.
  `normalize_module_name` replaces `.` and `-` with `_`, preserves `_`/case
  (`main.py:199-207`).
- `new_package_path = Path.cwd() / module_name` — `main.py:684`. This is the created
  directory path.
- Distribution/package name is the function parameter `package_name`
  (`main.py:673`); validated as a PEP 508 name upstream by `validate_package_name`
  (`main.py:183-196`). There is **no separate distribution-name local** — the param
  itself carries it.
- Locals available in the success path: `package_name` (param), `module_name`,
  `new_package_path`. Note `package_name` is never used after `module_name` is
  derived; the success summary line uses only `module_name` (`main.py:755`), and the
  directory path lives in `new_package_path` (used as clone target `main.py:701` and
  `cwd=` for both `just` calls `main.py:730, 750`).

## Q3: Version representation and reset to `0.0.1`

### Findings
- Source-of-truth version constant: `__version__ = '0.0.9'` in
  `modernpackage/__init__.py:3`. Imported into `main.py:17` and printed by the
  `--version` path (`main.py:769-770`).
- The reset is performed by `just init`, not by Python. `Justfile:67`:
  `@sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py`
  — a regex that rewrites any `X.Y.Z` to the literal `0.0.1`. This runs **before**
  `mv modernpackage {{package_name}}` (`Justfile:68`), so it targets the still-named
  `modernpackage/__init__.py`.
- `0.0.1` is a **hardcoded string literal** in the dry-run formatter:
  `'  run just init: reset version to 0.0.1'` (`main.py:555`). It is not derived from
  any constant and is not linked to the `Justfile` sed value programmatically.
- Test references to `0.0.1`: `tests/test_main.py:1360` asserts `'0.0.1' in plan`;
  `tests/test_e2e.py:90` asserts the scaffolded `__init__.py` contains `0.0.1` after a
  real `just init`.

## Q4: Conventions of user-facing output blocks (dry-run plan, preflight checklist)

### Findings
- **Formatter vs printer split** for the dry-run plan:
  - `_format_dry_run_plan(...) -> str` builds the multi-line string (`main.py:520-556`).
  - `_print_dry_run_plan(...)` wraps it and calls `print(...)` to stdout
    (`main.py:559-580`).
- The preflight checklist has a **line formatter** but no whole-block formatter:
  - `_format_check_line(label, *, ok) -> str` returns one line (`main.py:514-517`).
  - `_run_preflight_checks` prints the header then prints each formatted line as
    checks run (`main.py:643-669`) — printing is interleaved with execution, so no
    pure formatter for the entire checklist.
- **Headers as module constants**: `_PREFLIGHT_HEADER = 'Preflight checks:'` and
  `_DRY_RUN_HEADER = 'Dry run — no changes will be made:'` (`main.py:510-511`).
- **Indentation patterns**:
  - Check line: `f'  {marker:<6} {label}'` — 2-space indent, marker left-padded to 6
    chars so labels align; markers are `'[ok]'` / `'[FAIL]'` (`main.py:515-517`).
  - Dry-run plan: top-level actions indented 2 spaces (`'  clone ...'`,
    `'  update pyproject.toml metadata:'`, `'  run just init: ...'`), nested metadata
    fields indented 4 spaces (`f'    {label}: ...'`) (`main.py:544-555`).
  - None metadata fields render as `'    {label}: keeps template default'`
    (`main.py:550-553`).
- Both `print` calls carry `# noqa: T201` (the repo lints against bare prints; output
  helpers are the sanctioned exceptions).
- `_print_dry_run_plan`'s docstring cites "output convention, main.py:592"
  (`main.py:569`) — a stale line reference, but it documents the formatter/printer
  convention intent.

## Q5: Test capture/assertion of stdout/stderr and subprocess mocking patterns

### Findings
- **Two seams are patched on the module object**: `modernpackage.main.Popen` (the
  `git clone` / `just init` / `just check` calls) and `modernpackage.main.run`
  (the `git ls-remote` reachability probe and `git config` reads). Example:
  `tests/test_main.py:287-294`.
- **Uniform success setup**: `run_mock.return_value = MagicMock(returncode=0, stderr='')`,
  `popen_mock.return_value.returncode = 0`,
  `popen_mock.return_value.communicate.return_value = (b'', b'')`
  (`tests/test_main.py:291-293`). `communicate` returns a `(stdout, stderr)` bytes
  tuple because `init_new_package` does `stderr.decode()` (`main.py:707, 739`).
- **Per-call distinct results** use `popen_mock.side_effect = [mock1, mock2, ...]` with
  individually configured `MagicMock`s — e.g. clone ok / init ok / check fail
  (`tests/test_main.py:671-687`), or clone ok then `FileNotFoundError` for missing
  `just` (`tests/test_main.py:347-352`).
- **Call-count / argument assertions**: `popen_mock.call_count` (3 on full success,
  `tests/test_main.py:295`; `0` when preflight aborts, e.g. `:386, :443, :724`);
  `popen_mock.call_args_list[n].args[0]` / `.kwargs['cwd']` to assert exact argv and
  cwd (`tests/test_main.py:308-314, 326-328`).
- **stdout/stderr assertion — two styles**:
  - `capsys` fixture: `capsys.readouterr().out` / `.err`, with ordering checked via
    `out.index(line)` and `sorted(indices)` (`tests/test_main.py:644-668`,
    `727-769`).
  - `patch('modernpackage.main.print')` then inspect `print_mock.call_args` /
    `call_args_list` stringified (`tests/test_main.py:548-559, 629-641, 671-692`).
- **`shutil.which` patched** for the required-tools preflight, via `side_effect`
  function returning `None` for the "missing" tool (`tests/test_main.py:374-386`),
  or `return_value='/usr/bin/tool'` for all present (`:419-424`).
- **Dry-run** asserts no subprocess (`popen_mock.call_count == 0`) and plan text in
  `capsys` out (`tests/test_main.py:1297-1306, 1363-1376`).
- **`tests/test_e2e.py`** does NOT call `init_new_package`; it replicates the
  `git clone` (from local `REPO_ROOT`) + `just init` + `just check` flow with real
  `subprocess.run(..., check=False, capture_output=True, text=True)` (`:38-50`),
  guarded by `shutil.which` skips (`:55-57`) and the `@pytest.mark.e2e` marker
  (`:53`). It asserts via `CompletedProcess.returncode` and `.stdout`/`.stderr`
  (`:64, 80, 93`), not via captured prints, and checks generated files directly
  (`:88-103`).

## Cross-Cutting Observations
- Output convention throughout: success/informational text → stdout via `print`;
  failures either raise `RuntimeError` (surfaced to stderr by `main`, `main.py:784`)
  or print directly to `sys.stderr` (the `just check` failure line, `main.py:757-761`,
  and config-file notices, `main.py:290-293, 454-457`).
- The post-`just check` step is the only place an informational summary is printed
  from `init_new_package` itself, and it currently reports only `module_name`
  (`main.py:755`) — `new_package_path` is computed (`main.py:684`) but not surfaced in
  that line.
- `module_name` (not raw `package_name`) is the value threaded into all user-facing
  strings: dry-run rename/clone lines (`main.py:546, 554`) and the check-passed line
  (`main.py:755`).

## Open Areas
- `_print_dry_run_plan` docstring references `main.py:592` (`main.py:569`), which does
  not correspond to a current line — a stale comment, not behavior.
- No test asserts the exact text/path content of a success summary beyond
  `'just check passed'` substring (`tests/test_main.py:640`); there is currently no
  assertion that the created directory path is printed on success.
