# Data Flows

[overview.md](overview.md)

## Input → Output Pipeline

### User Input

**Command-line arguments:**
```
modernpackage PACKAGE_NAME [FLAGS] [ENV_VARS] [CONFIG_FILE]
```

### Step 1: Parse and Validate Arguments

`parse_args()` is called from `main()`:
1. Define argument parser with all CLI flags
2. Call `parser.parse_args()` to extract raw arguments
3. Load per-user config file via `_load_config_file()`
4. Resolve metadata defaults via `_resolve_metadata_defaults()`:
   - For each metadata field (author_name, author_email, description, license, repository_url)
   - If the flag value is None: try env var, then git config (if applicable), then config file
   - Stop at the first non-None source
5. Validate email and repository_url (if non-None) via `_validated_or_error()`:
   - `ArgumentTypeError` → `parser.error()` → exit code 2
6. Return `Namespace` with all parsed values

**Returned namespace fields:**
- `version`: bool (True if `--version` flag present)
- `dry_run`: bool (True if `--dry-run` flag present)
- `package_name`: str | None (None if not provided)
- `author_name`, `author_email`, `description`, `license`, `repository_url`: str | None each

**Precedence (highest to lowest):**
- Command-line flag (explicit in argv)
- Environment variable (e.g., `MODERNPACKAGE_AUTHOR_NAME`)
- Git config (only for author_name and author_email; via `git config user.name` / `user.email`)
- Config file (via `~/.config/modernpackage/config.toml` or `$XDG_CONFIG_HOME/modernpackage/config.toml`)
- None (no source set)

### Step 2: Validate Package Name

When `parse_args()` is called, the `package_name` argument has `type=validate_package_name` set. This validator:
1. Check regex `_PACKAGE_NAME_RE` (PEP 508 distribution name)
2. If invalid: explain the reason via `_explain_invalid_package_name()` and raise `ArgumentTypeError` → exit code 2
3. Normalize to module name via `normalize_module_name()` (replace `.` and `-` with `_`)
4. Check if normalized name shadows a stdlib module via `sys.stdlib_module_names`
5. If collision: raise `ArgumentTypeError` → exit code 2
6. Return the validated (original) package name string

### Step 3: Normalize and Compute Target Path

In `init_new_package(package_name, ...)`:
1. Call `normalize_module_name(package_name)` → module_name (for import safety)
2. Compute `new_package_path = Path.cwd() / module_name` (target directory in current working directory)

### Step 4: Dry-run Short-Circuit (conditional)

**If `--dry-run` flag is set:**

1. Call `_print_dry_run_plan()` with the normalized module name and all metadata fields (author_name, author_email, description, license, repository_url)
2. Print to stdout:
   - Header: `'Dry run — no changes will be made:'`
   - Target directory line: `f'  clone {_TEMPLATE_REPOSITORY_URL} into {new_package_path}'`
   - Metadata section header: `'  update pyproject.toml metadata:'`
   - For each metadata field:
     - If non-None: `f'    {field_label}: {value}'`
     - If None: `f'    {field_label}: keeps template default'`
   - Just init rename outcome: `f'  run just init: rename modernpackage/ -> {module_name}/'`
   - Just init version outcome: `'  run just init: reset version to 0.0.1'`
3. Return exit code 0 immediately (short-circuit, skip Steps 5-8)
4. No directory is created, no clone occurs, no subprocess is spawned

**If `--dry-run` flag is not set:** skip this step and proceed to Step 5 (Clone).

### Step 5: Git Clone

Spawn subprocess via `Popen(['git', 'clone', _TEMPLATE_REPOSITORY_URL, target_path], ...)`:
- Template URL: constant `_TEMPLATE_REPOSITORY_URL` = `https://github.com/albertas/modernpackage`
- Capture stdout and stderr
- If returncode != 0:
  - Try to humanize stderr via `humanize_git_clone_error()` (maps common patterns to friendly messages)
  - Raise `RuntimeError` with friendly message + raw stderr for diagnostics

### Step 6: Write Metadata

Call `_write_package_metadata(new_package_path, author_name=..., author_email=..., description=..., package_license=..., repository_url=...)`:
1. Read cloned pyproject.toml
2. For each non-None metadata field: do string replacement in the template
   - Escape the value via `_toml_escape()` (backslash + quote)
   - Replace known placeholder strings
3. If package_license is non-None: call `_apply_license()` to insert license key and drop MIT classifier
4. Write back to pyproject.toml only if content changed
5. If pyproject.toml is missing: print notice and return (graceful boundary degradation)

**Template placeholders:**
- author_name → "Name Surname"
- author_email → "email@example.com"
- description → "Package configuration example using bleeding edge toolset."
- repository_url → "https://github.com/albertas/modernpackage"
- license → (inserted after readme field; MIT classifier removed)

### Step 6.5: Strip Scaffolding

Call `_strip_scaffolding(new_package_path, package_name)` to remove the scaffolder's machinery and operational artifacts from the cloned tree:
1. Delete wholesale paths from `_SCAFFOLDING_PATHS_TO_DELETE`:
   - `modernpackage/main.py` — the self-replicating CLI
   - `tests/test_e2e.py` — end-to-end test for the scaffolder
   - `docs` — scaffolder documentation
   - `BACKLOG.md` — project-metadata file
   - `errors`, `issues`, `workspace` — scaffolder operational/process artifact directories
   - `lifecycle_state.yml`, `metrics.yml` — scaffolder operational/process artifact files (`lifecycle_state.yml` is re-seeded fresh below)
   - (tolerate missing paths — no error if not present)
2. Write `_TEST_MAIN_STUB` to `tests/test_main.py`:
   - Replaces scaffolder test suite with minimal stub
   - Imports package version to satisfy coverage requirements
   - Uses literal `modernpackage` token so `just init`'s rename sed updates it
3. Write `_README_STUB_TEMPLATE.format(package_name=package_name)` to `README.md`:
   - Replaces scaffolder README with generic template
   - Interpolates the user's chosen distribution name directly into the H1, bypassing `just init`'s rename sed for this file
4. Write `_LIFECYCLE_STATE_STUB` to `lifecycle_state.yml`:
   - Replaces the scaffolder's stripped state file with a fresh `code_quality_is_good: true` stub
   - Seeds the generated package's own lifecycle loop from a good-quality baseline (no scaffolder phases/semaphores)
5. Call `_remove_project_scripts(new_package_path / 'pyproject.toml')`:
   - Removes `[project.scripts]` table to avoid dangling entry points
   - Leaves surrounding tables (`[dependency-groups]`, `[tool.*]`) intact
   - Tolerates missing file or table — no-op if absent

**Result:** the cloned tree is now clean of scaffolder machinery and operational artifacts. The next step (`just init`) will operate on an already-stripped tree, and the single git commit will capture the clean initial state.

### Step 7: Just Init

Spawn subprocess via `Popen(['just', 'init', module_name], cwd=new_package_path, ...)`:
- Capture stdout and stderr
- If returncode != 0: raise `RuntimeError` with message "just init failed with exit code {code}: {stderr}"
- If FileNotFoundError (just not on PATH): raise `RuntimeError` with install message
- **Note**: operates on the already-stripped tree (see Step 6.5); renames the stub test file using the standard sed rename pass (README is already written with the distribution name and is not renamed)

### Step 7.5: Just Compile

Spawn subprocess via `Popen(['just', 'compile'], cwd=new_package_path, ...)`:
- Does not capture stdout/stderr; inherits parent streams so progress is visible to user
- This step regenerates the `uv.lock` file based on the scaffolded package's current dependencies (after metadata writing and template injection)
- If returncode != 0:
  - Print error message to stderr: "compile failed with exit code {code}: {stderr}"
  - Return exit code 1 (short-circuit; skip compile, sync, and check)
- **Purpose**: ensures the lockfile is fresh and reflects all injected dependencies (both runtime and dev), so subsequent sync and check steps operate on a valid locked environment

### Step 7.6: Just Sync

Spawn subprocess via `Popen(['just', 'sync'], cwd=new_package_path, ...)`:
- Does not capture stdout/stderr; inherits parent streams so progress is visible to user
- This step creates/updates the virtual environment and installs locked dependencies (dev group + editable package)
- If returncode != 0:
  - Print error message to stderr: "sync failed with exit code {code}: {stderr}"
  - Return exit code 1 (short-circuit; skip check)
- **Purpose**: ensures the package's dependencies are installed before the comprehensive quality gate runs, so import statements in tests work correctly

### Step 8: Just Check and Summary

Spawn subprocess via `Popen(['just', 'check'], cwd=new_package_path, ...)`:
- Does not capture stdout/stderr; inherits parent streams so progress is visible to user
- Communicate (wait for process to finish)
- At this point, the generated package contains only the stripped tree: no scaffolder CLI, no end-to-end tests, no scaffolder documentation — only a minimal stub test and generic README; dependencies are locked and synced
- If returncode == 0:
  - Print "just check passed — {module_name} scaffold is valid." to stdout
  - Call `_print_init_summary(package_name, new_package_path)` to output a multi-line summary block to stdout:
    ```
    Created package:
      package name: <package_name>
      path: <created_path>
      version: 0.0.1
    ```
    (where the version is the constant `_RESET_VERSION`)
  - Return exit code 0
- If returncode != 0:
  - Print "just check failed with exit code {code} — review the output in {module_name}." to stderr
  - Return exit code 1

### Step 9: Error Handling and Exit

In `main()`:
- If `init_new_package()` raises `RuntimeError`: catch, print to stderr, return exit code 1
- If no exception: return the exit code from `init_new_package()` (0 or 1)

**Final outputs:**
- Exit code 0: Success
- Exit code 1: Runtime failure (git, just init, just compile, just sync, or just check)
- Exit code 2: Argument validation error (invalid name, email, URL, or metadata)

## Config File Resolution

1. Resolve path via `_user_config_path()`:
   - Try `$XDG_CONFIG_HOME/modernpackage/config.toml`
   - Fall back to `~/.config/modernpackage/config.toml`
   - If home is unresolvable: return None
2. Parse via `_load_config_file()`:
   - Try to open and parse TOML
   - Missing file → return `{}` silently
   - Parse error → print notice to stderr, return `{}`
3. Extract values via `_config_file_default()`:
   - Only non-empty string values count as set
   - Empty strings, int, bool, array, table → treated as None

## Git Config Resolution

For each git config key (user.name, user.email):
1. Call `git config <key>`
2. Capture stdout
3. If returncode == 0 and stdout is non-empty (after strip): return the value
4. Otherwise: return None
5. If git is not on PATH or command fails: return None (no error printed; fallback expected)
