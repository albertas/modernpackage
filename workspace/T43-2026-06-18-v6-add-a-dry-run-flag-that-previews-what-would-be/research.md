# Research Findings

All references are to `modernpackage/main.py` unless otherwise noted.

## Q1: Full sequence of operations in `init_new_package`

`init_new_package` is defined at `main.py:602-679`. Order of operations:

1. **Compute paths (no disk effect)** — `module_name = normalize_module_name(package_name)` (`main.py:612`); `new_package_path = Path.cwd() / module_name` (`main.py:613`).
2. **Preflight checks (read-only)** — `_run_preflight_checks(new_package_path)` (`main.py:615`). See Q5. These only probe; they never create/modify/rename files. Any failure raises `RuntimeError` *before* any subprocess that mutates disk.
3. **`git clone` (creates directory tree)** — `Popen(['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path], ...)` (`main.py:617-622`). First on-disk mutation: creates `new_package_path` and populates it with the cloned template. Non-zero exit raises `RuntimeError` with a humanized message (`main.py:626-630`).
4. **Metadata rewrite (modifies a file)** — `_write_package_metadata(...)` (`main.py:632-639`) edits the cloned `pyproject.toml` in place. See Q3.
5. **`just init` (renames/transforms in-place)** — `Popen(['just', 'init', module_name], cwd=new_package_path, ...)` (`main.py:642-648`). This is what renames the package directory and rewrites string occurrences (see Q2). `FileNotFoundError` → `RuntimeError` (`main.py:649-654`); non-zero exit → `RuntimeError` (`main.py:658-660`).
6. **`just check` (no scaffolding mutation; validation)** — `Popen(['just', 'check'], cwd=new_package_path, ...)` (`main.py:662-669`). Return code drives the function's return value (0 success / 1 failure) and the printed summary (`main.py:671-679`).

The two `_verify_*` checks that touch external state (`run(['git', 'ls-remote', ...])` and `shutil.which`) run during step 2, strictly before any clone.

## Q2: Subprocess commands and their filesystem side effects

- **`git ls-remote <url>`** — preflight reachability probe via `run(...)` with `timeout=_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (=10, `main.py:75`) at `main.py:546-552`. No filesystem effect.
- **`git config <key>`** — `_git_config_default` (`main.py:241-246`), read-only, used during `parse_args` default resolution.
- **`git clone <template_url> <dest>`** (`main.py:617-622`) — creates `dest` directory and writes the full committed template into it.
- **`just init <module_name>`** (`main.py:642-648`) — defined in `Justfile:55-69` (recipe `init`). Side effects inside the clone:
  - `git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'` — replaces every occurrence of the literal `modernpackage` with the new name across tracked files (`Justfile:57-62`, Linux/Darwin branches).
  - `sed -i ... 's/<x.y.z>/0.0.1/g' modernpackage/__init__.py` — resets the version to `0.0.1` (`Justfile:63`).
  - `mv modernpackage {{package_name}}` — **renames the package source directory** (`Justfile:64`).
  - `rm -fr .git/ .venv` — removes the cloned git history and any venv (`Justfile:65`).
  - `git init -b main .`, `git add .`, `git commit -m "Initial modern {{package_name}} package setup"` — re-initializes a fresh repo and commits (`Justfile:66-68`).
- **`just check`** (`main.py:662-669`) — `Justfile:48` chains `check-format check-lint check-complexity check-typecheck test audit`; runs ruff/mypy/pytest/pip-audit. Validation only.

E2e test (`tests/test_e2e.py:53-103`) confirms `just init` renames `modernpackage` → `module_name` (asserts `source_dir = destination / module_name` is a dir at `:82-83`) and sets version `0.0.1` (`:90`).

## Q3: How `_write_package_metadata` decides what to change

Defined at `main.py:426-491`. It reads the cloned `pyproject.toml` (`main.py:444-446`). Missing file → prints notice to stderr and returns without raising (`main.py:447-452`). Each non-None field is a targeted `str.replace` of a known template literal, value passed through `_toml_escape` (`main.py:421-423`, escapes `\` then `"`):

- `author_name` → replaces literal `Name Surname` (`main.py:455-456`).
- `author_email` → replaces literal `email@example.com` (`main.py:457-458`).
- `description` → replaces literal `Package configuration example using bleeding edge toolset.` (`main.py:459-463`).
- `repository_url` → replaces literal `_TEMPLATE_REPOSITORY_URL` = `https://github.com/albertas/modernpackage` (`main.py:464-468`, constant at `main.py:71`).
- `package_license` → `_apply_license` (`main.py:469-470`, helper at `main.py:476-491`): inserts `license = "<value>"` after `readme = "README.md"` and deletes the `    "License :: OSI Approved :: MIT License",\n` classifier line.

None fields are skipped (left as template literal). The file is rewritten **only if** `updated != original` (`main.py:472-473`). These are plain literal substitutions, not placeholder tokens. Tests: `tests/test_main.py:1104-1196`.

## Q4: How CLI flags are defined and threaded

Defined in `parse_args` (`main.py:347-418`) using `ArgumentParser` (no subparsers):

- `-v/--version` — `action='store_true', default=False` (`main.py:350-356`). The only boolean/store-true flag.
- `package_name` — positional, `nargs='?'`, `type=validate_package_name` (`main.py:357-362`).
- `--author-name`, `--description`, `--license` — free strings, `default=None`, no validator (`main.py:363-399`).
- `--author-email` — `type=validate_author_email`, `default=None` (`main.py:381-390`).
- `--repository-url` — `type=validate_repository_url`, `default=None` (`main.py:400-409`).

Conventions: every metadata flag defaults to `None` (a sentinel meaning "unset", enabling the env→git→config fallback chain in `_resolve_metadata_defaults`, `main.py:310-330`); help text spells out the full precedence chain (e.g. `main.py:364-370`). `store_true` only used for `--version`. Hyphenated flag names map to underscored Namespace attrs (`--author-name`→`author_name`).

Threading: `parse_args()` → `main()` (`main.py:684`). `main` branches: `version` prints and returns (`main.py:686-687`); else if `package_name` truthy, calls `init_new_package(...)` mapping `parsed_args.license` → keyword `package_license` (note rename, `main.py:696`) and passing the other five fields by keyword (`main.py:691-698`). `RuntimeError` is caught, printed to stderr, returns 1 (`main.py:699-701`). `init_new_package` signature uses keyword-only args with `None` defaults (`main.py:602-610`). Test of full threading: `tests/test_main.py:502-525`.

## Q5: User-facing output conventions (stdout vs stderr)

- **stdout (success/progress):** preflight header `Preflight checks:` (`_PREFLIGHT_HEADER`, `main.py:504`; printed `main.py:592`); per-check lines via `_format_check_line` (`main.py:507-510`): `  {marker:<6} {label}` — two-space indent, marker `[ok]` or `[FAIL]` left-padded to 6 chars so labels align. Success summary `just check passed — {module} scaffold is valid.` (`main.py:672`). Version string (`main.py:687`).
- **stderr (failures/notices):** `just check failed ...` (`main.py:674-678`); missing `pyproject.toml` notice (`main.py:448-451`); unreadable config notice (`main.py:290-293`); top-level `RuntimeError` print in `main` (`main.py:700`).
- **Checklist mechanics:** `_run_preflight_checks` (`main.py:573-599`) builds the registry per-call (so the directory check closes over `target_path`), prints the header, then iterates printing `[ok]` after each passing check; on `RuntimeError` it prints the `[FAIL]` line and re-raises, so later checks' lines never appear. Checks in order: `package name valid` (always-pass `lambda`), `required tools on PATH (git, just, uv)`, `target directory available`, `template remote reachable` (`main.py:580-591`).
- **Error message format:** failures combine a friendly line + blank line + raw detail, e.g. `f'{friendly}\n\n{raw}'` (`main.py:629`, `559`, `569`). `humanize_git_clone_error` (`main.py:78-84`) maps known stderr patterns to friendly text; unknown → None. Tool-missing errors append per-tool install hint URLs (`_verify_required_tools`, `main.py:513-524`).

Exact expected stdout asserted in `tests/test_main.py:641-665` and `:724-766`.

## Q6: How the flow and subprocess interactions are tested

**Unit tests (`tests/test_main.py`, 1286 lines):** No `e2e` marker → default run (`pyproject.toml:40` adds `-m 'not e2e'`). Patterns:
- Patch the SDK seam on the module object: `patch('modernpackage.main.Popen')` and `patch('modernpackage.main.run')` together (e.g. `:286-294`). `Popen` mock sets `.returncode` and `.communicate.return_value = (b'', b'')`; `run` mock returns `MagicMock(returncode=0, stderr='')` to make the `ls-remote` preflight pass.
- Multi-step flows use `popen_mock.side_effect = [git_clone_mock, just_init_mock, just_check_mock]` to script per-call behavior (`:668-684`); single-behavior tests use `popen_mock.return_value`.
- Call assertions inspect `popen_mock.call_args_list` for command/cwd (`:307-313`, `:325-327`) and assert `popen_mock.call_count` (== 3 happy path `:294`; == 0 when a preflight aborts `:385`).
- `shutil.which` patched via `side_effect` function to simulate missing tools (`:373-385`).
- `parse_args` tested by patching `sys.argv` (`:108-118`); `main` tested by patching `modernpackage.main.ArgumentParser` and `init_new_package` (`:502-525`).
- Fixtures: built-in `monkeypatch` (env vars, `chdir`), `tmp_path`, `capsys`. Seed helpers prefixed `_`: `_write_config` (`:889`), `_parse_args_with_config` (`:895`), `_seed_pyproject` (`:1097`, copies the real `pyproject.toml`). `print` patched directly (`patch('modernpackage.main.print')`) to inspect output (`:546-557`).

**E2e test (`tests/test_e2e.py`):** single test `test_scaffolded_package_passes_check` marked `@pytest.mark.e2e` (`:53`). It does NOT mock — it runs real `git clone` (from local `REPO_ROOT`, not the GitHub URL), real `_write_package_metadata`, real `just init`, real `just check` via a `subprocess.run(..., check=False, capture_output=True, text=True)` helper `_run` (`:38-50`). Skips when required tools absent (`:55-57`). Marker registered at `pyproject.toml:41-43`; run via `just test-e2e` (`Justfile:14-15`, uses `-m e2e --no-cov`).

## Cross-Cutting Observations

- **Two subprocess seams:** module-level `run` (preflight/`git config`, with `capture_output`/`timeout`) and `Popen` (clone/init/check, with `PIPE` + `.communicate()`). Both imported from `subprocess` at `main.py:11` and patched on `modernpackage.main`.
- **Graceful boundary degradation vs loud invariants:** external/process boundaries return `None` or print notices (`_git_config_default`, `_load_config_file`, missing `pyproject.toml`); scaffolding failures raise `RuntimeError` caught once in `main`.
- **Metadata precedence chain:** flag > env > git config (author only) > config file > None, encoded in `_METADATA_FIELDS` (`main.py:148-158`) and applied by `_resolve_metadata_defaults`.
- **Name normalization** (`.`/`-` → `_`) is shared by clone target, `just init` arg, and metadata — single source `normalize_module_name` (`main.py:199-207`).
- **No existing `--dry-run` / preview flag**: a Grep for `dry`/`preview` in `main.py` finds nothing; all mutations (clone, metadata write, `just init`) execute unconditionally once preflight passes.

## Open Areas

- `just init`'s mutations live in the *template repo's* `Justfile` (the local checkout's `Justfile:55-69`), not in `main.py`; the Python code is unaware of what `just init` renames — it only checks the exit code.
- The preflight checks are the only point where the flow inspects state without mutating; there is no dedicated "plan/preview" abstraction in the current code to enumerate intended actions.
