# Structure Outline

## Approach

The e2e suite fails at **runtime**, not discovery: the generated package's
`just check` chain dies on `audit` (`pip-audit`) because a transitive pin,
`pydantic-settings 2.14.1` (vupi → mcp → pydantic-settings), carries
`GHSA-4xgf-cpjx-pc3j`. The fix is a single uv-managed lock bump to
`2.14.2`, applied at the repo root — which *is* the template, so it fixes both
the repo's own `just check` and every scaffolded package. No code, test, or
config changes are warranted (design §1).

> **Note on slicing:** This change has no database/service/API/UI layers to
> cross — it is one `uv.lock` edit whose blast radius is "every `audit` step."
> The phases below are therefore **sequential verification gates** of widening
> scope (lock → root check → bare scaffold → heavy compose/fullstack), each
> independently valuable: if Phase 4 reveals an unrelated compose flake, Phases
> 1–3 still prove the actual fix landed. This is the honest decomposition; the
> design (design §"Patterns to Follow") calls for exactly one surgical change.

---

## Phase 1: Bump the vulnerable transitive pin

Re-lock `pydantic-settings` from `2.14.1` to `2.14.2` via uv (never hand-edit
the lock; design §"Patterns"). This is the entire substantive change.

**Files**: `uv.lock` (uv-managed; expect only the `pydantic-settings`
registry/sdist/wheel block at ~`uv.lock:838-848` to move)

**Key changes**:
- Command: `uv lock --upgrade-package pydantic-settings`
- No edits to `pyproject.toml` (no speculative lower-bound pin — design §3)
- No edits to `Justfile` / `audit` recipe / skip guards (design §"NOT doing")

**Verify**:
- `git diff --stat uv.lock` shows only `uv.lock` changed.
- `git diff uv.lock` mentions only `pydantic-settings` and its hashes flipping
  `2.14.1 → 2.14.2` (grep the diff: no other package name on a `name = ` or
  `version = ` line within a changed hunk).
- `uv run pip-audit --skip-editable` exits 0 and stdout contains
  `No known vulnerabilities found` (vupi still reported "not found on PyPI" —
  that is expected, design "Open Risks"; it must NOT report
  `pydantic-settings ... GHSA-4xgf-cpjx-pc3j`).

---

## Phase 2: Repo-root `just check` stays green

Confirm the same re-locked tree still passes the repo's own full check chain —
the root recipes are what `just init` renames in place (design §"Patterns",
research "Cross-Cutting"), so this is the cheapest proof the bump is benign.

**Files**: none (verification only)

**Key changes**: none.

**Verify**:
- `just check` exits 0 (runs
  `check-format check-lint check-complexity check-typecheck test audit`,
  `Justfile:54`).
- `just sync` / `uv sync` succeeds first (prerequisite; needs the GitLab index
  to serve the 2.14.2 wheel — design Assumption in §2 / Open Risk 4).

---

## Phase 3: Bare-scaffold e2e passes (the reproduced failure)

Prove the originally-reproduced test now passes: a clean `git clone` + `just
init` + generated `just check`, whose `audit` step was the exit-1 culprit
(`tests/test_e2e.py:191`, design "Current State").

**Files**: none (verification only)

**Key changes**: none.

**Verify**:
- `uv run pytest -m e2e --no-cov tests/test_e2e.py::test_scaffolded_package_passes_check`
  exits 0, 1 passed (not skipped — `git/just/uv` are present on this host,
  design "Desired End State").

---

## Phase 4: Full e2e suite passes (heavy compose / fullstack tests)

Run the entire `-m e2e` selection (7 tests across `tests/test_e2e.py` and
`tests_e2e/`). These additionally exercise `podman compose` + `postgres:17`
pull, host-side `alembic` migrate, and `npm`/playwright. The design mandates
confirming these by an actual run, not inference (design §5).

**Files**: none (verification only)

**Key changes**: none.

**Verify**:
- `just test-e2e` (alias `just e`, `Justfile:13-15` → `uv run pytest -m e2e
  --no-cov`) exits 0.
- Final pytest summary line shows `7 passed` — OR any non-pass is an explicit
  `skipped` whose reason names a genuinely-absent host tool (compose / npm /
  playwright browser install — research Q6). Parse the summary: assert
  `0 failed` and `0 error`.
- If a compose/fullstack test *fails* (not skips) on `postgres:17` pull, port
  5432/8000 conflict, or playwright (design "Open Risks"), that is a
  **secondary** issue surfaced only because `audit` stopped short-circuiting —
  triage per design, do not work around by weakening skips or the audit gate.

---

## Testing Checkpoints

State that should hold after each phase (for resuming on context reset):

1. **After Phase 1** — `uv.lock` diff is minimal (`pydantic-settings`
   `2.14.1→2.14.2` only); `uv run pip-audit --skip-editable` exits 0 with
   `No known vulnerabilities found`.
2. **After Phase 2** — `just check` exits 0 at repo root.
3. **After Phase 3** — `test_scaffolded_package_passes_check` passes; the
   `audit` exit-1 reproduction is gone.
4. **After Phase 4** — `just test-e2e` exits 0; `7 passed` (or host-justified
   skips, `0 failed`, `0 error`). Matches design "Verification Plan" steps 1–4.

**Out of scope / known structural fragility** (flag to user, do not fix here):
pip-audit hits the live OSV/PyPI DB, so a future newly-disclosed CVE in any
transitive dep can re-break `audit` with no code change (design "Open Risks").
A future hardening could scope `audit` to direct deps or pin-and-bump
periodically — explicitly excluded from this task.
