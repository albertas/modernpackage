# Structure Outline

## Approach

Add a `_run_preflight_checks(target_path)` orchestrator that iterates an ordered,
immutable registry of `PreflightCheck` records, printing a one-line-per-check
ASCII checklist to **stdout** (`[ok]` / `[FAIL]`). The existing verifiers stay
unchanged — they keep raising `RuntimeError`; the orchestrator wraps them and
replaces the three direct calls at `main.py:555-557`. Stdlib-only, no styling, no
new dependency. This is one module (`modernpackage/main.py`) with no DB/API/UI,
so vertical slices are cut along **behavior paths** (happy path → failure path →
regression), each end-to-end and independently testable through the public
`init_new_package` / `_run_preflight_checks` seam.

---

## Phase 1: Happy-path checklist emitter

Introduce the check registry data model and the orchestrator, and emit the full
`[ok]` checklist on a clean run. Wires into `init_new_package`, replacing the
three direct verifier calls. After this phase a successful scaffold prints the
checklist and proceeds to `Popen` exactly as before.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `@dataclass(frozen=True) PreflightCheck { label: str, run: Callable[[], None] }` — new record (field comments per Code Best Practices).
- `_PREFLIGHT_HEADER: str = 'Preflight checks:'` — new constant.
- `_format_check_line(label: str, ok: bool) -> str` — new helper; returns `f'  {"[ok]" if ok else "[FAIL]":<6} {label}'` (marker right-padded to width 6 so labels align).
- `_run_preflight_checks(target_path: Path) -> None` — new orchestrator. Builds the ordered registry per-call (so `_verify_target_directory_absent` binds `target_path` via closure):
  1. `PreflightCheck('package name valid', lambda: None)` — display-only (Decision 5; name already validated at argparse time).
  2. `PreflightCheck(f'required tools on PATH ({", ".join(_REQUIRED_TOOLS)})', _verify_required_tools)` — label derived from `_REQUIRED_TOOLS`, not hardcoded.
  3. `PreflightCheck('target directory available', lambda: _verify_target_directory_absent(target_path))`.
  4. `PreflightCheck('template remote reachable', _verify_template_remote_reachable)`.
  Prints `_PREFLIGHT_HEADER`, then for each check calls `run()` and prints the `[ok]` line (`print(..., )  # noqa: T201`).
- `init_new_package` (`main.py:555-557`): replace the three calls with a single `_run_preflight_checks(new_package_path)`.

**Verify**: `just test` passes. New test patches `shutil.which`→present, `run`→`returncode=0`, `Popen`→mock; calls `init_new_package` (or `_run_preflight_checks(tmp_path/'pkg')`) and asserts `print_mock.call_args_list` (or `capsys.readouterr().out`) contains, in order: `Preflight checks:`, `  [ok]   package name valid`, `  [ok]   required tools on PATH (git, just, uv)`, `  [ok]   target directory available`, `  [ok]   template remote reachable`. Existing happy-path tests still reach `Popen` (`popen_mock.call_count >= 1`).

---

## Phase 2: Failure-path `[FAIL]` marking

Extend the orchestrator so the first verifier that raises is marked `[FAIL]`,
prior checks show `[ok]`, the `RuntimeError` re-propagates to `main()` (stderr
remediation unchanged), and `Popen` is never reached. Delivers the "at a glance
what failed" value on top of Phase 1.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_run_preflight_checks`: wrap each `check.run()` in `try/except RuntimeError`; on catch, print `_format_check_line(check.label, ok=False)` to stdout, then `raise` (bare re-raise preserves the original message and `__cause__` chain). Checks after the failure are not printed (Decision 3 — abort on first failure; lines reflect only what ran).

**Verify**: `just test` passes. New test patches `run` so `_verify_template_remote_reachable` raises (e.g. `returncode=128` or `TimeoutExpired`), `Popen`→mock; asserts `pytest.raises(RuntimeError, match=...)`, and via `capsys` that `.out` contains the prior three lines as `[ok]` and `  [FAIL] template remote reachable`, while the remediation text appears in `.err` (read `.out`/`.err` separately). Assert `popen_mock.call_count == 0`. Add an analogous test for an earlier-check failure (e.g. missing `git`) confirming only the lines up to and including the `[FAIL]` line are printed.

---

## Phase 3: Regression hardening of existing output assertions

No new feature — confirm the inserted checklist lines do not break existing
print/`capsys` assertions, and fix any index-based ones. Keeps the full suite
green (Desired End State criterion (c)).

**Files**: `tests/test_main.py` (assertion adjustments only, no production code)

**Key changes**:
- Audit tests inspecting `print_mock.call_args_list` for exact success messages (`test_main.py:489, 572, 597`) and the `popen_mock.call_count == 0` preflight-abort tests (`test_main.py:385, 400, 415, 442, 637, 1087`). Ensure each still locates its target message by content (filter), not by positional index; update any index-based assertion that now shifts due to the extra checklist lines.

**Verify**: `just test` passes with zero failures (`-m 'not e2e'` default). Then `just check` passes end-to-end (format, lint, complexity ≤ 10, typecheck, test, audit) — confirms `_run_preflight_checks` stays under the McCabe limit and no lint regressions on the new `# noqa: T201` prints.

---

## Testing Checkpoints

- **After Phase 1**: `_run_preflight_checks` exists; a clean run prints
  `Preflight checks:` + four `[ok]` lines (in registry order, tools label derived
  from `_REQUIRED_TOOLS`) to stdout and still reaches `Popen`. `init_new_package`
  has a single preflight call site. Failure behavior is unchanged from baseline
  (errors still raise, just without a `[FAIL]` line yet).
- **After Phase 2**: A failing check prints its line as `[FAIL]` with prior lines
  `[ok]`; the `RuntimeError` propagates to stderr via `main()`; `Popen` is never
  reached (`popen_mock.call_count == 0`). Checklist `.out` and remediation `.err`
  are on separate streams.
- **After Phase 3**: Entire suite (`just test`) and `just check` pass; no existing
  print-assertion test broken by the added checklist lines.

**Note on slicing**: this design is a single-module CLI change with no
DB/service/API/UI layers, so the slices are behavior-path slices rather than
layer-spanning ones. Each is still independently testable end-to-end via
`init_new_package`/`_run_preflight_checks`. Phases 1 and 2 share the orchestrator
function but are separable: Phase 1 delivers the success checklist standalone;
Phase 2 adds failure marking and is independently valuable even if reverted.
