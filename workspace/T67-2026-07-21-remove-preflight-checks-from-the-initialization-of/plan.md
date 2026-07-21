# Implementation Plan

## Overview

Remove the self-contained preflight-check layer from package initialization so
`init_new_package` proceeds directly from computing `new_package_path` to the
dry-run short-circuit and clone. All preflight-only code, constants, tests, and
documentation are deleted; shared helpers (`_green`/`_color_enabled`,
`humanize_git_clone_error` + `_GIT_CLONE_ERROR_MESSAGES`,
`_TEMPLATE_REPOSITORY_URL`) and the clone/`just init`/`just check` phases stay
untouched.

## Preconditions verified during planning

- `tests_e2e/` has **no** preflight references (grep returned nothing) — the
  Open Risk in `structure.md` §"Cross-cutting" and `design.md` §"Open Risks" is
  closed. No `tests_e2e/` changes are needed.
- `Callable` (`main.py:15`, used at `main.py:336` by `validate_package_name`'s
  `validator` param) and `run` (`main.py:11`, used at `main.py:241`) stay.
  `TimeoutExpired` (`main.py:11`) is used ONLY by
  `_verify_template_remote_reachable` (`main.py:860`) and becomes removable.
- Test import block (`tests/test_main.py:12-46`) imports five preflight symbols
  that become unused as their tests are deleted: `_REQUIRED_TOOLS` (`:16`),
  `_format_check_line` (`:24`), `_verify_required_tools` (`:34`),
  `_verify_target_directory_absent` (`:35`), `_verify_template_remote_reachable`
  (`:36`), plus `from subprocess import TimeoutExpired` (`:6`). Ruff lint (`just
  check`) flags unused imports, so these MUST be removed in lockstep with their
  tests.

### Deviations from `structure.md` (resolved here)

1. **`tests/test_main.py` import cleanup** — not enumerated in `structure.md`
   but mandatory for `just check` to stay green (Ruff `F401` unused-import).
   Split across phases to match when each symbol's last use is deleted:
   `_format_check_line` import removed in Phase 1; `_REQUIRED_TOOLS`, the three
   `_verify_*`, and `TimeoutExpired` removed in Phase 2.
2. **`test_init_output_has_blank_separators` (`tests/test_main.py:760-785`)** —
   not listed in `structure.md`. Its first assertion block (`:775-780`) keys off
   the preflight line `'template remote reachable'`; with preflight gone,
   `max(...)` over an empty sequence raises `ValueError`. Resolution: delete only
   that first assertion block (the preflight portion) in Phase 1 and keep the
   second block (`:782-785`, blank line between `just check passed` and the
   summary header), which is preflight-independent. This is the surgical minimum
   to keep the test meaningful.
3. **Phase 3 doc line numbers** re-derived from the current files (they had
   drifted slightly from `structure.md`/`research.md`). The `docs/data_flows.md`
   "index row (:29)" in `structure.md` is actually the table cell in
   `docs/overview.md:29`; corrected below. Additional inline `preflight` mentions
   beyond the enumerated sections are listed so the final `grep -rni preflight
   docs/` gate passes.

All commands below run from the repo root `/home/niekas/tools/modernpackage`.
Verification uses the `Justfile` recipe `just check` (= `check-format`,
`check-lint`, `check-complexity`, `check-typecheck`, `test`, `audit`).

---

## Phase 1: Remove the preflight step from `init_new_package`

Deletes the preflight call site, the checklist orchestrator, the
`PreflightCheck` dataclass, `_format_check_line`, and `_PREFLIGHT_HEADER`, plus
their tests. `_verify_*` functions and their constants remain (deleted in Phase
2); Ruff does not flag unused module-level functions, so `just check` stays
green. Behavioral change: the existing-directory case is now surfaced at clone
time via `_GIT_CLONE_ERROR_MESSAGES` (`already exists and is not an empty
directory`, `main.py:43-46`), not before clone.

### Changes

#### 1. Remove the preflight call site
**File**: `modernpackage/main.py`
**Action**: modify

Delete the single call and its surrounding blank line so the body flows from the
target-path compute straight into the dry-run check (`main.py:1046-1050`):

```python
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

    _run_preflight_checks(new_package_path)   # <-- delete this line (1048)

    if dry_run:
```

Result:

```python
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

    if dry_run:
```

#### 2. Delete the orchestrator
**File**: `modernpackage/main.py`
**Action**: delete

Remove `def _run_preflight_checks(target_path: Path) -> None` in full —
`main.py:880-906` (docstring, per-call `checks` tuple, header print, and the
run/`[ok]`/`[FAIL]` loop).

#### 3. Delete the `PreflightCheck` dataclass and its header constant
**File**: `modernpackage/main.py`
**Action**: delete

- `@dataclass(frozen=True) class PreflightCheck` with fields `label`/`run` —
  `main.py:664-671`.
- Constant `_PREFLIGHT_HEADER: str = 'Preflight checks:'` — `main.py:674`.
- **Keep** the neighboring header constants intact: `_DRY_RUN_HEADER` (`:675`),
  `_RESET_VERSION` (`:678`), `_INIT_SUMMARY_HEADER` (`:679`),
  `_NEXT_COMMANDS_HEADER` (`:680`), `_ANSI_GREEN`/`_ANSI_RESET` (`:681-682`).
- **Keep** the `dataclass` import (`main.py:9`) — still used by other
  dataclasses in the module. Verify after edit with the grep below; if
  `@dataclass` has no remaining uses, Ruff would flag the import — it does not,
  so leave it.

#### 4. Delete `_format_check_line`
**File**: `modernpackage/main.py`
**Action**: delete

Remove `def _format_check_line(label: str, *, ok: bool) -> str` —
`main.py:701-707`. **Keep** `_color_enabled` (`:685-691`) and `_green`
(`:694-698`) exactly as-is — `_green` is still used by the success line in
`init_new_package` (`main.py:1132-1133`).

#### 5. Remove Phase-1 tests
**File**: `tests/test_main.py`
**Action**: delete / modify

Delete these test functions (each in full, including decorators/blank lines):

- Full-checklist stdout tests:
  - `test_run_preflight_checks_prints_full_checklist_on_clean_run` (`:732-757`)
  - `test_run_preflight_checks_marks_failing_check_and_aborts` (`:845-864`)
  - `test_run_preflight_checks_aborts_on_earlier_check_without_later_lines`
    (`:867-887`)
- Target-directory abort integration tests:
  - `test_init_new_package_aborts_when_target_directory_exists` (`:1401-1414`)
  - `test_init_new_package_proceeds_when_target_directory_absent` (`:1417-1432`)
- Remote-unreachable integration test:
  - `test_init_new_package_aborts_when_remote_unreachable` (`:832-842`)
- `_format_check_line` direct tests:
  - `test_check_line_ok_is_green_on_tty` (`:1898-1904`)
  - `test_check_line_ok_is_plain_off_tty` (`:1906-1911`)
  - `test_check_line_fail_is_never_green` (`:1913-1918`)

Modify `test_init_output_has_blank_separators` (`:760-785`): delete only the
preflight assertion block and its comment (`:775-780`):

```python
    # blank line between the last preflight line and the progress line
    last_preflight = max(
        i for i, line in enumerate(lines) if 'template remote reachable' in line
    )
    progress = next(i for i, line in enumerate(lines) if 'Running just check' in line)
    assert '' in lines[last_preflight + 1 : progress]

```

Keep the rest of the function (the `with` block, the `lines = ...` capture, and
the `:782-785` blank-line-before-summary assertion). The `shutil.which` patch at
`:764` is now unnecessary but harmless — leave it to minimize churn.

Remove the now-unused import in the `from modernpackage.main import (...)` block:

- `_format_check_line,` — `tests/test_main.py:24`

**Keep** in Phase 1 (still used by verifier tests removed in Phase 2):
`_REQUIRED_TOOLS` (`:16`), `_verify_required_tools` (`:34`),
`_verify_target_directory_absent` (`:35`), `_verify_template_remote_reachable`
(`:36`), and `from subprocess import TimeoutExpired` (`:6`).

**Keep** unchanged: `_green`/`_color_enabled` direct tests (`:1879-1895`), all
`humanize_git_clone_error` tests (`:644-677`), and all clone/`just init`/`just
check` failure tests (`:376-419`, `:582-628`, `:680-729`, `:788-829`).

> **Deviation (Phase 1):** Four tests in the `_verify_required_tools` cluster
> that the plan slated for Phase 2 (`test_verify_required_tools_missing_git`,
> `_missing_just`, `_missing_uv`, `_reports_all_missing`) were actually
> *integration* tests calling `init_new_package` and asserting a preflight abort
> before clone (`popen_mock.call_count == 0`). With preflight removed they flow
> into the clone Popen and fail. Deleted them here (Phase 1) instead of Phase 2
> to keep `just check` green; the 5 direct-`_verify_required_tools()` tests
> remain for Phase 2.

### Verification
#### Automated
- [x] `just check` passes (format, lint, complexity, typecheck, test, audit).
      *(format/lint/complexity/typecheck/test all pass — 141 passed. `audit`
      fails on a pre-existing, unrelated dependency CVE: `mcp` 1.28.0
      CVE-2026-59950, not touched by this phase.)*
#### Manual
- [x] Preflight orchestration symbols gone from `main.py`:
      `grep -nE "_run_preflight_checks|PreflightCheck|_format_check_line|_PREFLIGHT_HEADER" modernpackage/main.py`
      → no output.
- [x] Call site gone:
      `grep -n "_run_preflight_checks" modernpackage/main.py` → no output.
- [x] Verifiers still present (deleted next phase):
      `grep -cE "_verify_required_tools|_verify_target_directory_absent|_verify_template_remote_reachable" modernpackage/main.py`
      → 3 (non-zero).
- [x] Existing-directory still guarded at clone time:
      `grep -n "already exists and is not an empty directory" modernpackage/main.py`
      → returns the `_GIT_CLONE_ERROR_MESSAGES` entry (`main.py:44`).
- [x] Verifier unit tests still pass:
      `uv run pytest tests/test_main.py -k "verify_required_tools or verify_target_directory or verify_template_remote" -o addopts=""`
      → 11 passed (functions still exist).

---

## Phase 2: Delete orphaned verifiers, constants, and unused imports

Removes the three now-uncalled verifier functions, their preflight-only
constants, and the `TimeoutExpired` imports (in both `main.py` and the test
module) that become unused once `_verify_template_remote_reachable` is gone.

### Changes

#### 1. Delete the verifier functions
**File**: `modernpackage/main.py`
**Action**: delete

- `def _verify_required_tools() -> None` — `main.py:820-831`.
- `def _verify_target_directory_absent(target_path: Path) -> None` —
  `main.py:834-841`.
- `def _verify_template_remote_reachable() -> None` — `main.py:844-877`.

#### 2. Delete preflight-only constants
**File**: `modernpackage/main.py`
**Action**: delete

- `_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')` and its comment —
  `main.py:55-56`.
- `_TOOL_INSTALL_HINTS: dict[str, str] = {...}` and its comment —
  `main.py:59-66`.
- `_REMOTE_REACHABILITY_TIMEOUT_SECONDS: int = 10` and its comment —
  `main.py:73-75`.
- **Keep** `_TEMPLATE_REPOSITORY_URL` (`main.py:71`) and its comment — used by
  clone (`:1065`), metadata replacement (`:486`), and dry-run plan (`:738`).

#### 3. Drop the unused `TimeoutExpired` import
**File**: `modernpackage/main.py`
**Action**: modify

`main.py:11`:

```python
from subprocess import PIPE, Popen, TimeoutExpired, run
```

→

```python
from subprocess import PIPE, Popen, run
```

Keep `PIPE`, `Popen` (clone/`just init`/`just check`), and `run` (`main.py:241`).

#### 4. Remove Phase-2 tests
**File**: `tests/test_main.py`
**Action**: delete

Delete these test functions in full:

- `_verify_required_tools` cluster — `test_main.py:421-547`:
  `test_verify_required_tools_missing_git` (`:421`), `_missing_just` (`:436`),
  `_missing_uv` (`:451`), `_all_present` (`:466`), `_reports_all_missing`
  (`:474`), `_hint_points_at_git_install_docs` (`:493`),
  `_hint_points_at_uv_install_docs` (`:508`),
  `_hint_points_at_just_install_docs` (`:523`),
  `_lists_all_install_hints_when_all_missing` (`:538`).
- `_verify_target_directory_absent` unit tests:
  `test_verify_target_directory_absent_raises_when_exists` (`:1435-1439`),
  `_passes_when_absent` (`:1442-1444`). Also delete the section comment banner
  `# _verify_target_directory_absent preflight check` (`:1396-1398`) that now
  labels nothing.
- `_verify_template_remote_reachable` unit tests:
  `_returns_none_when_reachable` (`:1447-1450`),
  `_raises_on_resolve_host` (`:1453-1463`),
  `_raises_on_repo_not_found` (`:1466-1475`),
  `_raises_on_timeout` (`:1478-1485`).

#### 5. Remove now-unused test imports
**File**: `tests/test_main.py`
**Action**: modify

- `from subprocess import TimeoutExpired` — `:6` (last use was the deleted
  `_raises_on_timeout` test at `:1480`). Delete the whole line.
- In the `from modernpackage.main import (...)` block, delete:
  `_REQUIRED_TOOLS,` (`:16`), `_verify_required_tools,` (`:34`),
  `_verify_target_directory_absent,` (`:35`),
  `_verify_template_remote_reachable,` (`:36`).

**Keep**: `humanize_git_clone_error`, `_GIT_CLONE_ERROR_MESSAGES`,
`_TEMPLATE_REPOSITORY_URL`, `_green`/`_color_enabled` and their tests.

### Verification
#### Automated
- [x] `just check` passes — confirms no unused `TimeoutExpired`, no unused
      imports/symbols (Ruff `F401`), typecheck and tests green.
      *(format/lint/complexity/typecheck/test all pass — 130 passed. `audit`
      fails on the same pre-existing, unrelated `mcp` 1.28.0 CVE-2026-59950 as
      Phase 1, not touched by this phase.)*
#### Manual
- [x] No preflight symbols remain in code/tests:
      `grep -rnE "preflight|PreflightCheck|_verify_required_tools|_verify_target_directory_absent|_verify_template_remote_reachable|_REQUIRED_TOOLS|_TOOL_INSTALL_HINTS|_REMOTE_REACHABILITY_TIMEOUT_SECONDS|_PREFLIGHT_HEADER|_format_check_line" modernpackage/ tests/`
      → no output.
- [x] `TimeoutExpired` import gone from both modules:
      `grep -rn "TimeoutExpired" modernpackage/ tests/` → no output.
- [x] `_TEMPLATE_REPOSITORY_URL` retained:
      `grep -c "_TEMPLATE_REPOSITORY_URL" modernpackage/main.py` → ≥ 3 (got 4).
- [x] End-to-end dry run prints no checklist and exits 0:
      `uv run modernpackage smoke_pkg_$$ --dry-run > /tmp/dryrun.out; echo "exit=$?"`
      → `exit=0`, and
      `grep -c "\[ok\]\|Preflight checks:" /tmp/dryrun.out` → `0`.

---

## Phase 3: Remove preflight from documentation

Deletes preflight sections from the five flow docs and `vision.md`'s V5
milestone, and rewords/renumbers the remaining sequences so they read correctly.
No unrelated prose rewrites. Because deletions shift line numbers, edit each file
top-to-bottom within one pass, or re-grep between edits. Line numbers below are
current as of planning; the authoritative gate is `grep -rni preflight docs/`
returning nothing.

### Changes

#### 1. `docs/invocation.md`
**Action**: modify / delete

- Delete the dedicated section **"Preflight checks and checklist"** and its
  sub-sections (happy-path + failure-path checklist output) — heading at `:398`
  through the closing paragraph at `:505` (ends `...incomplete clones.`).
- Delete the three literal `[ok]` checklist blocks inside the dry-run examples:
  `:70-74`, `:95-99`, `:123-127` (each is the five lines `Preflight checks:` +
  four `  [ok]   ...`). Remove any now-orphaned blank line left behind.
- Reword `:53` — drop "Runs preflight checks (same as a normal run), then":
  `Previews what scaffolding would do without making any changes. Exits cleanly
  with exit code 0 and prints a high-level plan showing:`
- Reword `:60` — `No directory is created, no clone occurs, no subprocess is
  spawned.` (drop "beyond preflight").
- Delete the `:144` **Important** note about the dry-run performing preflight
  checks / network probe in full (it no longer applies).
- Reword `:509` — drop "This occurs only after the preflight check has passed,
  so the required tools are guaranteed to be present." Keep the preceding
  sentence about clone-failure handling in `main()`.
- **Keep** the color/`[ok]`-marker prose at `:806-828` — those `[ok]` mentions
  describe the success line coloring, not preflight; they are not "preflight"
  matches.

#### 2. `docs/overview.md`
**Action**: modify

- Reword the inline sequence at `:7`: change
  `...validates the package name, verifies required tools are on PATH, checks
  that the target directory does not already exist, clones itself...` to
  `...validates the package name, clones itself...` (drop the two preflight
  clauses; keep validation-of-name, which is argparse-time, and clone onward).
- Delete the bullet **"Preflight checks with checklist"** at `:15` (single long
  bullet, ends `...scaffolding proceeds`).
- In the doc-index table, edit the `data_flows.md` row at `:29`: remove
  `preflight checks, ` from the description so it reads
  `**Data flows**: argument parsing, validation, scaffolding pipeline, metadata
  resolution, target path computation.`
- Delete the **"Preflight checks with checklist"** block at `:63-67` (the intro
  bullet `:63` plus numbered sub-items 1–4 naming `_run_preflight_checks`,
  `_verify_required_tools`, `_verify_target_directory_absent`,
  `_verify_template_remote_reachable`).
- **Keep** `:69` ("Precise validation diagnostics" / `_explain_invalid_package_name`)
  — unrelated to preflight.

#### 3. `docs/architecture.md`
**Action**: delete / modify

Delete these documentation blocks (heading through the block's end):

- Constant `_REQUIRED_TOOLS` doc — `:41-51`.
- Constant `_TOOL_INSTALL_HINTS` doc — `:53-65`.
- Constant `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` doc — `:75-82`.
- Constant `_PREFLIGHT_HEADER` doc — `:84-91`.
- `_verify_required_tools()` section — `:412-445`.
- `_verify_target_directory_absent()` section — `:447-469`.
- `_verify_template_remote_reachable()` section — `:471-497`.
- `PreflightCheck` dataclass section — `:499-514`.
- `_format_check_line(...)` section — `:565-598` (its function was removed in
  Phase 1; the section references the `Preflight checks:` header at `:577`).
- `_run_preflight_checks(target_path)` section — `:673-722` (through the
  "Integration with `init_new_package()`" subsection and its code fence).

Reword the surviving inline preflight mentions:

- `_TEMPLATE_REPOSITORY_URL` doc at `:73`: drop "the pre-flight reachability
  probe (`_verify_template_remote_reachable()`) and" so it reads "Used by the git
  clone command in `init_new_package()`."
- `_green`/`_color_enabled` design-rationale bullet at `:557`: it references the
  now-deleted `_format_check_line`. Reword to describe only the success-line use,
  e.g. "Wraps the padded field before ANSI codes are added so alignment is
  computed on plain text." Keep the rest of the `_green` section (it is a shared
  helper).
- `_print_dry_run_plan` doc at `:624`: change "when `dry_run=True` after
  preflight checks pass" → "when `dry_run=True`".
- `--dry-run` flag doc at `:1280`: change "runs preflight, then prints a plan and
  exits" → "prints a plan and exits".
- `init_new_package` summary at `:1323`: change "performs preflight checks and
  prints a preview plan" → "prints a preview plan".

Renumber the step-numbered flow at `:1345-1352`:

- Delete **"Step 0: Preflight checks & checklist"** and its sub-items
  (`:1345-1349`).
- Renumber **"Step 0.5: Dry-run short-circuit"** (`:1351`) → **"Step 0: Dry-run
  short-circuit"** and drop "after preflight checks pass," / the "If preflight
  checks fail..." trailing sentence from its body.
- Renumber **"Step 1: Clone"** (`:1352`) → **"Step 1"** stays if the list is
  0-based, but to keep a clean ascending sequence make it **"Step 0: Dry-run
  short-circuit"** then **"Step 1: Clone"**. Ensure the resulting list reads
  `Step 0 … Step 1 …` with no gap.

#### 4. `docs/data_flows.md`
**Action**: delete / modify

- Delete **"### Step 4: Preflight Checks"** and its body — `:57-80` (through the
  bold summary line ending `...before any filesystem mutation.**`).
- Renumber the remaining steps so they are contiguous. Current order after
  deletion: Step 4.5 (dry-run) → Step 5 (clone) → Step 6 … Step 9. Renumber to:
  - `### Step 4.5: Dry-run Short-Circuit (conditional)` (`:82`) →
    `### Step 4: Dry-run Short-Circuit (conditional)`.
  - `### Step 5: Git Clone` (`:102`) → `### Step 5` stays; but to keep contiguous
    numbering after collapsing 4/4.5 into 4, renumber Git Clone → `### Step 5`
    remains valid only if you keep 4.5. Choose the simpler scheme: keep clone at
    **Step 5** and rename the dry-run step to **Step 4** (filling the gap left by
    the removed preflight step). Downstream steps 6–9 are unchanged.
- Within the (renumbered) dry-run step body, drop preflight phrasing:
  - `:86` "After preflight checks pass (stdout shows full `[ok]` checklist)" →
    "When `--dry-run` is set".
  - `:98` "No directory is created, no clone occurs, no subprocess is spawned
    beyond preflight" → "...no subprocess is spawned".
- `:189` (Step 9 error handling): change
  "Exit code 1: Runtime failure (git, just init, just check, or preflight
  checks)" → "Exit code 1: Runtime failure (git, just init, or just check)".

#### 5. `docs/specification.md`
**Action**: modify

In the `init_new_package(package_name)` numbered orchestration list
(`:59-74`):

- Delete step `2. Runs preflight checks (tools on PATH, target directory absent,
  template reachable).` (`:61`).
- Renumber the subsequent steps: old 3→2 (git clone), 4→3, 5→4, 6→5, 7→6, 8→7.
  The list becomes a 7-step sequence: resolve path (1), git clone (2), metadata
  (3), strip scaffolding (4), `just init` (5), `just check` (6), return exit code
  (7).

#### 6. `docs/vision.md`
**Action**: delete

- Delete the milestone section **"## V5 — Preflight environment checks before
  cloning"** and its body — `:48-55` (heading through `...half-finished
  scaffold.`). Leave the surrounding V4 and V6 sections and their `## V<n>`
  numbering unchanged (renumbering milestones is out of scope; only the preflight
  section is removed, per `structure.md`).

> **Deviation (Phase 3):** On disk, the docs were already far ahead of the
> plan. Five of the six files (`overview.md`, `architecture.md`, `data_flows.md`,
> `specification.md`, `vision.md`) contained **no** preflight content or
> deleted-symbol references at all — `vision.md` already lacks the V5 section,
> step numbering in `data_flows.md`/`architecture.md`/`specification.md` was
> already contiguous, and `overview.md:7` was already reworded. The only
> remaining preflight mention was a single line in `docs/invocation.md`
> ("...result in git clone errors, not preflight errors."); the "not preflight
> errors" clause was dropped, leaving "...result in git clone errors." No other
> edits were needed to satisfy the `grep -rni preflight docs/` gate.

### Verification
#### Automated
- [x] `just check` passes (docs are not compiled, but this guards against any
      accidental code edits landing in this phase).
      *(format/lint/complexity/typecheck/test all pass — 130 passed. `audit`
      fails on the same pre-existing, unrelated `mcp` 1.28.0 CVE-2026-59950 as
      Phases 1–2, not touched by this phase.)*
#### Manual
- [x] No preflight references anywhere in docs:
      `grep -rni "preflight" docs/` → no output.
- [x] No deleted-symbol references in docs:
      `grep -rnE "PreflightCheck|_verify_required_tools|_verify_target_directory_absent|_verify_template_remote_reachable|_run_preflight_checks|_format_check_line|_REQUIRED_TOOLS|_TOOL_INSTALL_HINTS|_REMOTE_REACHABILITY_TIMEOUT_SECONDS|_PREFLIGHT_HEADER" docs/`
      → no output.
- [x] Step numbering has no gaps/dupes around the removed steps:
      `grep -nE "^### Step [0-9]" docs/data_flows.md` → contiguous `Step 1..9`
      (no `Step 4.5`, no missing `Step 4`); and
      `grep -nE "Step [0-9]" docs/architecture.md` → the flow list reads `Step 0`
      then `Step 1` with no gap.
- [x] Specification list is 7 contiguous items:
      `grep -nE "^  [0-9]+\." docs/specification.md` → the `init_new_package`
      block numbers `1.`–`7.` with no gap.

---

## Final acceptance (matches `design.md` §"Desired End State")

- [ ] `just check` passes end to end.
- [ ] `grep -rn "preflight\|PreflightCheck\|_verify_required_tools\|_REQUIRED_TOOLS\|_PREFLIGHT_HEADER\|_format_check_line" modernpackage/ tests/ docs/`
      → no output.
- [ ] `grep -rni "preflight" docs/` → no output.
- [ ] Clone failures still humanize: `just test tests/test_main.py -k "humanize or clone"`
      → all pass; existing-directory case still caught via
      `_GIT_CLONE_ERROR_MESSAGES` (`main.py:44`).
- [ ] A dry run succeeds with no checklist output:
      `uv run modernpackage accept_pkg_$$ --dry-run; echo "exit=$?"` → `exit=0`,
      no `Preflight checks:` / `[ok]` lines.
</content>
</invoke>
