# Research Findings

Scope: CLI metadata-default resolution in `modernpackage/main.py`, its helpers,
the unit tests in `tests/test_main.py`, and the `docs/` descriptions. All
references are `file:line`.

## Q1: Step-by-step sequence populating each field after argparse

### Findings
- `parse_args()` is the single orchestrator (`modernpackage/main.py:290-370`).
- Parsing first: every metadata flag is declared with `default=None`
  (`main.py:306-347`); `parser.parse_args()` at `main.py:348` produces the
  namespace.
- The fill-in happens in three blocks, each guarded by `if <field> is None:`
  (the guard is what prevents a stronger source overwriting a weaker one):
  1. **Environment** — all five fields, `main.py:349-358` (author_name,
     description, license, author_email, repository_url).
  2. **Git config** — only author_name then author_email, `main.py:359-362`.
  3. **Config file** — all five, via `_apply_config_file_defaults(arguments,
     _load_config_file())` at `main.py:363`; the helper repeats the same
     `if … is None` guard per field (`main.py:264-273`).
- Validation runs last on the final resolved value: `_validated_or_error` for
  `author_email` and `repository_url` (`main.py:364-369`).
- Effective order per field = **flag (argparse) > env > git config > config file
  > None**. Because each step only assigns when the value is still `None`, the
  first source to provide a non-`None` value wins; later steps short-circuit.
- The config file is loaded exactly once (`_load_config_file()` called inline at
  `main.py:363`) regardless of how many fields consult it.

## Q2: Helper functions and the shared "unset" convention

### Findings
- Env reader: `_environment_default(variable_name)` —
  `return os.environ.get(variable_name) or None` (`main.py:172-174`). Set-but-empty
  → `None`.
- Git reader: `_git_config_default(key)` (`main.py:177-197`). Runs
  `git config <key>` with `subprocess.run(check=False, capture_output=True,
  text=True)`; returns `None` on `FileNotFoundError` (git absent), on non-zero
  returncode (key unset / failure), and `result.stdout.strip() or None` (empty →
  `None`).
- Config-file reader: `_config_file_default(config, key)` (`main.py:243-253`).
  Returns the value only `if isinstance(value, str) and value`; otherwise `None`
  — so empty strings AND wrong-typed TOML values (int/bool/array/table) coalesce
  to `None`.
- Supporting helpers: `_user_config_path()` (`main.py:200-216`) resolves
  `$XDG_CONFIG_HOME` (empty → `~/.config` fallback, `main.py:208`; `Path.home()`
  RuntimeError → `None`); `_load_config_file()` (`main.py:219-240`) returns `{}`
  on missing file (silent) and prints a stderr notice + `{}` on TOMLDecodeError /
  OSError.
- **Shared convention:** "empty/missing/wrong-typed = unset (`None`)" applied
  uniformly by all three readers (the `or None` / `strip() or None` /
  `isinstance str and value` idioms). Documented as design Decision 5 in code
  comments (`main.py:248-253`, `main.py:206-208`).

## Q3: Which sources back each of the five fields

### Findings
- Env: ALL five fields. Env-var constants `main.py:87-91`; consulted at
  `main.py:349-358`.
- Git config: ONLY author_name (`user.name`) and author_email (`user.email`).
  Keys `main.py:96-97`; consulted at `main.py:359-362`. No git keys exist for
  description / license / repository_url.
- Config file: ALL five fields. Consulted in `_apply_config_file_defaults`
  (`main.py:264-273`) with flat keys `author_name`, `description`, `license`,
  `author_email`, `repository_url`.
- **The asymmetry (git config only for the two author fields) is encoded
  structurally**: there are simply two git lines (`main.py:359-362`) versus five
  env/config lines, rather than a table/loop. So name/email get a 4-level ladder
  (flag > env > git config > config file > None); the other three get a 3-level
  ladder (flag > env > config file > None).
- Documented in code comments `main.py:93-101` and in
  `docs/invocation.md:253-259` (table with "(none)" git column for the latter
  three).

## Q4: How tests verify multi-source competition

### Findings
- Naming pattern: `test_parse_args_<winner>_beats_<loser>` /
  `_overrides_` / `_fills_when_..._absent`. Examples:
  - `test_parse_args_flag_overrides_env_author_email` (`test_main.py:174-183`)
  - `test_parse_args_flag_overrides_env_description` (`test_main.py:249-255`)
  - `test_parse_args_flag_beats_git_config` (`test_main.py:539-556`)
  - `test_parse_args_env_beats_git_config` (`test_main.py:559-575`)
  - `test_parse_args_git_config_fills_when_flag_and_env_absent`
    (`test_main.py:578-593`)
  - `test_parse_args_env_beats_config_file` (`test_main.py:716-727`)
  - `test_parse_args_git_config_beats_config_file` (`test_main.py:730-745`)
  - `test_parse_args_flag_beats_config_file_email` (`test_main.py:774-783`)
  - `test_parse_args_all_sources_absent_stays_none` (`test_main.py:596-608`)
- Fixtures / mocks used:
  - **Env patching:** `monkeypatch.setenv` / `monkeypatch.delenv(raising=False)`
    (`test_main.py:167-171`, `:540-541`).
  - **argv patching:** `patch('sys.argv', [...])` (`test_main.py:104`, etc.).
  - **Git stubbing:** `patch('modernpackage.main._git_config_default')` with a
    `side_effect` lambda keyed on `_GIT_CONFIG_USER_NAME_KEY` /
    `_GIT_CONFIG_USER_EMAIL_KEY` (`test_main.py:544-550`); low-level tests patch
    `modernpackage.main.run` returning `MagicMock(returncode=…, stdout=…)`
    (`test_main.py:515-536`).
  - **Temp config files:** helper `_write_config(tmp_path, body)`
    (`test_main.py:635-638`) writes `tmp_path/modernpackage/config.toml`;
    `_parse_args_with_config` (`test_main.py:641-657`) clears the five env vars,
    sets `XDG_CONFIG_HOME=tmp_path`, and stubs `_git_config_default → None`.
- Competition is asserted both by the winning value AND by verifying the loser
  was never consulted, e.g. `_GIT_CONFIG_USER_NAME_KEY not in [call.args[0] for
  call in git_mock.call_args_list]` (`test_main.py:553-556`, `:573-575`).
- Cross-source validation aborts are tested:
  `test_parse_args_malformed_git_config_email_exits_two` (`test_main.py:611-627`),
  `test_parse_args_invalid_config_email_exits_two` (`test_main.py:786-792`),
  `test_parse_args_invalid_config_url_exits_two` (`test_main.py:795-801`) — all
  assert `SystemExit.code == 2`.

## Q5: Where the ordering is described and how consistent

### Findings
- **Code comments** (consistent, full chain):
  - `main.py:86` "precedence: flag > env > None" (env block header).
  - `main.py:94-95` "precedence: flag > env > git config > None" (git keys).
  - `main.py:99-101` "precedence: flag > env > git config > config file > None"
    (config file).
- **`--help` text (argparse)**: each flag's help only says
  `Defaults to $MODERNPACKAGE_<FIELD>.` (`main.py:308-346`). **It mentions ONLY
  the env var — not git config, not the config file.** `test_parse_args_help_
  advertises_env_vars` (`test_main.py:267-274`) asserts only that env-var names
  appear; it does not check for git/config mentions.
- **docs/** (full chain, consistent with code):
  - `docs/overview.md:9` and `:55` describe `flag > env > git config > config
    file > None` for name/email and `flag > env > config file > None` for the
    rest.
  - `docs/architecture.md:556-588` (esp. the explicit precedence statement at
    `:580`).
  - `docs/invocation.md:249-271` — dedicated "Metadata Defaults Resolution"
    section + table (`:253-259`) + worked examples (`:275-365`).
- **Inconsistencies found:**
  1. `--help` text is narrower than reality — advertises env only, omits git
     config and config file (`main.py:308-346`).
  2. `docs/specification.md` is stale: its CLI section (`specification.md:44-48`)
     documents only `-v` and `package_name` and does NOT mention the metadata
     flags or any precedence — it predates the metadata feature. Its `parse_args`
     line refs (`main.py:18-34`) no longer match.
  3. `docs/invocation.md:421` still states metadata flags are "not yet written to
     `pyproject.toml` (deferred to later V4 work)", which contradicts the
     overview/architecture docs and the actual `_write_package_metadata` wiring
     (see Q6) — this doc paragraph is stale.

## Q6: Where resolved values flow next and how unset values are handled

### Findings
- `main()` passes the namespace fields as keyword args to `init_new_package`
  (`main.py:531-540`): note `package_license=parsed_args.license` (flag attr is
  `license`, parameter is `package_license`).
- `init_new_package(... )` (`main.py:446-521`): after a successful `git clone`
  (`main.py:459-472`) and **before** `just init`, it calls
  `_write_package_metadata(new_package_path, author_name=…, …)`
  (`main.py:474-481`). Order matters: metadata lands in the initial git commit
  (docs/architecture.md:954-959).
- `_write_package_metadata(...)` (`main.py:378-425`): reads the cloned
  `pyproject.toml`; for **each non-`None`** field does a targeted, TOML-escaped
  `str.replace` of a known template literal:
  - author_name → `'Name Surname'` (`main.py:407-408`)
  - author_email → `'email@example.com'` (`main.py:409-410`)
  - description → `'Package configuration example…'` (`main.py:411-415`)
  - repository_url → `'https://github.com/albertas/modernpackage'`
    (`main.py:416-420`)
  - package_license → delegated to `_apply_license` (`main.py:421-422`,
    `_apply_license` at `main.py:428-443`: inserts `license = "<value>"` after
    `readme = "README.md"` and drops the MIT trove classifier).
- **Unset (`None`) handling:**
  - Each substitution is gated by `if <field> is not None:` (`main.py:407-422`),
    so a `None` field leaves its template placeholder untouched (partial
    scaffolding; docs/architecture.md:962-966).
  - The file is rewritten only if a substitution changed it: `if updated !=
    original: pyproject_path.write_text(updated)` (`main.py:424-425`).
  - Missing `pyproject.toml` → prints a stderr notice and returns without raising
    (`main.py:398-404`) — also lets Popen-mocked unit tests pass.
- Escaping: `_toml_escape` escapes `\` then `"` (`main.py:373-375`).
- Tests: `_write_package_metadata` behaviors in `test_main.py:850-942`
  (replaces all fields, None no-op, missing file, quote escaping, license insert,
  None-license keeps classifier).

## Cross-Cutting Observations
- The whole precedence ladder is plain top-to-bottom `if x is None:` assignments
  (`main.py:349-363`, `:264-273`) — no priority table or loop; the source order
  *is* the precedence, and the per-field `None` guard is the only mechanism.
- "Empty/missing/wrong-type = unset" is a single deliberate convention across
  env, git, and config readers (Q2), explicitly cross-referenced in comments as
  "design Decision 5" (`main.py:208`, `:248-253`).
- Validation is source-agnostic: it runs once on the final value
  (`main.py:364-369`), so env/git/config-sourced emails+URLs are validated with
  the same regexes as flags, and any failure exits code 2 via `parser.error`
  (`main.py:286-287`).
- `--license` flag stores to namespace attr `license`; everywhere downstream the
  parameter name becomes `package_license` (`main.py:421-422`, `:452`, `:538`).

## Open Areas
- Git config precedence relative to the config file is implemented for only the
  two author fields by construction; there is no code path or constant that would
  let description/license/repository_url ever read git config — confirmed absent
  (no git keys beyond `main.py:96-97`).
- `docs/specification.md` does not describe metadata sources at all (predates the
  feature), so it cannot be cross-checked for consistency beyond noting it is
  stale.
- Whether the `--help` text's env-only wording is intentional vs. an omission is a
  judgment call not resolvable from code; only the observed fact is reported.
