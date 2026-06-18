# Research Findings

Scope: `modernpackage/main.py`, `tests/test_main.py`, `tests/test_e2e.py`,
`pyproject.toml`. The codebase is small and self-contained; all findings come
from direct reading of these files.

## Q1: How is author name/email metadata resolved at startup — sources, helpers, precedence?

### Findings
- Resolution happens entirely inside `parse_args()` (`main.py:177-252`). There
  are **two** sources today: CLI flags and environment variables. **Git config
  is NOT consulted anywhere** — no `git config` invocation exists in the module.
- CLI flags `--author-name` and `--author-email` are registered with
  `default=None` (`main.py:193-200`, `201-217`). `--author-email` additionally
  has `type=validate_author_email` (`main.py:215`).
- After `parser.parse_args()`, each metadata field that is still `None` falls
  back to its env var via `_environment_default(...)` (`main.py:236-245`):
  - `author_name` → `_AUTHOR_NAME_ENV` = `'MODERNPACKAGE_AUTHOR_NAME'` (`main.py:86`, `236-237`)
  - `author_email` → `_AUTHOR_EMAIL_ENV` = `'MODERNPACKAGE_AUTHOR_EMAIL'` (`main.py:87`, `242-243`)
  - also `description`, `license`, `repository_url` (`main.py:88-90`, `238-245`)
- Helper `_environment_default(variable_name)` returns `os.environ.get(name) or None`,
  so a **set-but-empty** env var is treated as unset (`main.py:158-160`).
- Precedence is documented in a comment as **flag > env > None** (`main.py:84-85`)
  and implemented by the `if arguments.X is None:` guards (`main.py:236-245`):
  the flag wins because env is only consulted when the flag left the value `None`.
- Env-sourced `author_email` and `repository_url` are re-validated after the
  fallback via `_validated_or_error(...)` (`main.py:246-251`); flag-sourced
  values were already validated by argparse `type=`. (Note: a flag-provided
  email is validated twice — once by argparse, once by `_validated_or_error`.)

## Q2: How does the code invoke external CLI tools as subprocesses? Output capture, return codes, missing executable?

### Findings
- All external commands run through `subprocess.Popen` (imported as
  `from subprocess import PIPE, Popen`, `main.py:8`). `subprocess.run` is NOT
  used in `main.py` (it IS used in the e2e test — see Q5).
- Standard pattern in `init_new_package()` (`main.py:255-325`): construct
  `Popen([...], stdin=PIPE, stdout=PIPE, stderr=PIPE)`, then call
  `pipe.communicate()` to collect output (`main.py:272-278`, `288-301`, `308-315`).
- Three subprocesses, in order:
  1. `git clone https://github.com/albertas/modernpackage <path>` (`main.py:272-277`)
  2. `just init <module_name>` with `cwd=new_package_path` (`main.py:288-294`)
  3. `just check` with `cwd=new_package_path` (`main.py:308-314`)
- **Output capture**: `_stdout, stderr = pipe.communicate()`; stderr decoded and
  stripped: `stderr_text = stderr.decode().strip()` (`main.py:278-279`, `301-302`).
  For `just check`, output is not captured into a variable — `pipe.communicate()`
  is called for its side effect only (`main.py:315`).
- **Return-code checking**: `if pipe.returncode != 0:` after each step.
  - git clone failure → `RuntimeError`, enriched via `humanize_git_clone_error`
    (`main.py:281-285`).
  - just init failure → `RuntimeError` with exit code + stderr (`main.py:304-306`).
  - just check failure → prints to `sys.stderr` and returns `1` (does NOT raise)
    (`main.py:316-325`); success prints a message and returns `0` (`main.py:317-319`).
- **Missing executable**: only the `just init` call wraps `Popen` in
  `try/except FileNotFoundError`, re-raising a friendly `RuntimeError` advising
  to install `just` (`main.py:287-300`). The `git clone` and `just check`
  `Popen` calls are NOT wrapped, so a missing `git` would raise an uncaught
  `FileNotFoundError`.
- `# noqa: S603` / `# noqa: S607` suppress bandit warnings for subprocess +
  partial-path executables (`main.py:272`, `273`, `288`, `289`, `309`).
- `humanize_git_clone_error(stderr_text)` (`main.py:52-58`) lowercases stderr and
  returns the first matching friendly message from `_GIT_CLONE_ERROR_MESSAGES`
  (`main.py:17-49`), an ordered most-specific-first list of `(compiled_regex, message)`
  tuples; returns `None` when nothing matches.

## Q3: How are optional/default metadata values represented when absent? Where/how are name and email validated?

### Findings
- Absent values are represented as `None` throughout: argparse `default=None`
  (`main.py:200`, `208`, `217`, `225`, `234`); `_environment_default` returns
  `None` for unset/empty (`main.py:160`); `init_new_package` params default to
  `None` with type `str | None` (`main.py:256-262`).
- Email validation: `validate_author_email(value)` checks `_EMAIL_RE.match`
  (`main.py:142-147`). `_EMAIL_RE = re.compile(r'^\S+@\S+\.\S+$')` — a permissive
  shape, full RFC 5322 explicitly out of scope (`main.py:77-79`). Raises
  `ArgumentTypeError` on failure (`main.py:144-146`).
- **Author name has NO validator** — there is no `validate_author_name`. The
  `--author-name` flag has no `type=` (`main.py:193-200`) and name is never
  re-validated after env fallback. Any non-empty string is accepted as-is.
- Email validation is applied in two places: as argparse `type=` for the flag
  (`main.py:215`) and, post-fallback, via `_validated_or_error(parser,
  arguments.author_email, validate_author_email)` (`main.py:246-248`) so that
  env-sourced emails are also validated.
- `_validated_or_error(parser, value, validator)` (`main.py:163-174`): returns
  `None` for `None` input; otherwise calls the validator and converts a raised
  `ArgumentTypeError` into `parser.error(str(error))` (which exits with code 2).
- Other validators: `validate_package_name` (`main.py:115-128`),
  `validate_repository_url` (`main.py:150-155`), `_explain_invalid_package_name`
  (`main.py:93-112`).

## Q4: After resolution, how are metadata values threaded through the program? Who receives them, how consumed?

### Findings
- `main()` (`main.py:328-349`) reads the resolved `Namespace` and passes all five
  metadata fields as keyword args into `init_new_package(...)` (`main.py:337-344`):
  `author_name`, `author_email`, `description`, `package_license=parsed_args.license`,
  `repository_url`. Note the rename `license` → `package_license` (`main.py:343`).
- `init_new_package(package_name, *, author_name=None, author_email=None,
  description=None, package_license=None, repository_url=None)` is keyword-only
  for the metadata (`main.py:255-263`); `# noqa: PLR0913` suppresses too-many-args.
- **The metadata is NOT consumed downstream.** The function body immediately does
  `del author_name, author_email, description, package_license, repository_url`
  (`main.py:267`). The comment explains it is "Threaded for later V4 work
  (writing metadata into pyproject.toml); not yet consumed. The `del` documents
  intent and satisfies ruff ARG001." (`main.py:265-267`).
- Only `package_name` is used: normalized via `normalize_module_name` (`main.py:269`)
  and used to build `new_package_path` and the subprocess commands (`main.py:269-314`).

## Q5: How do tests exercise code that shells out? Subprocess seam mocking/patching, fixtures?

### Findings
- **Unit tests** patch `Popen` on the module object:
  `with patch('modernpackage.main.Popen') as popen_mock:` (`test_main.py:267`,
  `275`, `290`, `300`, `311`, `324`, `455`, `477`, `489`). This patches the seam
  on the defining module, matching the CLAUDE.md "patch the SDK seam on the
  defining module object" convention.
- Two mocking styles:
  - **Uniform return** for all calls: `popen_mock.return_value.returncode = 0;
    popen_mock.return_value.communicate.return_value = (b'', b'')`
    (`test_main.py:268-269`).
  - **Per-call sequencing** via `side_effect` with distinct `MagicMock`s, one per
    subprocess, to model different outcomes per step:
    `popen_mock.side_effect = [git_clone_mock, just_init_mock, just_check_mock]`
    (`test_main.py:308-312`, `321-325`, `467-480`).
- Assertions on subprocess interactions: `popen_mock.call_count == 3`
  (`test_main.py:271`); inspecting `popen_mock.call_args_list[N].args[0]` and
  `.kwargs['cwd']` to verify command and working directory (`test_main.py:280-296`).
- Missing-executable simulated by `FileNotFoundError` in `side_effect`:
  `popen_mock.side_effect = [git_clone_mock, FileNotFoundError('just not found')]`
  (`test_main.py:312`).
- `main()`/`parse_args()` tests patch `ArgumentParser`, `print`, and
  `init_new_package` on the module (`test_main.py:332-333`, `22-23`, `373`).
- **Fixtures used**: built-in `monkeypatch` for env vars
  (`monkeypatch.setenv`/`delenv`, e.g. `test_main.py:159-160`, `213-221`);
  `capsys` for captured stdout/stderr (`test_main.py:187`, `257`); `sys.argv`
  patched via `patch('sys.argv', [...])` (`test_main.py:96`, `102`, etc.).
  No custom `conftest.py`/fixtures — searched, none present.
- **E2E test** (`tests/test_e2e.py`) does NOT mock — it runs real subprocesses
  via a `_run` helper using `subprocess.run(..., check=False,
  capture_output=True, text=True)` (`test_e2e.py:37-49`), guarded by
  `@pytest.mark.e2e` (`test_e2e.py:52`) and `shutil.which` tool checks that
  `pytest.skip` when tools are absent (`test_e2e.py:54-56`). The `e2e` marker is
  excluded by default: `addopts = "... -m 'not e2e'"` (`pyproject.toml:40`).
  A git identity env dict `_GIT_IDENTITY_ENV` sets `GIT_AUTHOR_NAME`/`EMAIL` etc.
  for the `just init` commit (`test_e2e.py:29-34`, `65-69`).

## Q6: Conventions for module-private helpers, module-level constant naming, type annotations on helpers?

### Findings
- **Module-private helpers**: leading underscore marks privacy:
  `_environment_default` (`main.py:158`), `_validated_or_error` (`main.py:163`),
  `_explain_invalid_package_name` (`main.py:93`). Public surface (no underscore):
  `validate_*`, `normalize_module_name`, `humanize_git_clone_error`,
  `parse_args`, `init_new_package`, `main`. Tests import private names directly
  from the module (e.g. `from modernpackage.main import ...`, `test_main.py:8-17`).
- **Module-level constants**: UPPER_SNAKE, underscore-prefixed when private.
  Compiled regexes suffixed `_RE`: `_PACKAGE_NAME_RE` (`main.py:63`),
  `_DISALLOWED_CHAR_RE` (`main.py:70`), `_EMAIL_RE` (`main.py:79`),
  `_REPOSITORY_URL_RE` (`main.py:82`). Env var name constants suffixed `_ENV`:
  `_AUTHOR_NAME_ENV`, `_AUTHOR_EMAIL_ENV`, `_DESCRIPTION_ENV`, `_LICENSE_ENV`,
  `_REPOSITORY_URL_ENV` (`main.py:86-90`). Other: `_GIT_CLONE_ERROR_MESSAGES`
  (`main.py:17`), `_STDLIB_MODULE_NAMES` (`main.py:75`).
- **Type annotations**: module-level constants are explicitly annotated even when
  inferable — e.g. `_AUTHOR_NAME_ENV: str = '...'` (`main.py:86`),
  `_EMAIL_RE: re.Pattern[str] = re.compile(...)` (`main.py:79`),
  `_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern[str], str]]` (`main.py:17`),
  `_STDLIB_MODULE_NAMES: frozenset[str]` (`main.py:75`).
- Helper signatures are fully annotated, return types included:
  `_environment_default(variable_name: str) -> str | None` (`main.py:158`),
  `_validated_or_error(parser: ArgumentParser, value: str | None,
  validator: Callable[[str], str]) -> str | None` (`main.py:163-167`),
  `_explain_invalid_package_name(value: str) -> str` (`main.py:93`).
- `Callable` imported under `TYPE_CHECKING` and used as a forward reference type
  (`main.py:11-12`). Optional values use `X | None` union syntax throughout.
- Full-word naming (no abbreviations) per CLAUDE.md: `variable_name`,
  `package_name`, `module_name`, `new_package_path`, `stderr_text`,
  `lowercased`. Short throwaway `match` used for regex results
  (`main.py:103`, `144`). Docstrings present on public + private functions;
  ruff `select = ["ALL"]` with line-length 88, mccabe max-complexity 8
  (`pyproject.toml:56-79`).

## Cross-Cutting Observations
- The metadata-defaults system (flag > env > None) is fully built for five
  fields, but downstream **consumption is intentionally deferred** — values are
  threaded into `init_new_package` then immediately `del`-eted (`main.py:265-267`),
  labeled as "later V4 work (writing metadata into pyproject.toml)". The git
  identity is only used in the e2e test environment, never read by the program.
- Validation is asymmetric: email and repository URL have validators applied at
  both the argparse-`type` seam and the post-env-fallback seam; **author name and
  description have no validator at all**.
- Error handling follows CLAUDE.md's boundary policy: internal/external command
  failures degrade to `RuntimeError` (clone/init) or printed-stderr + return code
  (check), surfaced to the user in `main()` via try/except (`main.py:345-347`).

## Open Areas
- The task title references "read author name and email from the user's git",
  but **no git-config reading currently exists** in the codebase. The only git
  interaction is `git clone` (`main.py:272-277`) and the e2e test's
  `GIT_*` identity env vars (`test_e2e.py:29-34`). Whether/how a
  `git config user.name`/`user.email` source would fit the existing
  flag > env > None precedence is not determinable from current code — it is not
  implemented.
