# Research Findings

All references are to `modernpackage/main.py`, `tests/test_main.py`,
`pyproject.toml`, `README.md`, and `docs/` unless noted.

## Q1: Full flow of `parse_args()` and metadata default resolution

### Findings
- `parse_args()` lives at `main.py:206-285`. It builds an `ArgumentParser`,
  declares flags, calls `parser.parse_args()` (`main.py:264`), then fills
  unset values from fallback sources, then validates.
- Each metadata flag is declared with `default=None` so an omitted flag yields
  `None`: `--author-name` (`main.py:222-229`), `--description`
  (`main.py:230-237`), `--author-email` (`main.py:238-246`, `type=validate_author_email`),
  `--license` (`main.py:247-254`), `--repository-url` (`main.py:255-263`,
  `type=validate_repository_url`).
- Fallback ordering is enforced by the **sequence of `if … is None` guards**
  after parsing, not by a data structure:
  1. Environment defaults applied first for all five fields
     (`main.py:265-274`), in order: author_name, description, license,
     author_email, repository_url.
  2. Git-config defaults applied second, and **only** for author_name
     (`main.py:275-276`) and author_email (`main.py:277-278`).
  3. Validation of env/git-sourced email and URL applied last
     (`main.py:279-284`).
- Effective precedence per field: flag > env > git config > None for
  author_name / author_email; flag > env > None for description, license,
  repository_url. The "git config only for two fields" rule is enforced simply
  by there being no git-config block for the other three.
- `main()` (`main.py:361-382`) passes the resolved Namespace fields into
  `init_new_package(...)` as keyword arguments (`main.py:370-377`); note
  `license` maps to the `package_license` parameter (`main.py:375`).

## Q2: Env-variable reader and git-config reader behavior

### Findings
- `_environment_default(variable_name)` (`main.py:164-166`): returns
  `os.environ.get(variable_name) or None`. A missing var → `None`; a
  **set-but-empty** var → `None` (the `or None` coalesces falsy `''`).
- `_git_config_default(key)` (`main.py:169-189`): runs
  `run(['git', 'config', key], check=False, capture_output=True, text=True)`
  (`main.py:179-184`). Signals "not set" / degrades by returning `None` when:
  - `git` binary missing → `FileNotFoundError` caught (`main.py:185-186`).
  - non-zero return code (key unset → git exits 1) (`main.py:187-188`).
  - empty/whitespace stdout → `result.stdout.strip() or None` (`main.py:189`).
- Never raises; never prints a notice (documented as design Decision 4/6 in
  the docstring, `main.py:170-177`). Reads merged local-over-global config.
- Env var name constants: `main.py:86-90`. Git-config key constants:
  `_GIT_CONFIG_USER_NAME_KEY = 'user.name'`,
  `_GIT_CONFIG_USER_EMAIL_KEY = 'user.email'` (`main.py:95-96`).

## Q3: Where/how metadata is validated; flag vs non-flag sources

### Findings
- Validators: `validate_package_name` (`main.py:121-134`), `validate_author_email`
  (`main.py:148-153`, `_EMAIL_RE = ^\S+@\S+\.\S+$` at `main.py:79`),
  `validate_repository_url` (`main.py:156-161`, `_REPOSITORY_URL_RE =
  ^https?://\S+$` at `main.py:82`). Each raises `ArgumentTypeError` on failure.
  Only email and URL have shape validation; author_name, description, license
  are free strings (no validator).
- **Flag-supplied** values are validated at parse time via argparse `type=`
  hooks: `validate_author_email` (`main.py:244`) and `validate_repository_url`
  (`main.py:261`). An `ArgumentTypeError` raised here makes argparse exit with
  code 2.
- **Non-flag** values (env / git config) bypass the `type=` hooks (they are
  assigned directly to the Namespace), so they are re-validated explicitly
  after fallback resolution via `_validated_or_error(parser, value, validator)`
  (`main.py:192-203`; called at `main.py:279-284`). That helper returns `None`
  unchanged, else runs the validator, converting `ArgumentTypeError` into
  `parser.error(...)` (exit code 2).
- Only email and repository_url are re-validated for non-flag sources;
  license/description/author_name from env are never validated (free strings).
- Validation precedes any scaffolding — `parse_args()` returns before `main()`
  calls `init_new_package` (`main.py:363` then `370`).

## Q4: Conventions for reading/parsing structured files; declared parsing deps

### Findings
- **No structured-file parsing exists in the source.** A repo-wide grep for
  `tomllib`/`tomli`/`configparser`/`json`/config-file reading in
  `modernpackage/` found nothing; the only hit is a comment about future V4
  work writing into `pyproject.toml` (`main.py:298`).
- The only file/path operations in source: `pathlib.Path` import
  (`main.py:7`), `Path.cwd() / module_name` to build the clone target
  (`main.py:303`), and `subprocess` (`Popen`/`run`) for git/just
  (`main.py:8`, `305`, `321`, `341`, `179`).
- `pyproject.toml` itself is the project's single configuration hub but is read
  by external tools (ruff, mypy, pytest, hatchling), not by `modernpackage`
  code (`pyproject.toml:39-99`; `docs/overview.md:11,58`).
- **Declared dependencies**: runtime `dependencies = []` (`pyproject.toml:18`) —
  no third-party parsing libraries. Optional `test` extra lists tooling only
  (`pyproject.toml:27-37`). No TOML/YAML/INI parsing dependency is declared.
- `requires-python = ">= 3.14"` (`pyproject.toml:8`), so stdlib `tomllib`
  (added in 3.11) is available without any new dependency, though it is not
  currently imported.

## Q5: How the CLI advertises default sources (help / README / docs)

### Findings
- **Help text**: each flag's `help=` string names its env var, e.g.
  `'Author name to record in the new package. Defaults to
  $MODERNPACKAGE_AUTHOR_NAME.'` (`main.py:224-227`); same `Defaults to
  $MODERNPACKAGE_*` pattern for description (`233-236`), author_email
  (`241-244`), license (`249-252`), repository_url (`258-261`). Convention:
  `$ENV_VAR_NAME` referenced inline in a `Defaults to …` sentence. Git config
  is **not** mentioned in `--help`.
- A test asserts the help advertises env vars (`test_main.py:262-269`).
- **README** (`README.md:79-100`) "Optional Metadata Flags" section: bullet per
  flag with explicit precedence chains, e.g. `$MODERNPACKAGE_AUTHOR_NAME → git
  config user.name → None` (`README.md:83-84`), and a "Precedence" summary
  (`README.md:91-96`): `flag > env > git config > None` vs `flag > env > None`.
  Also documents empty-env-as-unset and silent git fallback
  (`README.md:96-98`).
- **docs/overview.md:55** mirrors this; **docs/vision.md:41-44** describes the
  (not-yet-built) per-user config file concept; **docs/architecture.md:393,408,489**
  document the validation helper and deferred pyproject writing.

## Q6: Test patterns for default resolution, precedence, graceful degradation

### Findings
- **Env-var fixtures via `monkeypatch`**: `monkeypatch.setenv(...)` for present
  values (`test_main.py:163,182,238,247,256`); `monkeypatch.delenv(...,
  raising=False)` to clear (`test_main.py:217-224,535-536`).
- **`sys.argv` patching** drives `parse_args()` through real argparse:
  `with patch('sys.argv', ['modernpackage', 'mypackage', ...])`
  (e.g. `test_main.py:99,164,538`).
- **Isolating subprocess/git**: `_git_config_default` is patched on the module
  object — `patch('modernpackage.main._git_config_default', ...)` with
  `return_value=None` or a `side_effect` keyed by config key
  (`test_main.py:227,539-545,582-585`). Lower-level tests patch
  `modernpackage.main.run` and set `MagicMock(returncode=..., stdout=...)`
  (`test_main.py:510-531`), and `Popen` for `init_new_package`
  (`test_main.py:273-333`).
- **Precedence assertions**:
  - flag > env: `test_parse_args_flag_overrides_env_author_email`
    (`test_main.py:169-178`), `test_parse_args_flag_overrides_env_description`
    (`244-250`).
  - flag > git config: `test_parse_args_flag_beats_git_config`
    (`534-551`) — also asserts git config was *not consulted* by checking the
    key is absent from `git_mock.call_args_list`.
  - env > git config: `test_parse_args_env_beats_git_config` (`554-570`),
    same not-consulted check.
  - git fills when flag+env absent:
    `test_parse_args_git_config_fills_when_flag_and_env_absent` (`573-588`).
- **Graceful degradation / not-set**:
  - git key unset (returncode 1) → None (`test_main.py:516-519`).
  - empty git value → None (`522-525`).
  - git missing (FileNotFoundError) → None (`528-531`).
  - empty env var → None: `test_parse_args_empty_env_license_is_none`
    (`253-259`).
  - all sources absent → None: `test_parse_args_metadata_defaults_none`
    (`216-234`), `test_parse_args_all_sources_absent_stays_none` (`591-604`).
- **Validation-of-non-flag-source** assertions: invalid env email/URL exit code
  2 (`test_main.py:188-213`); malformed git-config email exits 2
  (`606-622`, documents design Decision 7 / Open Risk).

## Cross-Cutting Observations
- Precedence is implemented imperatively as ordered `if … is None:` guards in
  `parse_args()` (`main.py:265-278`), not via a config object or a list of
  source callables — adding a new source means inserting another guard block in
  the right position.
- "Unset" is uniformly represented as `None`; both readers coalesce empty
  strings to `None` (`main.py:166,189`), and validators are only ever applied to
  non-`None` values (`main.py:198-199`).
- Non-flag sources are deliberately funneled through the same validators as
  flags via `_validated_or_error` (`main.py:192-203`) so all sources share one
  validation rule set (README.md:89).
- Constants for env names and git keys are module-level, `_`-prefixed, typed,
  and commented with precedence notes (`main.py:84-96`), matching the
  naming/annotation conventions in `docs/Code Best Practices`.
- Tests patch the SDK/subprocess seam on the defining module object
  (`modernpackage.main.run`, `...Popen`, `..._git_config_default`), never the
  stdlib symbol directly — consistent with the documented testing convention.

## Open Areas
- No per-user config-file reading currently exists anywhere in the source, so
  there is no in-repo precedent for *file* location/path resolution, file
  format, or parser choice — only the env-var and git-config source patterns
  above and the `Path.cwd()` usage (`main.py:303`). `tomllib` is available in
  the stdlib (Python ≥ 3.14) but is not imported.
- The README "Precedence" wording (`README.md:91-96`) and per-flag bullets are
  the existing template for documenting a source ordering, should a new source
  slot into the chain.
