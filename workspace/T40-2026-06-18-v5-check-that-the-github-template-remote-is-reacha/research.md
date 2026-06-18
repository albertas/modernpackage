# Research Findings

Scope: `modernpackage/main.py` (single module) and the test suites under
`tests/`. All references are `file:line`.

## Q1: End-to-end flow of `init_new_package`

### Findings
`init_new_package` is defined at `modernpackage/main.py:497-575`. Ordered steps:

1. `module_name = normalize_module_name(package_name)` — `.`/`-` → `_`
   (`main.py:507`, helper `main.py:180-188`).
2. `new_package_path = Path.cwd() / module_name` (`main.py:508`).
3. Pre-flight: `_verify_required_tools()` then
   `_verify_target_directory_absent(new_package_path)` (`main.py:510-511`).
4. **git clone** via `Popen` (`main.py:513-518`): argv
   `['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path]`,
   all three streams set to `PIPE`. `pipe.communicate()` then decode stderr
   (`main.py:519-520`). Non-zero exit → humanized `RuntimeError`
   (`main.py:522-526`).
5. `_write_package_metadata(...)` rewrites the cloned `pyproject.toml`
   (`main.py:528-535`, helper `main.py:407-454`).
6. **just init** via `Popen` with `cwd=new_package_path` (`main.py:538-544`),
   argv `['just', 'init', module_name]`; wrapped in `try/except FileNotFoundError`
   → `RuntimeError` (`main.py:545-550`). Non-zero exit → `RuntimeError`
   (`main.py:551-556`).
7. **just check** via `Popen` with `cwd=new_package_path` (`main.py:558-565`),
   argv `['just', 'check']`. Exit 0 → print success, return 0; else print to
   stderr, return 1 (`main.py:567-575`).

The **template URL is used only at the clone step** (`main.py:514`), step 4.
Three subprocesses total, all `Popen` (the `run` helper is used elsewhere only
in `_git_config_default`, `main.py:222`). The test
`test_init_new_package` asserts exactly 3 `Popen` calls (`tests/test_main.py:288`).

## Q2: Pre-flight validation helpers before the clone

### Findings
Two helpers run before clone, both invoked at `main.py:510-511`:

- `_verify_required_tools()` (`main.py:475-484`): builds
  `missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]`;
  if non-empty, raises `RuntimeError` listing missing tools plus remediation
  ("install the missing tool(s)…" + a just install URL). `_REQUIRED_TOOLS =
  ('git', 'just', 'uv')` at `main.py:56`.
- `_verify_target_directory_absent(target_path)` (`main.py:487-494`): if
  `target_path.exists()`, raises `RuntimeError` ("target directory already
  exists: … — choose a different package name or remove…").

Failure signalling: both raise `RuntimeError` (no return value), caught in
`main()` at `main.py:595-597` which prints and returns 1. Because they raise
before any `Popen`, tests assert `popen_mock.call_count == 0`
(`tests/test_main.py:357,370,383,408,1030`).

## Q3: git/subprocess failure detection & the humanizing layer

### Findings
Detection at clone (`main.py:519-526`):
- `_stdout, stderr = pipe.communicate()`; `stderr_text = stderr.decode().strip()`
  (`main.py:519-520`) — bytes decoded with default (UTF-8), stripped.
- `if pipe.returncode != 0:` builds `raw = f'git clone failed with exit code
  {pipe.returncode}: {stderr_text}'` (`main.py:522-523`).
- `friendly = humanize_git_clone_error(stderr_text)` (`main.py:524`); final
  message is `f'{friendly}\n\n{raw}'` when a friendly match exists, else `raw`
  (`main.py:525`), raised as `RuntimeError` (`main.py:526`).

`just init` failures use the same pattern but **no humanizing layer**
(`main.py:551-556`); a missing `just` binary raises before `communicate` via
`except FileNotFoundError` (`main.py:545-550`). `just check` failures don't raise
— they print and return 1 (`main.py:570-575`).

`humanize_git_clone_error(stderr_text)` (`main.py:59-65`): lowercases input
(`main.py:61`), iterates `_GIT_CLONE_ERROR_MESSAGES` and returns the first
pattern whose `.search()` matches, else `None`.

Pattern table `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20-52`), a
`list[tuple[re.Pattern[str], str]]`, **ordered most-specific-first** (comment
`main.py:19`):
- network (`could not resolve host|could not read from remote|failed to connect|
  connection timed out|network is unreachable`) → "repository unreachable —
  check your network connection" (`main.py:22-28`).
- repo-not-found (`repository.*not found|remote: not found|does not exist`) →
  "template repository not found — it may have moved or been removed"
  (`main.py:30-33`).
- auth (`permission denied \(publickey\)|authentication failed|could not read
  username`) → "authentication failed…"; comment notes it must precede the broad
  permission-denied rule (`main.py:34-41`).
- directory occupied (`already exists and is not an empty directory`) →
  "destination directory already exists…" (`main.py:43-46`).
- broad filesystem (`permission denied|could not create|unable to create`),
  "intentionally last" → "cannot write to the destination directory…"
  (`main.py:47-51`).

## Q4: Where the template remote URL lives

### Findings
- The clone URL `'https://github.com/albertas/modernpackage'` is a **bare string
  literal inline in the `Popen` argv** at `main.py:514`. There is **no shared
  constant** for it.
- The same string appears separately in `_write_package_metadata` at
  `main.py:448` as the `str.replace` target for the metadata `repository_url`
  substitution — a second independent literal of the same URL.
- No module-level constant aggregates these; `grep` for the URL finds only these
  two occurrences plus tests (`tests/test_main.py:938`). (Contrast: tools, env
  vars, regexes, and git-config keys ARE module-level constants —
  `main.py:56,93-110`.)

## Q5: How the test suite exercises the clone path

### Findings
Primary pattern: `with patch('modernpackage.main.Popen') as popen_mock`
(`tests/test_main.py:284,292,307,317,328,341,353,366,379,399,537,559,571,1024,
1037`). Two mock shapes:

- **Uniform mock** — every `Popen()` returns the same object:
  `popen_mock.return_value.returncode = 0` and
  `popen_mock.return_value.communicate.return_value = (b'', b'')`
  (`tests/test_main.py:285-286`). Used for happy paths and single-stage
  failures.
- **Per-call sequence** — `popen_mock.side_effect = [git_clone_mock,
  just_init_mock, just_check_mock]` of distinct `MagicMock`s, each with its own
  `returncode` and `communicate.return_value` (`tests/test_main.py:548-562`).
  Also used to inject `FileNotFoundError` as a side-effect element for the
  "just not installed" case (`tests/test_main.py:329`).

Simulating failures:
- Non-zero exit + stderr bytes: `returncode = 1`,
  `communicate.return_value = (b'', b'some error')`
  (`tests/test_main.py:318-319`); network case feeds
  `b'fatal: Could not resolve host: github.com'` (`tests/test_main.py:573-576`).

Asserting on `RuntimeError`:
- `pytest.raises(RuntimeError, match='git clone failed with exit code 1')`
  (`tests/test_main.py:320`); `match=r'just.*install'` (`:330`);
  `match='just init failed with exit code 1'` (`:343`). Network test inspects
  `str(exc_info.value)` for both the friendly and raw fragments
  (`tests/test_main.py:577-582`).

Asserting on argv / cwd: `popen_mock.call_args_list[0]` (clone),
`[1]` (init), `[2]` (check); e.g. `clone_call.args[0][-1]` is the clone target
path (`tests/test_main.py:297-299`), and
`init_call.kwargs['cwd'] == Path.cwd() / 'my_cool_package'`
(`tests/test_main.py:303`).

`humanize_git_clone_error` is tested directly with raw git strings
(`tests/test_main.py:499-532`), one test per pattern plus an unknown→None case.

`_git_config_default` (the only `run`-based seam) is patched as
`modernpackage.main.run` returning `MagicMock(returncode=, stdout=)`
(`tests/test_main.py:586-606`).

`tests/test_e2e.py` does NOT exercise `init_new_package`; it replicates the
clone+init flow against the local repo root via `subprocess.run`
(`tests/test_e2e.py:8-11,43,63,75,92`) to avoid hitting GitHub.

## Q6: Defensive subprocess conventions & remediation phrasing

### Findings
- **Clone/init/check use `Popen` with all three streams `PIPE`** (`stdin=PIPE,
  stdout=PIPE, stderr=PIPE`) and `communicate()`
  (`main.py:513-519,538-543,558-565`). Subprocess `cwd` is set for init/check
  (`main.py:543,564`).
- **`_git_config_default` uses `run(..., check=False, capture_output=True,
  text=True)`** (`main.py:222-227`) — the documented "degrade gracefully at
  boundaries" style: returns `None` on `FileNotFoundError`, non-zero exit, or
  empty output (`main.py:228-232`); never raises.
- **`check` is never `True`**: clone/init inspect `pipe.returncode` manually
  (`main.py:522,554,567`); `run` passes `check=False` explicitly
  (`main.py:224`). This matches CLAUDE/code-style guidance on graceful boundary
  degradation.
- **Decoding**: `Popen` stderr decoded with `stderr.decode().strip()`
  (`main.py:520,552`); `run` uses `text=True` and strips stdout (`main.py:232`).
- **`# noqa` security annotations**: every subprocess call carries `# noqa: S603`
  (subprocess call) on the call and `# noqa: S607` (partial executable path /
  start-process-with-partial-path) on the argv line — `main.py:513-514` (clone),
  `538-539` (init), `559` (check), `222-223` (`run`). Related `# noqa`: `T201`
  on `print` (`main.py:271,429,568,570,583,596`), `PLR0913` on wide signatures
  (`main.py:407,497`).
- **Remediation phrasing** — messages use an em-dash then a fix imperative:
  - `_verify_required_tools`: "required tool(s) not found on PATH: … — install
    the missing tool(s) before scaffolding. See https://github.com/casey/just#installation"
    (`main.py:479-483`).
  - `_verify_target_directory_absent`: "… — choose a different package name or
    remove the existing directory" (`main.py:491-493`).
  - just-not-found: "'just' command not found — install it to initialize the
    package. See https://github.com/casey/just#installation" (`main.py:546-549`).
  - humanized clone messages all follow "<problem> — <suggested check/action>"
    (`main.py:27,32,40,45,50`).
  - just check failure: "… — review the output in {module_name}."
    (`main.py:571-573`).

## Cross-Cutting Observations
- Two subprocess idioms coexist by intent: `Popen`+`PIPE`+manual `returncode`
  for the scaffolding pipeline; `run(check=False, capture_output, text)` for the
  silent git-config probe.
- Failure model: pre-flight + clone + just-init raise `RuntimeError` (caught in
  `main()`, `main.py:595-597`); `just check` is non-fatal (return code only).
- Friendly-message humanization exists ONLY for git clone, not for `just init`/
  `just check`.
- Module-level constants are the norm for tools, env vars, git keys, and regex
  tables (`main.py:56,93-110,20-52`), making the inline, duplicated template URL
  (`main.py:514` and `448`) a notable deviation from the module's own pattern.

## Open Areas
- No reachability/network pre-check for the template remote exists today; the
  clone itself is the first network contact, and only post-hoc stderr matching
  (`humanize_git_clone_error`) classifies an unreachable remote (`main.py:22-28`).
- Whether the two duplicate URL literals are meant to stay independent (clone vs.
  metadata-replacement target) is not stated in code comments.
