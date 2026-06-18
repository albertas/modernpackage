# Research Findings

Scope is small: one source module (`modernpackage/main.py`), two test files
(`tests/test_main.py`, `tests/test_e2e.py`), plus config in `pyproject.toml`.
All findings below come from reading those files directly.

## Q1: How are the metadata CLI options defined in `parse_args`?

### Findings
`parse_args` builds a bare `ArgumentParser()` (no prog/description) and adds the
options at `main.py:145-188`. The five metadata options:

- `--author-name` (`main.py:161-165`): `help='Author name to record in the new
  package.'`, `default=None`, no `type=` (plain string).
- `--description` (`main.py:166-170`): `help='Short description of the new
  package.'`, `default=None`, no `type=`.
- `--author-email` (`main.py:171-176`): `help='Author email to record in the new
  package.'`, `type=validate_author_email`, `default=None`.
- `--license` (`main.py:177-181`): `help='License identifier for the new
  package.'`, `default=None`, no `type=`. Stored on the namespace as
  `parsed_args.license` (the attribute name, later mapped to `package_license`).
- `--repository-url` (`main.py:182-187`): `help='Repository URL to record in the
  new package.'`, `type=validate_repository_url`, `default=None`.

All five default to `None`. Only the email and URL options have validators.
Other args defined in the same parser: `-v/--version` (`store_true`,
`default=False`, `main.py:148-154`) and positional `package_name`
(`nargs='?'`, `type=validate_package_name`, `main.py:155-160`).

## Q2: How do `validate_author_email` / `validate_repository_url` and their regex constants work; when are they invoked vs. defaults?

### Findings
- Regex constants defined at module level:
  - `_EMAIL_RE = re.compile(r'^\S+@\S+\.\S+$')` (`main.py:74`) — permissive shape
    (non-whitespace, `@`, non-whitespace, `.`, non-whitespace); comment notes
    full RFC 5322 is out of scope ("design Decision 4").
  - `_REPOSITORY_URL_RE = re.compile(r'^https?://\S+$')` (`main.py:77`) — requires
    an http(s):// scheme; no reachability check ("design Decision 5").
- `validate_author_email` (`main.py:129-134`): if `_EMAIL_RE.match(value)` is
  falsy, raises `ArgumentTypeError(f'Invalid author email: {value!r} — expected
  name@domain.tld')`; otherwise returns `value` unchanged.
- `validate_repository_url` (`main.py:137-142`): if `_REPOSITORY_URL_RE.match`
  falsy, raises `ArgumentTypeError(f'Invalid repository URL: {value!r} — expected
  http(s)://…')`; otherwise returns `value`.
- **Lifecycle**: argparse calls a `type=` callable only on a string value
  actually supplied on the command line. Because each option's `default=None` and
  the default is not a string, argparse passes the default through WITHOUT
  running the validator. So when the option is omitted the value is `None` and
  the regex never runs; the validators fire only on user-supplied input. Verified
  by `test_parse_args_metadata_defaults_none` (`test_main.py:157-164`), where all
  metadata attributes are `None` with no validation error.

## Q3: How are parsed values threaded from `parse_args` → `main` → `init_new_package`?

### Findings
- `main` (`main.py:264-285`) calls `parse_args()` then, when
  `parsed_args.package_name` is set, calls `init_new_package` with keyword args
  (`main.py:271-280`), mapping:
  - `package_name=parsed_args.package_name`
  - `author_name=parsed_args.author_name`
  - `author_email=parsed_args.author_email`
  - `description=parsed_args.description`
  - `package_license=parsed_args.license` (note: namespace attr `license` →
    param `package_license`)
  - `repository_url=parsed_args.repository_url`
- `init_new_package` signature (`main.py:191-199`): `package_name: str` positional;
  remaining metadata are keyword-only (`*`) params each defaulting to `None`,
  typed `str | None`. Carries `# noqa: PLR0913` (too-many-args).
- **Currently discarded**: `main.py:201-203` immediately does
  `del author_name, author_email, description, package_license, repository_url`.
  The comment states they are "Threaded for later V4 work (writing metadata into
  pyproject.toml); not yet consumed. The `del` documents intent and satisfies
  ruff ARG001." The function then proceeds with `git clone` + `just init` +
  `just check` using only `package_name` (`main.py:205-261`).

## Q4: Where are environment variables read/referenced today; naming and access patterns?

### Findings
- **No source code reads environment variables.** `modernpackage/main.py` and
  `modernpackage/__init__.py` contain no `os.environ`, `os.getenv`, `getenv`,
  or `getpass` usage (grep over `*.py` returns nothing in `modernpackage/`).
  `main.py` does not even import `os`.
- The only environment-variable usage is in the e2e test
  (`tests/test_e2e.py`):
  - `_GIT_IDENTITY_ENV: dict[str, str]` module constant (`test_e2e.py:29-34`)
    holds `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`,
    `GIT_COMMITTER_EMAIL` (all set to `e2e` / `e2e@example.com`).
  - Accessed via `env=os.environ | _GIT_IDENTITY_ENV` passed to the `just init`
    subprocess (`test_e2e.py:68`) — merges the real environment with the fixed
    git identity. `import os` at `test_e2e.py:17`.
- Naming convention observed for env vars: uppercase `SCREAMING_SNAKE_CASE`,
  standard git names (`GIT_AUTHOR_*`, `GIT_COMMITTER_*`). No project-specific env
  var names exist anywhere in the codebase.

## Q5: How does the test suite construct argument scenarios and verify defaults; isolation mechanisms?

### Findings
Two distinct patterns in `tests/test_main.py`:

1. **`parse_args` tests patch `sys.argv`** via `unittest.mock.patch` as a context
   manager, then call `parse_args()` and assert on the returned namespace:
   - version flag: `patch('sys.argv', ['modernpackage', '--version'])`
     (`test_main.py:93-96`).
   - per-option: e.g. `test_parse_args_author_name` (`test_main.py:105-108`),
     `--description` (`111-114`), `--license` (`117-120`),
     `--author-email` (`132-135`), `--repository-url` (`148-154`).
   - **defaults**: `test_parse_args_metadata_defaults_none`
     (`test_main.py:157-164`) patches argv to just `['modernpackage',
     'mypackage']` and asserts all five metadata attrs are `None`.
2. **`main` tests patch the `ArgumentParser` class** on the module
   (`patch('modernpackage.main.ArgumentParser')`) and set attributes on the mock
   namespace, e.g. `argparse_mock().parse_args().version = False` / `.package_name
   = 'mypackage'` / each metadata attr `= None` (`test_main.py:231-253`). This
   isolates `main`'s orchestration from real argparse.
- Validator unit tests call the functions directly and assert on return value or
  `pytest.raises(ArgumentTypeError, match=...)`: e.g.
  `test_validate_author_email_accepts/rejects` (`test_main.py:123-129`),
  `test_validate_repository_url_accepts/rejects` (`138-145`).
- `init_new_package` tests patch `modernpackage.main.Popen` (`MagicMock`),
  setting `.returncode` and `.communicate.return_value`, sometimes via
  `side_effect` lists for per-call control (e.g. `test_main.py:212-215`,
  `360-373`).
- **No `monkeypatch` and no environment fixtures are used in `test_main.py`.**
  The e2e test uses the built-in `tmp_path` fixture (`test_e2e.py:53`) and a
  helper `_run` wrapper around `subprocess.run(..., check=False,
  capture_output=True, text=True)` (`test_e2e.py:37-49`); it is gated behind the
  `@pytest.mark.e2e` marker (`test_e2e.py:52`), which the default pytest addopts
  exclude (`pyproject.toml:40`, `-m 'not e2e'`).
- Test style: top-level `def test_*` functions returning `-> None`, plain
  `assert`, no test classes — matches CLAUDE.md/code-style guidance.

## Q6: Conventions new code is expected to match (constants, regex naming, annotations, helpers)?

### Findings
- **Module-level constants**: `_`-prefixed, `SCREAMING_SNAKE_CASE`, annotated.
  Examples: `_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern[str], str]]`
  (`main.py:12`), `_STDLIB_MODULE_NAMES: frozenset[str]` (`main.py:70`).
- **Regex constants suffixed `_RE`** and typed `re.Pattern[str]`, compiled at
  module level, each preceded by an explanatory comment: `_PACKAGE_NAME_RE`
  (`main.py:58`), `_DISALLOWED_CHAR_RE` (`main.py:65`), `_EMAIL_RE` (`main.py:74`),
  `_REPOSITORY_URL_RE` (`main.py:77`).
- **Type annotations**: full annotations on every function signature and return
  type; constants annotated. Optionals written `str | None` (PEP 604).
- **Helper functions**: small, single-purpose; module-private helpers `_`-prefixed
  (`_explain_invalid_package_name`, `main.py:80`); validators are public (non-`_`)
  named `validate_*` and return the validated value or raise `ArgumentTypeError`
  (`validate_package_name`, `validate_author_email`, `validate_repository_url`).
- **Docstrings**: one-line imperative docstrings on every function; longer
  docstrings document edge cases / out-of-scope decisions (`main.py:81-87`,
  `118-125`). No module-level docstring beyond the top file summary
  (`main.py:1`).
- **Strings**: single quotes throughout (ruff `inline-quotes = "single"`,
  `pyproject.toml:59-64`).
- **Error handling**: raises `ArgumentTypeError` for CLI validation,
  `RuntimeError` for process failures (`main.py:217-221`, `240-242`); subprocess
  boundary uses `check=False` style in tests.
- **Lint config** (`pyproject.toml:56-95`): ruff `select = ["ALL"]`, line-length
  88, mccabe `max-complexity = 8`, mypy `strict = True`, `python_version =
  "3.14"`. Inline `# noqa: ...` codes used where intentional (e.g. `PLR0913`,
  `S603`, `S607`, `T201`, `ARG001`).

## Cross-Cutting Observations
- The metadata feature is half-wired: CLI fully parses and threads all five
  metadata values into `init_new_package`, but the function deliberately `del`s
  them (`main.py:201-203`) pending "later V4 work (writing metadata into
  pyproject.toml)". The plumbing/tests already exist; only consumption is absent.
- Validators run only on supplied values; `default=None` bypasses `type=`
  callables — a relevant detail for any environment-default mechanism, since a
  default sourced elsewhere would similarly not pass through these validators
  unless explicitly validated.
- Two `print` targets: success → stdout, failures → `sys.stderr`
  (`main.py:254-260`, `282`).

## Open Areas
- The questions reference reading metadata defaults "from environment," but **no
  environment-variable reading exists in source today** — the only precedent is
  the e2e test's `GIT_AUTHOR_*`/`GIT_COMMITTER_*` constants (`test_e2e.py:29-34`).
  There is no established project convention for env-var names or access in
  `modernpackage/main.py` to model from.
