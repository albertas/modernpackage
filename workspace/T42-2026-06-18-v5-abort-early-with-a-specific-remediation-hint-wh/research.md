# Research Findings

All references are to `modernpackage/main.py` and `tests/test_main.py` unless noted.

## Q1: Preflight check sequence structure, registration, ordering, partial failure

### Findings
- The registry is a `@dataclass(frozen=True) PreflightCheck` with two fields: `label: str` and `run: Callable[[], None]` (`main.py:484-491`). The docstring states the verifier "returns None on success, raises RuntimeError on failure" (`main.py:490-491`).
- Checks are built fresh **per call** inside `_run_preflight_checks(target_path)` as a tuple, not a module-level constant (`main.py:568-579`). The docstring explains this is so `_verify_target_directory_absent` can bind `target_path` via a closure (`main.py:564-566`).
- Run order (fixed by tuple position, `main.py:568-579`):
  1. `package name valid` — `lambda: None` (no-op placeholder; name is already validated at parse time via `validate_package_name`).
  2. `required tools on PATH (git, just, uv)` — `_verify_required_tools`.
  3. `target directory available` — `lambda: _verify_target_directory_absent(target_path)`.
  4. `template remote reachable` — `_verify_template_remote_reachable`.
- Execution loop: prints `_PREFLIGHT_HEADER` ("Preflight checks:", `main.py:494`), then iterates checks. Each `check.run()` is wrapped in `try/except RuntimeError`: on exception it prints a `[FAIL]` line for that check and **re-raises** (`main.py:581-586`); on success it prints an `[ok]` line (`main.py:587`).
- Partial-failure behavior: the failing check's `[FAIL]` line is printed, the exception propagates out of `_run_preflight_checks` immediately, so **no later checks run and no later lines print**. Verified by `test_run_preflight_checks_aborts_on_earlier_check_without_later_lines` (`test_main.py:689-709`) and `test_run_preflight_checks_marks_failing_check_and_aborts` (`test_main.py:667-686`).

## Q2: Each verifier's failure signal and message content

### Findings
All verifiers signal failure by raising `RuntimeError`; success is silent (`return None`).

- **Required tools on PATH** — `_verify_required_tools` (`main.py:503-512`). Builds `missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]` where `_REQUIRED_TOOLS = ('git', 'just', 'uv')` (`main.py:56`). Message: `f'required tool(s) not found on PATH: {", ".join(missing)} — install the missing tool(s) before scaffolding. See https://github.com/casey/just#installation'` (`main.py:507-511`). Lists all missing tools joined by `, `.
- **Target directory availability** — `_verify_target_directory_absent(target_path)` (`main.py:515-522`). Raises if `target_path.exists()`. Message: `f'target directory already exists: {target_path} — choose a different package name or remove the existing directory'` (`main.py:518-521`). Carries the full target path.
- **Template remote reachability** — `_verify_template_remote_reachable` (`main.py:525-558`). Runs `git ls-remote <_TEMPLATE_REPOSITORY_URL>` with `check=False, capture_output=True, text=True, timeout=_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (10s, `main.py:65`). Two failure shapes:
  - `TimeoutExpired`: friendly = `'repository unreachable — check your network connection'`; raw = `'template remote unreachable (git ls-remote timed out after 10s)'`; combined `f'{friendly}\n\n{raw}'` (`main.py:541-548`).
  - Non-zero return code: raw = `'template remote unreachable (git ls-remote exit code {returncode}): {stderr_text}'`; friendly comes from `humanize_git_clone_error(stderr_text)`; message is `f'{friendly_msg}\n\n{raw}'` if a friendly match exists, else just `raw` (`main.py:550-558`).
- **Package-name validity** — there is no dedicated preflight verifier; the registry slot is `lambda: None` (`main.py:569`). Actual validation happens at argument-parse time in `validate_package_name` (`main.py:173-186`), which raises `ArgumentTypeError` (not `RuntimeError`). Messages: invalid form → `f'Invalid package name: {value!r} — {reason}'` where `reason` comes from `_explain_invalid_package_name` (`main.py:151-170`: "name must not be empty" / "name contains a disallowed character: {char!r} (only letters, digits, '.', '_', '-' are allowed)" / "name must start and end with a letter or digit"); stdlib collision → `f'Package name {value!r} collides with the Python standard-library module {module_name!r}'` (`main.py:181-184`).

## Q3: Conventions for composing user-facing error messages

### Findings
- **Friendly + raw two-part pattern**: a human hint and the raw diagnostic are joined by a blank line: `f'{friendly}\n\n{raw}'`, falling back to `raw` alone when no friendly match exists. Used in `_verify_template_remote_reachable` (`main.py:547`, `557`) and `init_new_package`'s git-clone failure (`main.py:617`). Identical `if friendly else raw` idiom in both.
- **Reusable hint translation** lives in `humanize_git_clone_error(stderr_text)` (`main.py:68-74`), which scans the module-level table `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20-52`): a `list[tuple[re.Pattern, str]]` ordered most-specific-first ("Ordered most-specific first so that a more precise pattern wins", `main.py:19`). It lowercases input and returns the first matching friendly string, or `None`. Categories: network, repo-not-found, auth, destination-occupied, broad filesystem-permission (intentionally last, `main.py:47`).
- **Inline-hint pattern (em-dash suffix)**: many one-shot messages append a remediation hint after an em dash `—` directly: required-tools (`main.py:508`), target-dir (`main.py:520`), invalid name/email/url (`main.py:177`, `203`, `211`), just-check-failed (`main.py:663-664`). Install hints point at `https://github.com/casey/just#installation` (`main.py:510`, `640`).
- **Checklist line formatting helper**: `_format_check_line(label, *, ok)` (`main.py:497-500`) returns `f'  {marker:<6} {label}'` where marker is `'[ok]'` or `'[FAIL]'`, padded to 6 chars for label alignment.
- Validators raise `ArgumentTypeError` (parse layer); verifiers and subprocess steps raise `RuntimeError` (scaffolding layer). Message-building is inline at each raise site; the only extracted helpers are `humanize_git_clone_error`, `_explain_invalid_package_name`, and `_format_check_line`.

## Q4: Failure propagation through `init_new_package` and `main`; exit status

### Findings
- `init_new_package` returns `int` (`main.py:590-667`). It raises `RuntimeError` for hard failures and returns an int code for soft outcomes:
  - `_run_preflight_checks` failure → `RuntimeError` propagates out before any subprocess (`main.py:603`).
  - git clone non-zero → builds friendly+raw message, raises `RuntimeError` (`main.py:614-618`).
  - `just init` `FileNotFoundError` (just missing) → re-raised as `RuntimeError` with install hint (`main.py:637-642`).
  - `just init` non-zero → `RuntimeError` `'just init failed with exit code {n}: {stderr}'` (`main.py:646-648`).
  - `just check`: **does not raise**. Returns `0` and prints "just check passed …" on success (`main.py:659-661`); returns `1` and prints "just check failed … review the output in {module_name}." to stderr on failure (`main.py:662-667`).
- `main` (`main.py:670-691`): wraps the `init_new_package(...)` call in `try/except RuntimeError`; on exception it prints the error to `sys.stderr` and returns `1` (`main.py:687-689`). Otherwise returns whatever `init_new_package` returned (`main.py:679`). Version branch prints and the function returns `0`; no-package-name path returns `0` (`main.py:674-691`).
- Net exit-status mapping: any preflight/clone/just-init `RuntimeError` → caught in `main` → `1`. A failing `just check` (no exception) → `init_new_package` returns `1` → `main` returns `1`. Success → `0`. Tests: `test_main_returns_one_on_failure` (`test_main.py:502-514`), `test_main_returns_one_when_just_check_fails` (`test_main.py:471-482`), `test_main_surfaces_stderr_on_failure` (`test_main.py:485-499`).
- Argument validation errors (`ArgumentTypeError`) are converted by `_validated_or_error` → `parser.error(...)` → `SystemExit` code `2`, before `main`'s body runs (`main.py:323-334`; tests `test_main.py:198-223`, `983-998` assert exit code 2).

## Q5: Ordering between preflight checks and the first mutating/network step (git clone)

### Findings
- In `init_new_package`, `_run_preflight_checks(new_package_path)` is called at `main.py:603`, **before** the first `Popen(['git', 'clone', ...])` at `main.py:605-610`. There is no filesystem-mutating or network call between them.
- The ordering guarantee is structural: `_run_preflight_checks` raises on the first failing check and the exception propagates out of `init_new_package` (`main.py:584-586`), so control never reaches the clone `Popen`. Preflight itself only reads (`shutil.which`, `Path.exists`, `git ls-remote` which does not write locally).
- Tests assert the clone never starts when a check fails by checking `popen_mock.call_count == 0`:
  - missing tool: `test_verify_required_tools_missing_git/just/uv` (`test_main.py:373-415`), `test_verify_required_tools_reports_all_missing` (`test_main.py:426-442`).
  - target dir exists: `test_init_new_package_aborts_when_target_directory_exists` (`test_main.py:1146-1159`).
  - remote unreachable: `test_init_new_package_aborts_when_remote_unreachable` (`test_main.py:654-664`).
- Note: the remote-reachability probe uses `run` (mockable separately as `modernpackage.main.run`), while clone/init/check use `Popen`; tests rely on this split to assert "checks ran but Popen did not."

## Q6: How preflight checks and verifier failure messages are tested

### Findings
- **Mocking seams**: tests patch on the module object — `modernpackage.main.shutil.which`, `modernpackage.main.Popen`, `modernpackage.main.run`, `modernpackage.main.print`, `modernpackage.main.ArgumentParser` (e.g. `test_main.py:373-385`, `587-595`, `445-468`). `shutil.which` is patched with a `side_effect` function returning `None` for the targeted tool (`test_main.py:374-376`).
- **Subprocess stubbing**: `run_mock.return_value = MagicMock(returncode=0, stderr='')` for the reachability probe; `popen_mock.return_value.returncode` / `.communicate.return_value = (b'', b'')` for clone/init/check. Multi-step sequences use `popen_mock.side_effect = [mock1, mock2, ...]` (`test_main.py:351`, `368`, `627`).
- **Verifier-level unit tests** call verifiers directly: `_verify_required_tools` (`test_main.py:418-423`), `_verify_target_directory_absent` with real `tmp_path` dirs (`test_main.py:1179-1188`), `_verify_template_remote_reachable` with mocked `run` for reachable / resolve-host / repo-not-found / `TimeoutExpired` (`test_main.py:1191-1229`).
- **Asserting on message content**: failure tests use `pytest.raises(RuntimeError, match=...)` with substrings ('git', 'uv', 'already exists', 'repository unreachable', 'git clone failed with exit code 1') and also inspect `str(exc_info.value)` for multiple fragments — e.g. `test_verify_template_remote_reachable_raises_on_resolve_host` asserts both 'check your network' and 'git ls-remote exit code 2' and 'Could not resolve host' (`test_main.py:1204-1207`). `humanize_git_clone_error` has exact-equality tests per category (`test_main.py:533-566`).
- **Checklist output tests** use `capsys` to assert exact `[ok]`/`[FAIL]` lines and their order: full-clean-run (`test_main.py:584-608`), fail-and-abort (`test_main.py:667-686`), early-abort-omits-later-lines (`test_main.py:689-709`).
- **Abort-before-mutation** asserted via `assert popen_mock.call_count == 0` across all preflight-failure tests (Q5 list). Success path asserts `popen_mock.call_count == 3` (clone + init + check, `test_main.py:294`, `1176`).
- Tests are top-level `def test_*` functions, plain `assert`, built-in `tmp_path`/`monkeypatch`/`capsys` fixtures, seed helpers prefixed `_` (`_write_config`, `_seed_pyproject`, `_parse_args_with_config`).

## Cross-Cutting Observations
- Two error layers: parse-time validation raises `ArgumentTypeError` → `SystemExit(2)`; scaffolding-time checks/steps raise `RuntimeError` → caught in `main` → exit `1`.
- The same friendly-translation table (`humanize_git_clone_error`) is reused by both the preflight reachability probe (`main.py:556`) and the actual clone failure path (`main.py:616`), giving consistent network/auth/not-found wording in both places.
- Module-level constants drive behavior: `_REQUIRED_TOOLS` (`main.py:56`), `_TEMPLATE_REPOSITORY_URL` (`main.py:61`), `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`main.py:65`), `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20`).
- The "package name valid" preflight entry is presentational only (`lambda: None`); real enforcement is upstream at parse time. The checklist still prints `[ok]` for it on every run.

## Open Areas
- The `package name valid` check is a no-op placeholder in the preflight registry (`main.py:569`); there is no `RuntimeError`-raising verifier for package name inside `_run_preflight_checks`. Whether name validation is "a preflight check" depends on framing — it lives in the argparse layer (`validate_package_name`, `main.py:173`), not the registry.
- `_write_package_metadata` and the `just check` step run *after* the clone (post-mutation); they are outside the preflight scope but are where soft (`return 1`) vs hard (`raise`) failures diverge (`main.py:620-667`).
