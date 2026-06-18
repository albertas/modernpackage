# Plan

## Phase 1: Refuse to proceed when the target directory already exists

### Goal
Fail fast with a clear, actionable error if the computed target directory for
the new package already exists, before any git clone or other filesystem work
runs. This mirrors the existing `_verify_required_tools` preflight pattern
introduced in T38.

### Implementation (`modernpackage/main.py`)

1. Add a module-private preflight helper modeled on `_verify_required_tools`:

   ```python
   def _verify_target_directory_absent(target_path: Path) -> None:
       """Raise RuntimeError if the target package directory already exists."""
       if target_path.exists():
           message = (
               f'target directory already exists: {target_path}'
               ' — choose a different package name or remove the existing directory'
           )
           raise RuntimeError(message)
   ```

   Decision: refuse when the path exists at all (file or directory, empty or
   not). The task says "already exists"; this is the strict, unambiguous reading
   and it runs before any disk mutation. `Path.exists()` covers files and
   directories.

2. In `init_new_package`, call the new check right after `_verify_required_tools()`
   and before the `git clone` `Popen`, so all preflight checks run together
   before any subprocess:

   ```python
   module_name = normalize_module_name(package_name)
   new_package_path = Path.cwd() / module_name

   _verify_required_tools()
   _verify_target_directory_absent(new_package_path)
   ```

3. Leave the existing `humanize_git_clone_error` mapping for
   `'already exists and is not an empty directory'` in place. With the preflight
   check it is now effectively a fallback for races (directory created between
   the check and the clone); keeping it is harmless and out of this task's scope
   to remove.

   The raised `RuntimeError` is already surfaced by `main` (prints to stderr,
   returns 1), so no changes are needed in `main` or to exit-code handling.

### Tests (`tests/test_main.py`)
Model on the existing `test_verify_required_tools_*` tests and the `Popen`
mocking conventions (patch `modernpackage.main.Popen`, assert
`call_count == 0` when the preflight aborts). Use the `tmp_path` and
`monkeypatch` built-in fixtures; `monkeypatch.chdir(tmp_path)` so `Path.cwd()`
resolves into the temp dir.

1. `test_init_new_package_aborts_when_target_directory_exists` — `chdir` into
   `tmp_path`, create the directory matching the normalized module name, patch
   `Popen`, assert `init_new_package(name)` raises `RuntimeError` whose message
   mentions "already exists", and assert `popen_mock.call_count == 0` (no clone
   attempted).

2. `test_init_new_package_proceeds_when_target_directory_absent` — `chdir` into
   an empty `tmp_path`, patch `Popen` for the happy path (returncode 0,
   `communicate` returns `(b'', b'')`), patch `shutil.which` so required tools
   resolve, assert `init_new_package(name)` returns 0 and the three `Popen`
   calls happen (clone, `just init`, `just check`).

3. (Optional) A direct unit test of `_verify_target_directory_absent` for both
   the existing-path (raises) and absent-path (returns None) cases.

### Verification
- [x] `just check` passes (format, lint, complexity, typecheck, tests).
- [x] Coverage stays >= 95% (new branch covered by the tests above). — 98.58%
- [x] New tests pass; existing tests remain green. — 91 passed
