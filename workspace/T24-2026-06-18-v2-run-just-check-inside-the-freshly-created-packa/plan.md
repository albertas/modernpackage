# Plan

## Phase 1: Run `just check` in the freshly scaffolded package

### Context
`modernpackage/main.py::init_new_package(package_name)` currently performs two
subprocess steps via `Popen` (`stdin/stdout/stderr=PIPE`):
1. `git clone https://github.com/albertas/modernpackage <new_package_path>`
2. `just init <package_name>` with `cwd=new_package_path`

Both already check `pipe.returncode` and raise `RuntimeError` on failure, and
the `just` command is guarded with a `FileNotFoundError -> RuntimeError` hint.
`new_package_path = Path.cwd() / package_name`.

### Implementation
Add a third step in `init_new_package`, immediately after the successful
`just init` block, that runs `just check` inside the new package directory,
mirroring the existing `just init` block:

- `Popen(['just', 'check'], stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=new_package_path)`
  with the same `# noqa: S603` / `# noqa: S607` annotations as the existing
  calls.
- Call `pipe.communicate()` to drain the pipes (consistent with the other
  steps; prevents the child from blocking on a full pipe buffer).

Scope note (keep this task minimal and avoid stepping on sibling V2 tasks):
- "Report whether `just check` passed/failed", "Exit non-zero when `just check`
  fails", and "Add an e2e test" are **separate** backlog tasks. This task only
  adds the invocation. Do **not** add return-code-based reporting or a new
  `RuntimeError` for `just check` here — that belongs to the sibling tasks.
- Keep the implementation a near-copy of the existing `just init` Popen block
  for style consistency. Do not refactor the existing two steps.

### Tests (tests/test_main.py)
The existing unit tests mock `modernpackage.main.Popen`. Adding a third
subprocess call changes the expected call count.

- Update `test_init_new_package`: change the assertion from
  `popen_mock.call_count == 2` to `popen_mock.call_count == 3` (update the
  `# noqa: PLR2004` magic-value comment accordingly).
- Verify the existing failure tests still hold:
  - `test_init_new_package_git_clone_failure` — clone returns 1, raises before
    reaching `just init`/`just check` (unchanged).
  - `test_init_new_package_just_init_failure` and
    `test_init_new_package_just_not_installed` use `side_effect` lists with two
    entries; since `just init` raises/fails before `just check` runs, the third
    `Popen` is never reached — these remain valid. Confirm by running them.
- Optionally add `test_init_new_package_runs_just_check` asserting the third
  `Popen` call args are `['just', 'check']` with `cwd=<package dir>` (use
  `popen_mock.call_args_list[2]`), following the existing mocking style
  (`returncode = 0`, `communicate.return_value = (b'', b'')`).

The e2e test (`tests/test_e2e.py::test_scaffolded_package_passes_check`)
already runs `just check` against the scaffolded package and needs no change.

### Verify
- [x] `just check` passes at the repo root (runs `check-format`, `check-lint`,
  `check-complexity`, `check-typecheck`, `test`, `audit`).
- [x] Confirm the new/updated unit tests pass and coverage stays >= 95%.
