# Research Findings

Scope: `modernpackage/` CLI, `pyproject.toml` (hatchling), `Justfile`, `tests/`,
`docs/`. All references are to files under `/home/niekas/tools/modernpackage`.

## Q1: End-to-end scaffolding flow in `main.py`

### Findings
Entry point: `main()` (`main.py:807`) calls `parse_args()` (`main.py:347`), then
dispatches on `--version` vs a positional `package_name`, calling
`init_new_package(...)` (`main.py:712`) inside a `try/except RuntimeError` that
prints to stderr and returns exit code 1 (`main.py:825-827`).

Argument parsing: `parse_args()` builds an `ArgumentParser`, validates
`package_name` via `validate_package_name` (`main.py:183`, PEP 508 shape +
stdlib-shadow rejection), then `_resolve_metadata_defaults` fills unset metadata
fields from env → git config → config.toml in precedence order
(`main.py:310-330`, `_METADATA_FIELDS` at `main.py:148`).

`init_new_package` steps (`main.py:712-804`):
1. `module_name = normalize_module_name(package_name)` (`.`/`-` → `_`,
   `main.py:199`); `new_package_path = Path.cwd() / module_name` (`main.py:724`).
2. `_run_preflight_checks(new_package_path)` (`main.py:683`) — runs 4 checks in
   order: name-valid (no-op lambda), required tools on PATH, target dir absent,
   template remote reachable. First failure raises `RuntimeError` (Q6).
3. If `dry_run`: print plan and return 0 (`main.py:728-738`); no clone happens.
4. **`git clone`** of `_TEMPLATE_REPOSITORY_URL` into `new_package_path` via
   `Popen` (`main.py:740-745`). Non-zero exit → `RuntimeError`, friendly message
   from `humanize_git_clone_error` (`main.py:749-753`).
5. **pyproject metadata rewrite** via `_write_package_metadata` (`main.py:432`,
   called at `main.py:755`): targeted `str.replace` of known template literals
   in the **cloned** `package_path / 'pyproject.toml'` (`main.py:450`). Missing
   file prints a notice and returns without raising (`main.py:452-458`).
6. **`just init <module_name>`** via `Popen` with `cwd=new_package_path`
   (`main.py:765-771`); `FileNotFoundError` → friendly `RuntimeError`
   (`main.py:772-777`); non-zero exit → `RuntimeError` (`main.py:781-783`).
7. **`just check`** via `Popen` with `cwd=new_package_path` (`main.py:785-791`).
   Exit 0 → prints success, `_print_init_summary`, `_print_next_commands`,
   returns 0 (`main.py:794-798`); else prints failure to stderr, returns 1.

What produces the final directory: the `git clone` creates it; `just init`
renames `modernpackage/` → `module_name/` inside it (Q3).

Template-source assumptions: every step assumes the template is a **remote git
repository reachable over the network** at `_TEMPLATE_REPOSITORY_URL`
(`main.py:71`). The reachability probe (`main.py:647`), the clone
(`main.py:741`), and the `repository_url` metadata replacement target
(`main.py:471-474`) all reference that same constant. Nothing reads the template
from the installed package itself.

## Q2: How the wheel/sdist is built and what it contains

### Findings
Build backend: hatchling (`pyproject.toml:45-47`). Build config
(`pyproject.toml:49-54`):
- `[tool.hatch.build] include = ["**/*.py"]`, `exclude = ["tests/**"]`.
- Version source: `[tool.hatch.version] path = "modernpackage/__init__.py"`
  (dynamic version, `pyproject.toml:17` + `53-54`); `__version__ = '0.0.9'`
  (`__init__.py:3`).

`publish` recipe (`Justfile:54-57`): `rm -fr dist/*`, `uv build`, `uv publish`.
Uses `uv build` (which invokes hatchling), not a custom step.

Observed artifact contents (`dist/modernpackage-0.0.9-py3-none-any.whl`):
- `modernpackage/__init__.py`, `modernpackage/main.py`, and the
  `dist-info/` metadata only — **just the two Python source files**.

Observed sdist (`dist/modernpackage-0.0.9.tar.gz`):
- `modernpackage/__init__.py`, `modernpackage/main.py`, `.gitignore`,
  `README.md`, `pyproject.toml`, `PKG-INFO`.

What is NOT packaged into the wheel today: the `Justfile`, `pyproject.toml`,
`README.md`, `docs/`, `.github/`, `.gitignore`, `requirements*.txt`, or any other
template files. The wheel ships only `**/*.py` from the `modernpackage/` package.
Because `include = ["**/*.py"]`, no template tree is bundled inside the
distributed artifact — the scaffold always comes from the remote clone (Q1).

## Q3: What `just init` does, and which steps need a real git tree

### Findings
`init` recipe (`Justfile:59-73`), default `package_name="modernpackage"`:
1. `echo "Initializing ..."` (`Justfile:60`).
2. **Name substitution** (`Justfile:61-66`): `git grep -l 'modernpackage' |
   xargs sed -i 's/modernpackage/{{package_name}}/g'` — Linux and Darwin
   variants. **Requires a git working tree**: `git grep` only lists tracked
   files, so this depends on the clone being a real repo with committed content.
3. **Version reset** (`Justfile:67`): `sed -i ... 's/<x.y.z>/0.0.1/g'
   modernpackage/__init__.py`. Operates on a fixed path; no git dependency.
   (Mirrored in code as `_RESET_VERSION = '0.0.1'`, `main.py:514`.)
4. **Directory rename** (`Justfile:68`): `mv modernpackage {{package_name}}`.
   Filesystem op; no git dependency. Note: renames the literal `modernpackage`
   dir — after step 2 substituted file *contents* but not the dir name.
5. **Remove `.git`/`.venv`** (`Justfile:69`): `rm -fr .git/ .venv`. Discards the
   cloned git history.
6. **`git init -b main .`** (`Justfile:70`): fresh repo.
7. **`git add .`** (`Justfile:71`) + **`git commit -m ...`** (`Justfile:72`):
   first commit. Requires git identity (e2e supplies it via env, `test_e2e.py:30`).
8. `echo "Finished ..."` with next-steps hint (`Justfile:73`).

Steps that depend on a real git working tree: **step 2** (`git grep` needs
tracked files) is the strongest dependency. Steps 6–7 create/commit a repo but
don't require the *source* to have been a git tree. Steps 3–5 are plain
filesystem/sed ops.

## Q4: Runtime file location / read patterns

### Findings
- `Path.cwd()`: `init_new_package` computes the target as `Path.cwd() /
  module_name` (`main.py:724`). The CLI scaffolds relative to the **invocation
  working directory**, not the package install location.
- `Path(__file__)`: **not used in `main.py`**. The only `Path(__file__)` usage is
  in the test (`test_e2e.py:27`, `REPO_ROOT = Path(__file__).resolve().parent.parent`).
- `importlib.resources`: **not used anywhere** (no occurrences). No mechanism
  currently reads package-internal data/resources.
- `tomllib`: imported (`main.py:7`); used only to read the **per-user config
  file** `_load_config_file()` (`main.py:273-294`) at `_user_config_path()`
  (`main.py:254`, `$XDG_CONFIG_HOME` or `~/.config/modernpackage/config.toml`).
  The cloned `pyproject.toml` is read/written as **plain text** via
  `read_text()/write_text()` + `str.replace`, not parsed (`main.py:450-479`).
- Cloned-template paths are always derived from `new_package_path` /
  `package_path` (e.g. `package_path / 'pyproject.toml'`, `main.py:450`), i.e.
  relative to the freshly cloned directory under `cwd`.
- Package-internal path referencing: the only package-internal read is
  `from modernpackage import __version__` (`main.py:17`) for `--version`. No code
  reads files shipped inside the installed package.

## Q5: How tests mock/exercise clone + init

### Findings
Unit tests (`tests/test_main.py`):
- Mock the subprocess seams on the module object: `patch('modernpackage.main.Popen')`
  and `patch('modernpackage.main.run')` (`test_main.py:290-291`). `run` is the
  preflight `git config`/`ls-remote` seam; `Popen` is the clone/init/check seam.
- `popen_mock.return_value.communicate.return_value = (b'', b'')` and
  `returncode = 0` simulate success (`test_main.py:294-295`).
- `test_init_new_package` asserts **3 `Popen` calls** (clone, `just init`,
  `just check`) (`test_main.py:297`).
- `test_init_new_package_normalizes_name`: clone target's basename is
  `my_cool_package`; second call is `['just','init','my_cool_package']` with
  `cwd == Path.cwd()/'my_cool_package'` (`test_main.py:310-316`).
- `test_init_new_package_runs_just_check`: third call is `['just','check']`
  with matching `cwd` (`test_main.py:328-330`).
- Failure paths: clone non-zero → `RuntimeError 'git clone failed with exit code
  1'` (`test_main.py:333-342`); `just` missing → `Popen.side_effect=[clone,
  FileNotFoundError]` → `RuntimeError` matching `just.*install`
  (`test_main.py:345-356`). No real clone happens in unit tests, which is why
  `_write_package_metadata` tolerates a missing pyproject (`main.py:452-458`).

E2E test (`tests/test_e2e.py`, marker `e2e`, excluded by default
`pyproject.toml:40`):
- Skips unless `git`/`just`/`uv` on PATH (`test_e2e.py:55-57`).
- Clones the **local committed checkout** `REPO_ROOT`, not the GitHub URL
  (`test_e2e.py:27,63`) — module docstring notes this deviation
  (`test_e2e.py:1-15`).
- Calls `main._write_package_metadata(...)` directly (`test_e2e.py:66-73`), then
  runs real `just init <module>` with git identity env (`test_e2e.py:75-80`),
  then `just check` (`test_e2e.py:92`).
- Asserts on a freshly scaffolded package: renamed source dir exists
  (`destination/module_name` is a dir, `test_e2e.py:82-83`); module name has no
  `-`/`.` and contains `_` (`test_e2e.py:84-86`); `__init__.py` exists and
  contains `0.0.1` (`test_e2e.py:88-90`); `just check` returns 0
  (`test_e2e.py:92-93`); pyproject contains substituted metadata and no template
  placeholders / MIT classifier (`test_e2e.py:95-103`).

## Q6: Where the template URL / config lives, and coupled behavior

### Findings
Single source-of-truth constant: `_TEMPLATE_REPOSITORY_URL =
'https://github.com/albertas/modernpackage'` (`main.py:71`). Referenced by:
- Reachability probe `_verify_template_remote_reachable` → `git ls-remote
  <url>` with `_REMOTE_REACHABILITY_TIMEOUT_SECONDS = 10` (`main.py:647-680`,
  constant at `main.py:75`).
- The actual clone `['git','clone', url, ...]` (`main.py:741`).
- `repository_url` metadata replacement target in `_write_package_metadata`
  (`main.py:471-474`) — the cloned pyproject's `homepage` URL
  (`pyproject.toml:21`) is rewritten only because it equals this constant.
- Dry-run plan text `clone {url} into {target}` (`main.py:551`).

Related error classification: `humanize_git_clone_error` (`main.py:78-84`) maps
`_GIT_CLONE_ERROR_MESSAGES` patterns (`main.py:20-52`) — unreachable / not found
/ auth / dir-exists / fs-permission — used by both the probe (`main.py:678`) and
the clone failure path (`main.py:751`).

Docs coupled to clone-from-remote:
- `docs/invocation.md` describes the URL cloned (`:74,:147`), the `ls-remote`
  probe with 10s timeout (`:208`), and clone failure modes (`:287-340`).
- `docs/specification.md` shows `git clone albertas/modernpackage` in the flow
  diagram (`:27,:57`).
- `docs/overview.md` describes `_verify_template_remote_reachable` (`:58`).

Other behavior coupled to the remote approach: the preflight checklist's
"template remote reachable" check (`main.py:700`) and the dry-run network probe
(it still runs preflight including the network probe before printing the plan,
`main.py:726-738`; documented at `docs/invocation.md:87`). The `git init`/clean
in `just init` (`Justfile:69`) assumes a `.git` exists from the clone.

## Cross-Cutting Observations
- The template is always sourced over the network from one constant
  (`main.py:71`); nothing reads a template bundled in the installed package, and
  `importlib.resources` is unused (Q2, Q4).
- The wheel ships only `modernpackage/*.py` (`include=["**/*.py"]`,
  `pyproject.toml:50`); the sdist additionally has `README.md`, `pyproject.toml`,
  `.gitignore` (Q2).
- Version is duplicated/coupled by convention: `__init__.py:3` (hatch source),
  `Justfile:67` (sed reset to `0.0.1`), and `_RESET_VERSION` (`main.py:514`,
  comment explicitly notes the coupling to `Justfile:67`).
- The cloned `pyproject.toml` is manipulated as text via known-literal
  `str.replace` (`main.py:460-497`), not parsed; template placeholders are
  `'Name Surname'`, `'email@example.com'`, the description string, the homepage
  URL, and the MIT trove classifier.
- `just init`'s name substitution relies on `git grep` over a real working tree
  (`Justfile:62,65`), the strongest git-tree dependency in the flow (Q3).

## Open Areas
- No existing mechanism reads template files from inside the installed package
  (no `importlib.resources`, no package-data config). Whether hatchling could
  bundle a template tree is a packaging question not answered by current code;
  current `[tool.hatch.build]` includes only `**/*.py` (`pyproject.toml:50`).
- `just init` operates on the literal `modernpackage/` directory and `git grep`
  for the literal string `modernpackage` (`Justfile:62-68`); how it would behave
  if the template were materialized from a bundled resource rather than a clone
  is not exercised by any current test.
