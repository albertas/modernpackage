# Research Findings

Scope: `modernpackage/main.py` (clone-and-init flow), the template `pyproject.toml`,
the `just init` recipe in `Justfile`, tests in `tests/`, and design records in `docs/`.

## Q1: End-to-end flow of `init_new_package`

### Findings
- Signature & metadata params: `main.py:373-381`. All five metadata kwargs are
  keyword-only, default `None`.
- Params are **immediately discarded**: `del author_name, author_email, description,
  package_license, repository_url` (`main.py:385`) — comment says threaded for "later
  V4 work (writing metadata into pyproject.toml); not yet consumed."
- Target path derivation: `module_name = normalize_module_name(package_name)` then
  `new_package_path = Path.cwd() / module_name` (`main.py:387-388`). Name is normalized
  (`.`/`-` → `_`) so the clone directory uses underscores.
- **Step 1 — git clone** (`main.py:390-403`): `Popen(['git','clone',
  'https://github.com/albertas/modernpackage', new_package_path], ...)`. On
  `returncode != 0`, builds `raw` message, calls `humanize_git_clone_error(stderr_text)`
  (`main.py:53-59`), raises `RuntimeError` (friendly + raw if pattern matched).
- **Step 2 — just init** (`main.py:405-424`): `Popen(['just','init', module_name],
  cwd=new_package_path)`. Wrapped in `try/except FileNotFoundError` → `RuntimeError`
  ("'just' command not found …"). Non-zero exit → `RuntimeError('just init failed …')`.
- **Step 3 — just check** (`main.py:426-443`): `Popen(['just','check'], cwd=new_package_path)`.
  Exit 0 → prints "just check passed", returns 0; else prints failure to stderr, returns 1.
- Order: clone → `just init` → `just check`, all in/against `new_package_path`
  (clone targets it; init and check use `cwd=new_package_path`).
- **`just init` on-disk transforms** (`Justfile:59-73`):
  1. `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'`
     (Linux) / `sed -i ''` (Darwin) — rename token everywhere (`Justfile:61-66`).
  2. `sed -i -e 's/[[:digit:]]+\.[[:digit:]]+\.[[:digit:]]+/0.0.1/g' modernpackage/__init__.py`
     — reset version to `0.0.1` (`Justfile:67`).
  3. `mv modernpackage {{package_name}}` — rename package dir (`Justfile:68`).
  4. `rm -fr .git/ .venv`; `git init -b main`; `git add .`;
     `git commit -m "Initial modern {{package_name}} package setup"` (`Justfile:69-72`).
- The recipe does NOT touch author/email/description/license/URL — only the
  `modernpackage` token and the version string are rewritten.

## Q2: Template `pyproject.toml` structure (`pyproject.toml`)

### Findings
- Author name + email live in `[project].authors`, an array of inline tables:
  `authors = [{name = "Name Surname", email = "email@example.com"}]` (`pyproject.toml:3-5`).
  These are the placeholder values rewritten by no recipe today.
- Description: `[project].description = "Package configuration example using bleeding
  edge toolset."` (`pyproject.toml:6`).
- **License is NOT a dedicated field** — there is no `license = ...` key and no
  `license-files`. It is expressed only as a **trove classifier**:
  `"License :: OSI Approved :: MIT License"` inside `[project].classifiers`
  (`pyproject.toml:9-16`, specifically line 11).
- Repository/project URL: `[project.urls]` table with a single key
  `homepage = "https://github.com/albertas/modernpackage"` (`pyproject.toml:20-21`).
  No `repository`/`source` key exists.
- Other `[project]` keys: `name = "modernpackage"` (`:2`), `readme = "README.md"` (`:7`),
  `requires-python = ">= 3.14"` (`:8`), `dynamic = ["version"]` (`:17`),
  `dependencies = []` (`:18`).
- Because this repo clones itself as the template, this same `pyproject.toml` is the
  file a generated package receives (before `just init`'s `modernpackage`→name sed pass).

## Q3: Metadata from CLI parsing through to scaffolding

### Findings
- `parse_args()` defines flags `--author-name`, `--description`, `--author-email`
  (`type=validate_author_email`), `--license`, `--repository-url`
  (`type=validate_repository_url`), all `default=None` (`main.py:306-347`).
- Namespace attributes produced: `author_name`, `description`, `author_email`,
  `license`, `repository_url` (note attr is `license`, not `package_license`).
- Default resolution in `parse_args()` (in-place on the Namespace):
  env defaults (`main.py:349-358`), then git-config for name/email only
  (`main.py:359-362`), then config-file via `_apply_config_file_defaults`
  (`main.py:363`), then validation of email + URL via `_validated_or_error`
  (`main.py:364-369`).
- `main()` maps Namespace → `init_new_package` kwargs (`main.py:455-462`):
  `package_name=…, author_name=…, author_email=…, description=…,
  package_license=parsed_args.license, repository_url=…`. The `--license`/`.license`
  attribute is renamed to the param `package_license` here.
- Inside `init_new_package`, all five are deleted unused at `main.py:385`; they never
  reach the subprocess calls or any file.

## Q4: Available patterns/dependencies for reading/modifying TOML

### Findings
- Only TOML library imported in code: stdlib `tomllib` (`main.py:6`), used
  **read-only**: `tomllib.load(config_file)` and `tomllib.TOMLDecodeError`
  (`main.py:231-235`). `tomllib` cannot write TOML.
- Read pattern already established: `_load_config_file()` opens the per-user
  `config.toml` in binary mode and parses it (`main.py:219-240`); field extraction
  via `_config_file_default()` coerces non-str/empty to `None` (`main.py:243-253`).
- No TOML **writer** is imported or used anywhere in `modernpackage/` or `tests/`
  (grep: only `tomllib`, plus the `config.toml` filename literal).
- `pyproject.toml` declares **no** TOML dependency (runtime `dependencies = []`
  at `pyproject.toml:18`; `test` extra has no toml lib, `pyproject.toml:27-37`).
- `tomli==2.4.1` and `tomli-w==1.2.0` appear in `requirements-dev.txt:175-180` and
  `uv.lock:1151,1178`, but only as **transitive** deps: `tomli` via deadcode/pip-audit,
  `tomli-w` via pip-audit. They are not direct/declared deps and are not imported.

## Q5: How existing tests exercise the init/scaffolding path

### Findings
- **Unit tests** (`tests/test_main.py`) mock `modernpackage.main.Popen` and assert on
  call arguments — no real subprocess, no real filesystem:
  - `test_init_new_package` asserts `popen_mock.call_count == 3` (`:275-280`).
  - `test_init_new_package_normalizes_name` inspects `call_args_list` for clone target
    name and the `['just','init','my_cool_package']` argv + `cwd` (`:283-295`).
  - `test_init_new_package_runs_just_check` asserts third call is `['just','check']`
    with `cwd` (`:298-305`).
  - Failure paths use `popen_mock.side_effect = [..]` to stage per-step mocks: clone
    failure (`:308-313`), `FileNotFoundError` for just (`:316-323`), just-init failure
    (`:326-336`), check pass/fail reporting (`:463-495`).
  - Mocks set `returncode` and `communicate.return_value = (b'', b'')`.
  - `test_main_with_package_name` asserts `init_new_package` is called with all five
    metadata kwargs = `None`, including `package_license=None` (`:339-362`).
  - Generated **file contents are NOT asserted** in unit tests — only subprocess argv,
    cwd, return codes, and printed messages.
- **e2e test** (`tests/test_e2e.py`, `@pytest.mark.e2e`, excluded by default via
  `addopts … -m 'not e2e'`, `pyproject.toml:40`):
  - Runs **real** `git clone` + `just init` against the **local committed checkout**
    (`REPO_ROOT`), not the GitHub URL, and not via `init_new_package` (`:52-70`).
  - Asserts on-disk results: renamed source dir exists, name has `_` not `-`/`.`
    (`:72-76`), `__init__.py` exists and contains `0.0.1` (`:78-80`).
  - Then runs real `just check` and asserts exit 0 (`:82-83`).
  - Does **not** assert pyproject author/description/license/URL contents.
  - Difference: unit tests verify orchestration/argv with everything mocked; e2e
    verifies the actual template transform and that the scaffold passes `just check`.

## Q6: What design/decision records say about applying metadata

### Findings
- Metadata writing to files is **explicitly deferred**, not yet designed for layout:
  - `docs/invocation.md:421`: flags "are currently threaded through the initialization
    flow but **not yet written to `pyproject.toml`** (that is deferred to later V4 work)."
  - `docs/architecture.md:499`: parameters "are currently **not written to
    `pyproject.toml` or any other files** — that writing is deferred to later V4 work."
  - `docs/architecture.md:580`: kwargs "passed through even though they are not yet
    written to files, establishing the plumbing for later V4 work that will perform the
    actual substitution in `pyproject.toml`."
- **Precedence** (resolved in `parse_args`, documented in `docs/invocation.md:251-261`):
  - author_name / author_email: **flag > env > git config > config file > None**.
  - description / license / repository_url: **flag > env > config file > None**
    (no git-config fallback). Table at `docs/invocation.md:255-259`.
  - Empty env/config values treated as unset (`docs/invocation.md:269`;
    code `_environment_default` `main.py:172-174`, `_config_file_default` `main.py:243-253`).
- Numbered design Decisions referenced in code/docs (relevant ones):
  - Decision 4: absent git default is expected, not an error — no notice
    (`main.py:184`, `docs/architecture.md:356`).
  - Decision 5: empty-as-unset / type coercion for config values (`main.py:248`,
    `docs/architecture.md:408`).
  - Decision 6: degrade gracefully reading config; print notice on malformed
    (`main.py:226`, `docs/architecture.md:395`).
- **No record** specifies how/where each field should land in the generated
  `pyproject.toml` (e.g. `authors` table vs license field vs trove classifier vs
  `[project.urls]` key), nor placeholder-replacement strategy for the existing
  `"Name Surname"` / `"email@example.com"` / homepage placeholders. That layout
  decision is not present in `docs/`.

## Cross-Cutting Observations
- The repo is its own template (self-replication): `init_new_package` clones
  `albertas/modernpackage`; the e2e test clones the local checkout (`main.py:391`,
  `test_e2e.py:62`). Any pyproject change is both tool config and template output.
- License has no first-class field anywhere — only the trove classifier at
  `pyproject.toml:11`; `--license`/`MODERNPACKAGE_LICENSE` is a free string with no
  validation (`main.py:331-338`).
- Attribute/param naming mismatch: CLI/Namespace use `license`; the function param is
  `package_license` (renamed at the `main()` call site, `main.py:459`).
- Only `tomllib` (read) is wired in; writing TOML would need a new capability/dep,
  none currently declared.
- `docs/specification.md` is stale (its `file:line` citations and "single test" /
  cov-fail-under 50 claims predate the current `main.py` and test suite); prefer
  `docs/architecture.md` and `docs/invocation.md` for current behavior.

## Open Areas
- No design/decision record prescribes the target TOML location or placeholder-
  substitution mechanism for author, description, license, or repository URL — only
  that it is "deferred to later V4 work."
- Whether license should become a `[project].license` field/SPDX string vs. remain a
  trove classifier is unspecified in `docs/`.
- No existing test asserts generated `pyproject.toml` metadata contents (unit or e2e).
