# Design Discussion

## Current State

Package initialization runs a preflight checklist as "Step 0" before any
subprocess or filesystem mutation. `init_new_package` (`main.py:1032`) computes
`new_package_path`, then calls `_run_preflight_checks(new_package_path)`
(`main.py:1048`) before the dry-run short-circuit and the `git clone`.

The preflight layer is self-contained and, per research, almost entirely
preflight-only:

- `PreflightCheck` dataclass (`main.py:664-671`) — preflight-only.
- `_run_preflight_checks` (`main.py:880-906`) — builds a per-call tuple of four
  `PreflightCheck` records, prints `_PREFLIGHT_HEADER`, runs each check,
  emitting `[ok]`/`[FAIL]` lines and re-raising on the first `RuntimeError`.
- Verifiers, all preflight-only: `_verify_required_tools` (`main.py:820-831`),
  `_verify_target_directory_absent` (`main.py:834-841`),
  `_verify_template_remote_reachable` (`main.py:844-877`).
- `_format_check_line` (`main.py:701-707`) — preflight-only caller, but depends
  on the shared `_green`.
- Constants, all preflight-only: `_REQUIRED_TOOLS` (`main.py:56`),
  `_TOOL_INSTALL_HINTS` (`main.py:62-66`), `_PREFLIGHT_HEADER` (`main.py:674`),
  `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`main.py:73-75`).

Two things straddle the preflight boundary and are reused by the real clone
path — they MUST stay:

- `humanize_git_clone_error` + `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20-52,
  78-84`) — used by the clone failure path (`main.py:1075`).
- `_TEMPLATE_REPOSITORY_URL` (`main.py:71`) — used by clone (`main.py:1065`),
  metadata replacement (`main.py:486`), and the dry-run plan (`main.py:738`).
- `_green` / `_color_enabled` (`main.py:685-698`) — also used by the post-`just
  check` success line (`main.py:1132-1133`).

Import fallout (research + inspection): `TimeoutExpired` (`main.py:11`) is used
ONLY by `_verify_template_remote_reachable:860`, so it becomes unused. `run`
(`main.py:11`) is still used at `main.py:241`; `shutil` still used at
`main.py:656, 998, 1027`; `Callable` still used at `main.py:336`. Those stay.

Tests: `tests/test_main.py` has a dedicated preflight cluster (verifier unit
tests, full-checklist stdout tests, and direct `_format_check_line` tests — see
research Q4). Clone/`just init` failure tests and `humanize_git_clone_error`
tests are independent and stay. Docs describe preflight in five files
(`invocation.md`, `overview.md`, `architecture.md`, `data_flows.md`,
`specification.md`) plus `vision.md`'s "V5" milestone (research Q5).

## Desired End State

`init_new_package` proceeds directly from computing `new_package_path` to the
dry-run short-circuit and clone — no preflight step. All preflight-only code,
constants, tests, and documentation are removed. Shared helpers and the
clone-time error handling are untouched.

Verify:
- `just check` passes (format, lint, typecheck, tests all green) — no unused
  imports/symbols remain (Ruff would flag orphaned `TimeoutExpired`).
- `grep -rn "preflight\|PreflightCheck\|_verify_required_tools\|_REQUIRED_TOOLS\|_PREFLIGHT_HEADER\|_format_check_line" modernpackage/ tests/ docs/`
  returns nothing.
- Clone failures still humanize correctly (existing clone tests pass); the
  existing-directory case is still caught at clone time via
  `_GIT_CLONE_ERROR_MESSAGES:43-46`.
- A dry run and a real init still succeed end to end.

## Patterns to Follow

- **Module-private surface + direct-import tests**: preflight symbols are
  `_`-prefixed and imported directly in tests (per Code Best Practices). Remove
  the symbol and its direct tests together.
- **Shared-helper preservation**: keep `_green`/`_color_enabled`
  (`main.py:685-698`) and `humanize_git_clone_error` (`main.py:78-84`) — they
  have non-preflight callers. Do NOT follow the temptation to also remove
  `_format_check_line`'s dependency `_green`.
- **Graceful boundary error handling**: the clone path already raises
  `RuntimeError` with a friendly + raw message (`main.py:1073-1077`); `main()`
  catches it and returns 1 (`main.py:1156-1170`). This remains the sole failure
  surface after preflight removal — no new handling needed.
- **Surgical changes** (CLAUDE.md §3): touch only preflight lines; do not
  reformat or "improve" adjacent clone/metadata/dry-run code.
- **Split, don't compress** (CLAUDE.md §7): this is pure deletion; do not
  restructure remaining code to shrink line count.

## Design Decisions

1. **Remove, do not soft-disable** — delete the preflight code outright rather
   than gating it behind a flag. `task.md` explicitly asks for removal of the
   step and its now-unused helpers/constants/tests/docs.

2. **Remove `_format_check_line` too** (`main.py:701-707`) — its only caller is
   `_run_preflight_checks`. Its direct tests (`test_check_line_*` at
   `test_main.py:1898-1919`) are removed with it; keep the `_green`/
   `_color_enabled` direct tests (`test_main.py:1879-1895`).

3. **Drop the `TimeoutExpired` import** from `main.py:11` — it becomes unused
   once `_verify_template_remote_reachable` is gone. Keep `run` (used at
   `main.py:241`). Ruff enforces this (`pyproject.toml`); relying on `just
   check` to catch a miss.

4. **Existing-directory coverage moves to clone time only** — after removal, a
   pre-existing target directory is no longer caught before clone; it surfaces
   via `git clone` failure classified at `_GIT_CLONE_ERROR_MESSAGES:43-46`. This
   is acceptable and already covered by the humanize layer. Preflight
   integration tests asserting `Popen.call_count == 0` on abort
   (`test_main.py:1401, 1417, 832`) are removed, not reworked — they test the
   removed early-abort behavior, not the clone-time behavior.

5. **Keep `PreflightCheck` dataclass removal clean** — delete the dataclass
   (`main.py:664-671`) and its header constant `_PREFLIGHT_HEADER`
   (`main.py:674`); leave neighboring header constants (`_DRY_RUN_HEADER`, etc.)
   intact.

6. **Docs: delete preflight sections, preserve flow narrative** — remove the
   preflight sections/steps in the five flow docs and `vision.md` V5, and
   renumber the step lists (e.g. `data_flows.md` "Step 4/4.5/5",
   `architecture.md` "Step 0/0.5/1", `specification.md` 8-step list) so the
   remaining sequence reads correctly. Do not rewrite unrelated doc prose.

## What We're NOT Doing

- Not adding any replacement validation (tools-on-PATH, remote reachability) at
  clone time — the clone's own failure + `humanize_git_clone_error` is the
  behavior we fall back to.
- Not removing or altering `humanize_git_clone_error`,
  `_GIT_CLONE_ERROR_MESSAGES`, `_TEMPLATE_REPOSITORY_URL`, `_green`,
  `_color_enabled`, or the clone/`just init`/`just check` phases.
- Not touching argparse-time name validation (`validate_package_name`,
  `main.py:183`) — the "package name valid" check was display-only.
- Not refactoring the remaining `init_new_package` body beyond deleting the
  single `_run_preflight_checks` call site.
- Not analyzing/altering the `tests_e2e/` suite (research Open Areas noted it
  was not examined; flag if any e2e test references preflight during
  implementation).

## Open Risks

- **`tests_e2e/` references**: not analyzed in research. Grep `tests_e2e/` for
  preflight symbols during implementation; remove/adjust if present.
- **Doc step renumbering churn**: the flow docs use numbered steps that
  reference preflight as "Step 0/Step 4". Renumbering must stay consistent
  within each doc — mechanical but easy to leave half-done. Verify with a final
  grep.
- **Shared-symbol over-deletion**: the biggest failure mode is deleting
  `_green`/`_color_enabled`/`humanize_git_clone_error`/`_TEMPLATE_REPOSITORY_URL`
  by association. `just check` (typecheck + tests) is the guardrail.
