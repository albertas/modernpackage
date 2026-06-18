# Design Discussion

## Current State

The `modernpackage` CLI scaffolds a new package by executing a fixed,
unconditional sequence once preflight passes. `init_new_package`
(`main.py:602-679`) runs: read-only preflight (`main.py:615`), `git clone` of the
template (`main.py:617-622`), in-place `pyproject.toml` rewrite via
`_write_package_metadata` (`main.py:632-639`), `just init <module>` which renames
`modernpackage/` → `<module>/` and rewrites string occurrences
(`main.py:642-648`, `Justfile:55-69`), then `just check` for validation
(`main.py:662-669`).

Flags are parsed in `parse_args` (`main.py:347-418`) and threaded
`parse_args() → main() → init_new_package(...)` (`main.py:684`, `691-698`). The
only `store_true` boolean is `--version` (`main.py:350-356`); every metadata flag
defaults to `None` (`main.py:363-409`). Output convention: progress/success to
stdout via `print(... )  # noqa: T201`, failures/notices to stderr
(`main.py:592`, `672`, `674-678`). The preflight checklist
(`_run_preflight_checks`, `main.py:573-599`) is the only existing read-only,
non-mutating stage; lines are formatted by `_format_check_line` with a
two-space indent and a left-padded marker (`main.py:507-510`).

There is **no existing `--dry-run`/preview path** — a Grep for `dry`/`preview`
finds nothing (research §Cross-Cutting). The Python code is unaware of the exact
file list `just init` renames; those mutations live in the template's `Justfile`
(research §Open Areas), so the code only inspects exit codes.

## Desired End State

A `--dry-run` flag previews what a real run *would* create and rename, then exits
**0 without** cloning, rewriting metadata, or invoking any scaffolding
subprocess (`git clone`, `just init`, `just check`). Verification:

- `modernpackage foo --dry-run` prints a plan (target directory, the template it
  would clone, the metadata substitutions it would apply, the
  `modernpackage/ → foo/` rename + version reset) and returns 0.
- A unit test patching `Popen`/`run` asserts `popen_mock.call_count == 0` when
  `--dry-run` is set (mirrors the abort assertion at `test_main.py:385`).
- `parse_args` exposes `dry_run` (test via `sys.argv` patch, `test_main.py:108-118`).
- `main` threads the flag into `init_new_package` (test via patched
  `ArgumentParser` + `init_new_package`, `test_main.py:502-525`).
- `just check` stays green.

## Patterns to Follow

- **Boolean flag**: define `--dry-run` exactly like `--version` —
  `action='store_true', default=False` (`main.py:350-356`). Hyphenated name maps
  to `dry_run` attr.
- **Threading**: add `dry_run` to the keyword-only, defaulted signature of
  `init_new_package` (`main.py:602-610`) and pass it from `main`
  (`main.py:691-698`), matching the existing keyword-passing style.
- **Read-only stage placement**: run the existing preflight first
  (`main.py:615`), then branch on `dry_run` *before* the first mutation (the
  clone at `main.py:617`) — the same "inspect before mutate" ordering preflight
  already establishes (`main.py:573-599`).
- **Output**: plan goes to **stdout** via `print(...)  # noqa: T201`
  (`main.py:592`, `672`). Reuse the two-space-indent line aesthetic of
  `_format_check_line` (`main.py:507-510`); add a header constant alongside
  `_PREFLIGHT_HEADER` (`main.py:504`).
- **Resolved metadata**: the plan should report the already-resolved values
  (flag > env > git > config), since resolution happens in `parse_args`
  (`_resolve_metadata_defaults`, `main.py:411`) before threading. `None` fields
  are "unset" and should be reported as keeping the template literal — matching
  the skip-if-None behavior of `_write_package_metadata` (research §Q3).
- **Testing seams**: patch `Popen`/`run` on the module object
  (`test_main.py:286-294`); use `capsys` to assert plan text. No new mocking
  pattern is needed.

No actively-bad patterns were flagged in research to avoid; the only gap is the
absence of a preview abstraction, which this work introduces minimally.

## Design Decisions

1. **Branch inside `init_new_package`, not in `main`** — Keeping the dry-run
   short-circuit next to the mutations it guards (right after preflight,
   `main.py:615`) keeps `main` a thin dispatcher and ensures the preview reflects
   the same path/normalization (`normalize_module_name`, `main.py:612`) a real
   run uses.

2. **Run preflight during dry-run** — Preflight is strictly read-only
   (research §Q1, §Q5) and surfaces the real blockers (missing tools, occupied
   target directory, unreachable remote). A preview that skipped it could claim
   a run is possible when it isn't. Failures stay caught in `main`
   (`main.py:699-701`). *Assumption*: the `git ls-remote` network probe
   (`main.py:546-552`) is acceptable in dry-run because it neither writes disk
   nor is a "scaffolding subprocess."

3. **Static, high-level plan — do not clone to enumerate files** — The task asks
   to preview "files written, renames," but the exact cloned file list and the
   precise `just init` renames live in the template `Justfile` (research §Open
   Areas); enumerating them would require a clone, which the task forbids. The
   plan therefore describes what the *code* knows: the target directory, the
   template URL it would clone, the specific `pyproject.toml` literal
   substitutions (`_write_package_metadata`, research §Q3), and the
   well-known `just init` outcomes (rename `modernpackage/ → <module>/`, version
   reset to `0.0.1`) drawn from the template recipe.

4. **Exit 0 on a clean preview** — Matches "exit cleanly"; a successful preview
   is not a failure. Preflight-detected blockers still return 1 via the existing
   `RuntimeError` path, so an impossible run is honestly reported.

5. **Dedicated formatting helper** — Add a private `_format_dry_run_plan` /
   `_print_dry_run_plan` (or a `_DRY_RUN_HEADER` constant + inline prints)
   following the `_format_check_line` precedent, keeping `init_new_package`
   readable and the plan independently testable. *Assumption*: a single small
   helper is preferred over inlining (CLAUDE.md simplicity vs. testability).

6. **No `--dry-run` + `--version` interaction** — `--version` already
   short-circuits in `main` before the package branch (`main.py:686-689`); when
   no `package_name` is given, dry-run is a no-op returning 0, consistent with
   today's behavior.

## What We're NOT Doing

- Not cloning to a temp directory to enumerate the real file tree.
- Not parsing or simulating the template `Justfile` to derive an exact rename
  list — only the known, documented outcomes are reported.
- Not adding dry-run support to `just init`/`just check` themselves.
- Not changing metadata resolution, validation, or any existing flag behavior.
- Not introducing a general "plan object" abstraction beyond what this one
  preview needs.
- Not touching the e2e test (`tests/test_e2e.py`); it exercises the real
  mutating path.

## Open Risks

- **Preview fidelity**: because we don't clone, the plan can drift from reality
  if the template's `Justfile` changes its renames/version logic. Mitigation:
  describe outcomes at the level the code already asserts in the e2e test
  (`test_e2e.py:82-90`) and keep wording generic where the file list is unknown.
- **Network probe in dry-run**: the `git ls-remote` preflight makes a network
  call; if reviewers consider any external call out of scope for a "preview,"
  this may need to become skippable. Flagged for confirmation.
- **Output assertions**: exact stdout is asserted elsewhere
  (`test_main.py:641-665`); the new plan text must be stable and covered by its
  own test to avoid brittle coupling.
