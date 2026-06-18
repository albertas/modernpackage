# Research Findings

Scope: the scaffolding/initialization machinery in `modernpackage/`, the
`Justfile`, `tests/`, `pyproject.toml`, `README.md`, and `docs/`. All references
are to the repo root `/home/niekas/tools/modernpackage/`.

## Q1: How does the package-initialization flow work end to end?

### Findings — `init_new_package` (`modernpackage/main.py:712-804`)
Signature accepts `package_name` plus keyword metadata fields and `dry_run`
(`main.py:712-721`). Steps in order:
1. `module_name = normalize_module_name(package_name)`; `new_package_path =
   Path.cwd() / module_name` (`main.py:723-724`).
2. `_run_preflight_checks(new_package_path)` (`main.py:726`) — runs four checks
   (see Q3/below) and prints a checklist.
3. If `dry_run`: `_print_dry_run_plan(...)` then `return 0` — no clone/subprocess
   (`main.py:728-738`).
4. `Popen(['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path], ...)`,
   `communicate()`; on non-zero returncode, `humanize_git_clone_error` maps
   stderr to a friendly message and raises `RuntimeError` (`main.py:740-753`).
5. `_write_package_metadata(new_package_path, ...)` rewrites cloned
   `pyproject.toml` placeholders (`main.py:755-762`).
6. `Popen(['just', 'init', module_name], cwd=new_package_path, ...)`; wraps
   `FileNotFoundError` ("just not found"); non-zero raises `RuntimeError`
   (`main.py:764-783`).
7. `Popen(['just', 'check'], cwd=new_package_path, ...)`; on 0 prints
   "just check passed", `_print_init_summary`, `_print_next_commands`, returns 0;
   on non-zero prints failure to stderr, returns 1 (`main.py:785-804`).

### Findings — `init` recipe (`Justfile:59-73`)
Parameter `package_name="modernpackage"` (`Justfile:59`). Applies, to the cloned
copy:
- **Rename**: `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'`
  (Linux `Justfile:61-63`; Darwin variant `Justfile:64-66`).
- **Version reset**: `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g'
  modernpackage/__init__.py` (`Justfile:67`).
- **Directory move**: `mv modernpackage {{package_name}}` (`Justfile:68`).
- **Git re-init**: `rm -fr .git/ .venv`, `git init -b main .`, `git add .`,
  `git commit -m "Initial modern {{package_name}} package setup"`
  (`Justfile:69-72`).
- Final echo of next step `cd {{package_name}} && just check` (`Justfile:73`).

Note: the directory `mv` uses the raw `{{package_name}}` (with `-`/`.`), but
`init_new_package` passes the *normalized* `module_name` as the recipe argument
(`main.py:766`), so the moved directory matches the normalized name.

## Q2: Module-level structure of `modernpackage/main.py`

### Findings — constants (`main.py:19-129`)
`_GIT_CLONE_ERROR_MESSAGES` (`:20-52`), `_REQUIRED_TOOLS` (`:56`),
`_TOOL_INSTALL_HINTS` (`:62-66`), `_TEMPLATE_REPOSITORY_URL` (`:71`),
`_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`:75`), `_PACKAGE_NAME_RE` (`:89-92`),
`_DISALLOWED_CHAR_RE` (`:96`), `_STDLIB_MODULE_NAMES` (`:101`), `_EMAIL_RE`
(`:105`), `_REPOSITORY_URL_RE` (`:108`), five `_*_ENV` metadata env names
(`:112-116`), two `_GIT_CONFIG_USER_*_KEY` (`:121-122`), config-file constants
`_CONFIG_DIR_NAME`/`_CONFIG_FILE_NAME`/`_XDG_CONFIG_HOME_ENV` (`:127-129`),
output headers + `_RESET_VERSION='0.0.1'` (`:510-516`).

### Findings — dataclasses
- `_MetadataField` (`@dataclass(frozen=True)`, `:132-158`) with the
  `_METADATA_FIELDS` tuple driving metadata default resolution.
- `PreflightCheck` (`@dataclass(frozen=True)`, `:500-507`): `label` + `run`
  callable.

### Findings — functions & dependencies
- Validation/normalization: `humanize_git_clone_error` (`:78`),
  `_explain_invalid_package_name` (`:161`), `validate_package_name` (`:183`, uses
  `_PACKAGE_NAME_RE`, `normalize_module_name`, `_STDLIB_MODULE_NAMES`),
  `normalize_module_name` (`:199`), `validate_author_email` (`:210`),
  `validate_repository_url` (`:218`).
- Metadata default resolution: `_environment_default` (`:226`),
  `_git_config_default` (`:231`), `_user_config_path` (`:254`),
  `_load_config_file` (`:273`), `_config_file_default` (`:297`),
  `_resolve_metadata_defaults` (`:310`), `_validated_or_error` (`:333`).
- CLI: `parse_args` (`:347`, calls `_resolve_metadata_defaults` +
  `_load_config_file` + `_validated_or_error`).
- pyproject rewrite: `_toml_escape` (`:427`), `_write_package_metadata`
  (`:432`), `_apply_license` (`:482`).
- Output formatters: `_format_check_line` (`:519`), `_format_dry_run_plan`
  (`:525`)/`_print_dry_run_plan` (`:564`), `_format_init_summary`
  (`:588`)/`_print_init_summary` (`:603`), `_format_next_commands`
  (`:608`)/`_print_next_commands` (`:618`).
- Preflight: `_verify_required_tools` (`:623`), `_verify_target_directory_absent`
  (`:637`), `_verify_template_remote_reachable` (`:647`), `_run_preflight_checks`
  (`:683`).
- Orchestration: `init_new_package` (`:712`), `main` (`:807`, dispatches on
  `--version` / `package_name`, catches `RuntimeError`).
- Imports `__version__` from `modernpackage` (`main.py:17`).

### Findings — `modernpackage/__init__.py`
Three lines: module docstring + `__version__ = '0.0.9'` (`__init__.py:1-3`). No
other exports. The version is the hatch dynamic-version source
(`pyproject.toml:53-54`) and the `sed` reset target (`Justfile:67`).

## Q3: `check` target composition & pyproject config

### Findings — `Justfile`
`check: check-format check-lint check-complexity check-typecheck test audit`
(`Justfile:52`). Each gate (all depend on `sync` which runs
`uv pip sync requirements-dev.txt` + `uv pip install -e .[test]`, `Justfile:9-11`):
- `check-format` → `ruff format --check modernpackage tests` (`Justfile:28-29`).
- `check-lint` → `ruff check modernpackage tests` (`Justfile:31-32`).
- `check-complexity` → `ruff check --select C901 modernpackage tests`
  (`Justfile:34-35`).
- `check-typecheck` → `mypy modernpackage tests` (`Justfile:37-38`).
- `test` → `pytest -n "$(nproc --ignore=1)" {{args}}` (`Justfile:13-14`).
- `audit` → `pip-audit --skip-editable` (`Justfile:40-41`).
- `deadcode` gate is commented out (`Justfile:43-44, 52`).

### Findings — `pyproject.toml`
- pytest: `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0
  -m 'not e2e'"` (`:40`); marker `e2e` declared (`:41-43`). So the default suite
  excludes e2e and fails under 95% coverage.
- Coverage threshold 95.0% on `modernpackage` (`:40`). `test-e2e` recipe runs
  `pytest -m e2e --no-cov` (`Justfile:16-17`).
- Entry-point scripts: `modernpackage` and `mp` both → `modernpackage.main:main`
  (`:23-25`).
- ruff: `line-length = 88` (`:57`), single quotes (`:60, 63`), `select=["ALL"]`
  with four ignores (`:66-73`), tests ignore `S101`/`D` (`:76`), mccabe
  `max-complexity = 8` (`:78-79`).
- mypy: `strict = true`, `python_version = "3.14"` (`:81-89`).
- Build: hatchling, version path `modernpackage/__init__.py` (`:45-54`).
- `requires-python = ">= 3.14"` (`:8`).

Note: `CLAUDE.md`/Code-Best-Practices mention line-length 120, complexity ≤10,
Python 3.11 — the live `pyproject.toml` actually uses 88, 8, and 3.14.

## Q4: Organization of `tests/`

### Findings — `tests/test_main.py` (~1413 lines, unit tests, mocked)
Imports from `modernpackage.main` (`test_main.py:10-33`): `_GIT_CONFIG_USER_EMAIL_KEY`,
`_GIT_CONFIG_USER_NAME_KEY`, `_REQUIRED_TOOLS`, `_config_file_default`,
`_format_dry_run_plan`, `_format_init_summary`, `_format_next_commands`,
`_git_config_default`, `_load_config_file`, `_user_config_path`,
`_verify_required_tools`, `_verify_target_directory_absent`,
`_verify_template_remote_reachable`, `_write_package_metadata`,
`humanize_git_clone_error`, `init_new_package`, `main`, `normalize_module_name`,
`parse_args`, `validate_author_email`, `validate_package_name`,
`validate_repository_url`.
- Flat `def test_*` functions, no classes. Groups: `main()`/version
  (`:36-46, 505-592, 1357-1374`), name validation (`:61-108`), `parse_args`
  flags/env/git-config/config-file precedence (`:111-286, 833-1095`),
  `init_new_package` happy + failure paths (`:288-373, 631-761`), preflight
  checks (`:376-502, 681-806`), `humanize_git_clone_error` (`:595-629`),
  metadata write (`:1144-1235`), dry-run (`:1334-1413`).
- Patches the SDK seam on `modernpackage.main`: `Popen`, `run`,
  `ArgumentParser`, `_git_config_default`, `shutil.which`, `print`, `Path.home`
  (per analysis; e.g. `popen_mock.side_effect` sequences, `call_count` asserts).
- Helpers: `_write_config` (`:929`), `_parse_args_with_config` (`:935-951`),
  `_seed_pyproject` (`:1137-1141`); no module constants or fixtures beyond these.

### Findings — `tests/test_e2e.py` (104 lines, `@pytest.mark.e2e`)
- Imports `from modernpackage import main` and `normalize_module_name`
  (`test_e2e.py:24-25`). Constants `REPO_ROOT`, `REQUIRED_TOOLS`,
  `_GIT_IDENTITY_ENV` (`:27-35`); helper `_run` (`:38-50`).
- `test_scaffolded_package_passes_check` (`:53-104`): clones the **local
  committed checkout** (not the GitHub URL), calls `main._write_package_metadata`
  directly, runs `just init scaffold_check_pkg`, then `just check`
  (`:63-93`). Asserts: cloned moved source dir exists with `_` (no `-`/`.`)
  (`:82-86`); `__init__.py` exists and contains `0.0.1` (`:88-90`); `just check`
  returncode 0 (`:92-93`); `pyproject.toml` contains the substituted author/
  email/description/`license = "Apache-2.0"` and *omits* the MIT classifier and
  the `Name Surname`/`email@example.com`/template-description placeholders
  (`:95-103`). Skips if `git`/`just`/`uv` absent (`:55-57`).

## Q5: README.md and docs/ on the init flow & generated package

### Findings
- `README.md`: invocation `modernpackage <name>` / `mp <name>` (`README.md:10-11`),
  preflight + dry-run + post-init summary output samples (`:7-55`), "After
  Initialization" workflow (`:237-257`), backlog referencing old behavior
  (`:280-322`). States `just init` renames `modernpackage/ -> my_package/` and
  resets version to `0.0.1` (`README.md:53`).
- `docs/overview.md:7-67` narrates the whole flow (preflight, normalization,
  metadata flags, `just init` recipe, `just check`, summary); `:61` describes
  metadata as targeted TOML-escaped `str.replace` before `just init`.
- `docs/specification.md:53-68` "Package-init flow" documents `init_new_package`
  steps and the `just init` recipe; `:113-131` lists the generated package
  structure (`<name>/__init__.py` reset to `0.0.1`, `<name>/main.py`, `tests/`,
  `pyproject.toml`, `Justfile`, requirements files, `uv.lock`, CI files,
  `README.md`, `BACKLOG.md`); `:15` both scripts route to `main:main`.
- `docs/data_flows.md:1-188` traces all steps (args → preflight → dry-run →
  clone → metadata write → just init → just check → error handling).
- `docs/invocation.md:45-358` documents dry-run/success/failure paths; `:146-165`
  describes generated-package contents and the success summary block.
- `docs/architecture.md` covers init-related constants and every private init
  helper (e.g. `_RESET_VERSION='0.0.1'`, preflight functions, metadata writers).

The generated package, per docs, contains: all template source files renamed
from `modernpackage`, version `0.0.1`, a fresh single-commit git repo, optional
substituted pyproject metadata, validated by `just check`.

## Q6: Files carried into a cloned copy & those referenced/rewritten

### Findings
`init_new_package` clones `_TEMPLATE_REPOSITORY_URL =
'https://github.com/albertas/modernpackage'` (`main.py:71, 741`), i.e. the
committed GitHub template, not the local tree. The committed file set
(`git ls-files`) carried into a clone includes: `modernpackage/__init__.py`,
`modernpackage/main.py`, `pyproject.toml`, `Justfile`, `README.md`,
`BACKLOG.md`, `requirements.txt`, `requirements-dev.txt`, `uv.lock`,
`tests/__init__.py`, `tests/test_main.py`, `tests/test_e2e.py`, `docs/*`,
`.github/workflows/check-modernpackage-on-python314.yml`, `.gitlab-ci.yml`,
`.gitignore`, plus repo-management files (`lifecycle_state.yml`, `metrics.yml`,
`errors/`, `issues/`, `workspace/`).

Referenced/rewritten by the init flow:
- `pyproject.toml` — `_write_package_metadata` (`main.py:432-479`) replaces
  literals `Name Surname` (`:462`), `email@example.com` (`:464`), the template
  description (`:466-469`), `_TEMPLATE_REPOSITORY_URL` (`:470-474`), and license
  via `_apply_license` which inserts `license = "..."` after `readme = ...` and
  drops the MIT trove classifier (`:482-497`). Current template literals confirmed
  at `pyproject.toml:4` (`Name Surname`/`email@example.com`), `:6` (description),
  `:11` (MIT classifier), `:21` (homepage URL).
- `modernpackage/__init__.py` — `Justfile:67` `sed` resets the version to
  `0.0.1`.
- Package directory `modernpackage/` — `Justfile:68` `mv` to the new name; all
  `modernpackage` string occurrences across grep-matched files are sed-replaced
  (`Justfile:61-66`).
- `.git/` and `.venv` are removed and git is re-initialized (`Justfile:69-72`).

## Cross-Cutting Observations
- The flow is split across two layers: Python orchestrator (`main.py`) drives
  subprocesses; the `just init` recipe (`Justfile:59-73`) performs in-tree
  string/dir mutation. They are coupled by convention — `_RESET_VERSION`
  (`main.py:514`) mirrors `Justfile:67`, noted in the code comment.
- `_TEMPLATE_REPOSITORY_URL` is used in three places: reachability probe
  (`main.py:657`), clone (`:741`), and as a metadata-replacement target (`:472`).
- The default `pytest` suite excludes `e2e` and enforces 95% coverage; e2e runs
  separately with `--no-cov` (`pyproject.toml:40`, `Justfile:16-17`).
- `init_new_package` also runs `just check` inside the new package as a
  post-scaffold validation gate, returning 1 on failure (`main.py:785-804`).

## Open Areas
- The questions are fully answerable from the repo. One nuance: the e2e test
  clones the *local* checkout while production code clones the *GitHub* URL
  (`test_e2e.py:8-13`); both exercise the same `just init` recipe and metadata
  writer.
- `CLAUDE.md` style notes (line-length 120, complexity 10, Python 3.11) diverge
  from the live `pyproject.toml` values (88, 8, 3.14) — noted, not resolved.
