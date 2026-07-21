# Structure Outline

## Approach

Pure deletion of the self-contained preflight layer from `modernpackage/main.py`,
its tests in `tests/test_main.py`, and its docs. Shared helpers
(`_green`/`_color_enabled`, `humanize_git_clone_error` + `_GIT_CLONE_ERROR_MESSAGES`,
`_TEMPLATE_REPOSITORY_URL`) and the clone/`just init`/`just check` phases are
untouched. Sliced into three phases that each leave `just check` green: (1) remove
the preflight step from the init flow, (2) delete the now-orphaned verifiers,
constants, and unused import, (3) clean the docs. Ruff flags unused *imports* and
*local variables* but not unused *module-level functions*, so the verifiers may
outlive Phase 1 without breaking the build — this is what allows the split.

---

## Phase 1: Remove the preflight step from `init_new_package`

Deletes the preflight call site and the checklist orchestration so package init
proceeds directly from computing `new_package_path` to the dry-run short-circuit
and clone. This is the behavioral change; the existing-directory case now surfaces
at clone time via `_GIT_CLONE_ERROR_MESSAGES` (`already exists and is not an empty
directory`).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes** (all deletions):
- Remove call `_run_preflight_checks(new_package_path)` — `main.py:1048`
- Delete `def _run_preflight_checks(target_path) -> None` — `main.py:880-906`
- Delete `@dataclass(frozen=True) class PreflightCheck { label: str; run: Callable[[], None] }` — `main.py:664-671`
- Delete `def _format_check_line(label, *, ok: bool) -> str` — `main.py:701-707` (only caller was preflight)
- Delete constant `_PREFLIGHT_HEADER` — `main.py:674` (leave neighboring `_DRY_RUN_HEADER`/`_INIT_SUMMARY_HEADER`/`_NEXT_COMMANDS_HEADER` intact)
- Remove tests: full-checklist stdout (`test_run_preflight_checks_prints_full_checklist_on_clean_run:732`, `_marks_failing_check_and_aborts:845`, `_aborts_on_earlier_check_without_later_lines:867`); target-dir abort integration (`test_init_new_package_aborts_when_target_directory_exists:1401`, `_proceeds_when_target_directory_absent:1417`); remote-unreachable integration (`test_init_new_package_aborts_when_remote_unreachable:832`); `_format_check_line` direct tests (`test_check_line_*:1898-1919`)
- **Keep**: `_green`/`_color_enabled` and their direct tests (`test_main.py:1879-1895`); `humanize_git_clone_error` + its tests; all clone/`just init`/`just check` tests

**Verify**: `just check` passes. Verifier unit tests (`test_verify_*`) still pass
because the `_verify_*` functions still exist (untouched this phase). Confirm
preflight no longer runs:
`grep -n "_run_preflight_checks\|PreflightCheck\|_format_check_line\|_PREFLIGHT_HEADER" modernpackage/main.py`
returns nothing. Existing-directory still guarded at clone time:
`grep -n "already exists and is not an empty directory" modernpackage/main.py`
returns the `_GIT_CLONE_ERROR_MESSAGES` entry.

---

## Phase 2: Delete orphaned verifiers, constants, and unused import

Removes the three verifier functions (now called by nothing), their preflight-only
constants, and the `TimeoutExpired` import that becomes unused once
`_verify_template_remote_reachable` is gone.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes** (all deletions):
- Delete `def _verify_required_tools() -> None` — `main.py:820-831`
- Delete `def _verify_target_directory_absent(target_path) -> None` — `main.py:834-841`
- Delete `def _verify_template_remote_reachable() -> None` — `main.py:844-877`
- Delete constants `_REQUIRED_TOOLS` (`main.py:56`), `_TOOL_INSTALL_HINTS` (`main.py:62-66`), `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`main.py:73-75`)
- Remove `TimeoutExpired` from the `subprocess` import — `main.py:11` (keep `run`, still used at `main.py:241`; keep `shutil`, `Callable`)
- Remove tests: `_verify_required_tools` cluster (`test_main.py:421-551`), `_verify_target_directory_absent` unit tests (`:1435-1445`), `_verify_template_remote_reachable` unit tests (`:1447-1490`)
- **Keep**: `humanize_git_clone_error`, `_GIT_CLONE_ERROR_MESSAGES`, `_TEMPLATE_REPOSITORY_URL`, `_green`/`_color_enabled`

**Verify**: `just check` passes (Ruff confirms no unused `TimeoutExpired`, no
unused symbols).
`grep -rn "preflight\|PreflightCheck\|_verify_required_tools\|_verify_target_directory_absent\|_verify_template_remote_reachable\|_REQUIRED_TOOLS\|_TOOL_INSTALL_HINTS\|_REMOTE_REACHABILITY_TIMEOUT_SECONDS\|_PREFLIGHT_HEADER\|_format_check_line" modernpackage/ tests/`
returns nothing. End-to-end smoke: a dry run
(`python -m modernpackage <name> --dry-run` or the project's init entrypoint)
returns 0 and prints no `[ok]` checklist lines.

---

## Phase 3: Remove preflight from documentation

Deletes preflight sections from the five flow docs and `vision.md`'s V5 milestone,
renumbering step lists so the remaining sequence reads correctly. No unrelated
prose rewrites.

**Files**: `docs/invocation.md`, `docs/overview.md`, `docs/architecture.md`,
`docs/data_flows.md`, `docs/specification.md`, `docs/vision.md`

**Key changes**:
- `invocation.md`: delete "Preflight checks and checklist" section (`:398-505`), the `[ok]` output blocks in dry-run examples (`:70-74, :95-99, :123-127`), and "only after the preflight check has passed" phrasing (`:509`)
- `overview.md`: remove preflight from inline sequence (`:7`) and bullets (`:15-16, :63-67`)
- `architecture.md`: delete constant docs (`_PREFLIGHT_HEADER:84-91`, `_REMOTE_REACHABILITY_TIMEOUT_SECONDS:73-82`), verifier docs (`:412-497`), `PreflightCheck` (`:499-514`), `_run_preflight_checks` (`:673-722`); renumber flow "Step 0/0.5/1" (`:1345-1352`)
- `data_flows.md`: delete "Step 4: Preflight Checks" (`:57-80`), renumber Step 4.5 dry-run and Step 5 clone (`:82, :104`); remove index row (`:29`)
- `specification.md`: drop preflight step from the 8-step list (`:60-74`) and renumber
- `vision.md`: delete "V5 — Preflight environment checks before cloning" (`:48-55`)

**Verify**:
`grep -rni "preflight" docs/` returns nothing.
`grep -rn "PreflightCheck\|_verify_required_tools\|_run_preflight_checks" docs/`
returns nothing. Manually scan each edited doc's step list for a monotonically
consistent numbering:
`grep -nE "Step [0-9]" docs/architecture.md docs/data_flows.md` shows no gap or
duplicate around the removed steps.

---

## Cross-cutting: tests_e2e (Open Risk)

Not analyzed in research. Run once at the start of Phase 1:
`grep -rni "preflight\|PreflightCheck\|_verify_required_tools\|_run_preflight_checks" tests_e2e/`
If any hits, fold their removal/adjustment into the phase that removes the
referenced symbol (Phase 1 for orchestration, Phase 2 for verifiers). If empty,
no action.

## Testing Checkpoints

- **After Phase 1**: `just check` green; init flow no longer calls preflight;
  `_run_preflight_checks`/`PreflightCheck`/`_format_check_line`/`_PREFLIGHT_HEADER`
  absent from `main.py`; verifier unit tests still pass (functions still present);
  existing-dir handled at clone time.
- **After Phase 2**: `just check` green; no preflight symbols or constants in
  `modernpackage/` or `tests/`; `TimeoutExpired` import gone; dry run + real init
  succeed with no checklist output.
- **After Phase 3**: `grep -rni "preflight" docs/` empty; doc step numbering
  consistent. Full removal complete — matches design's "Desired End State" verify
  grep.
