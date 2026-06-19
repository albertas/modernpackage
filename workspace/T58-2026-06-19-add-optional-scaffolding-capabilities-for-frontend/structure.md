# Structure Outline

## Approach

The optional, opt-in frontend scaffolding this task asks for **already exists**
(delivered in T53–T57). Per `design.md`, T58 is a **verification & consolidation**
pass, not new feature work: confirm the `--fullstack`/`--reactjs` capability end to
end via the existing suites, and touch code **only** to close concrete gaps the
verification surfaces. The natural slices are therefore capability-verification
slices — each exercises the full path (CLI flag → strip → inject → `just init` →
`just check`/template tests) for one user-visible behavior and can be run
independently. There is no horizontal "all DB / all API / all UI" work because the
layers are already built; slicing is by *behavior verified*, not by *layer added*.

> **Note (per Rules):** because the design is verification-only, slices cannot be
> "new vertical features." Each phase instead verifies one complete behavior across
> all its layers (flag parse → injection → generated project → its own checks). If a
> phase finds a gap, the fix is implemented within that same phase, keeping the slice
> vertical. Expect the likely outcome to be a no-op change set plus a verification
> record (`design.md` Open Risks).

---

## Phase 1: Unit suite — flags, injection wiring, clean default

Confirm flag/alias parsing, `_strip_scaffolding` (both template trees removed),
backend+frontend injection, and the "no-flag output is byte-identical" guarantee all
hold at the unit level. This is the cheapest, broadest gate and proves the wiring
before any real clone.

**Files** (read/verify only): `modernpackage/main.py`, `tests/test_main.py`
**Key surfaces exercised** (existing, no signature changes expected):
- `parse_args() -> argparse.Namespace` — `--backend`/`--fastapi`, `--fullstack`/`--reactjs`
- `init_new_package(..., *, backend: bool, fullstack: bool) -> int`
- `_inject_templates(package_path: Path, *, fullstack: bool) -> None`
- `_add_frontend(package_path: Path) -> None` (no Python deps, no subprocess)

**Verify**: `just test` passes (all 148 unit tests). Targeted check:
`just test -k "frontend or fullstack or strip_scaffolding"` passes and collects
the four frontend tests (`test_add_frontend_copies_template_and_appends_recipes`,
`test_add_frontend_no_npm_or_subprocess`,
`test_init_new_package_invokes_add_frontend_when_fullstack`,
`test_init_new_package_backend_only_does_not_add_frontend`). Confirm exit code 0.

---

## Phase 2: Default scaffold has no frontend/backend leak (negative e2e)

Prove a no-flag `modernpackage myapp` produces a base package with **zero** frontend
or backend artifacts — the clean-default contract that makes the opt-in safe.

**Files** (verify only): `tests/test_e2e.py`
(`test_scaffolded_package_has_no_backend_or_frontend`, line ~196),
`modernpackage/main.py` (`_SCAFFOLDING_PATHS_TO_DELETE`, incl. `frontend_template`).

**Verify**: `just test-e2e -k "no_backend_or_frontend"` passes (exit 0). Confirms a
real clone+strip+init yields no `frontend/`, no `frontend-*` recipes, no FastAPI
deps. If `git`/`just`/`uv` missing the test `pytest.skip`s — re-run after installing
required tools; a skipped negative case is **not** a pass.

---

## Phase 3: Fullstack scaffold builds and its frontend tests pass (fullstack e2e)

The core slice: `--fullstack` injects backend **and** an isolated `frontend/` React
app; the generated project renames the `modernpackage` token, installs Node deps, and
its Vitest suite passes. Crosses every layer (flag → inject → `git add -A` →
`just init` rename → `just frontend-install` → `just frontend-test`).

**Files** (verify only): `tests/test_e2e.py`
(`test_scaffolded_fullstack_package_passes_check`, line ~272), `frontend_template/`
(`package.json`, `vite.config.ts`, `src/App.test.tsx`, placeholder `src/client/index.ts`).

**Verify**: `npm --version` succeeds (confirmed available: 11.11.0), then
`just test-e2e -k "fullstack"` passes (exit 0). Asserts: token renamed in
`package.json`/`App.tsx`/`index.html`, `frontend/` present, Vitest run output captured,
and the generated `check:` recipe excludes `frontend-*` recipes. A `pytest.skip` due
to missing `npm` counts as a **failure to verify**, not a pass.

---

## Phase 4: Source repo stays green (`just check`)

Confirm the source repository itself is clean: format, lint, complexity (≤10),
mypy, the full pytest suite, and pip-audit all pass — proving the task introduced no
regressions and the codebase is in a shippable state.

**Files**: whole repo (no edits expected). `pyproject.toml` gates (line-length 120,
C901 ≤10, py3.11).

**Verify**: `just check` exits 0. (Runs `check-format check-lint check-complexity
check-typecheck test audit`.) Also `just test-e2e` (full e2e set, all 4 tests, not
`-k`-filtered) exits 0 with `npm` present.

---

## Phase 5: Gap closure / backlog record (conditional)

Only if Phases 1–4 surface a concrete, in-scope defect. Per `design.md` "What We're
NOT Doing", out-of-scope items (non-root `USER` in `Containerfile`, `main.py`
module-split, real generated client) are **not** fixed here — they are appended to
`BACKLOG.md` instead. Placeholder `src/client/index.ts` stays a placeholder
(Decision 2). If no in-scope gap exists, this phase is a written verification record
confirming the no-op outcome.

**Files** (only if needed): `modernpackage/main.py` and the relevant template file for
an in-scope fix; otherwise `BACKLOG.md` for out-of-scope notes.
**Key changes**: none expected. Any fix must keep `_add_frontend` subprocess-free,
keep `--fullstack` a strict superset of `--backend`, and preserve the byte-identical
no-flag output.

**Verify**: re-run the phase whose gate failed; then `just check` and the relevant
`just test-e2e -k ...` pass. If no change was needed, assert `git diff --stat` is
empty for `modernpackage/` and `frontend_template/` and record that in the task notes.

---

## Testing Checkpoints

After each phase the following should hold (use to resume if context resets):

1. **Phase 1** — `just test` green; the four frontend unit tests collected & passing.
2. **Phase 2** — `just test-e2e -k no_backend_or_frontend` green (not skipped); default
   scaffold provably free of `frontend/` and backend artifacts.
3. **Phase 3** — `just test-e2e -k fullstack` green with real `npm`; `frontend-install`
   + `frontend-test` run, token renamed, `check:` excludes `frontend-*`.
4. **Phase 4** — `just check` exit 0; full `just test-e2e` (4 tests) exit 0.
5. **Phase 5** — either an in-scope fix landed with its gate re-verified, or
   `git diff --stat` empty for source/template trees plus a backlog note for any
   out-of-scope item; task closed as verification-only.

**Most likely terminal state:** all gates green, no code change — surface the
"task is redundant / already-delivered" finding to the user rather than inventing edits
(`design.md` Open Risks).
