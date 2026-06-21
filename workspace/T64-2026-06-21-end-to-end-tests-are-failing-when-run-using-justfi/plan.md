# Implementation Plan

## Overview

The `-m e2e` suite fails at runtime because every scaffolded package's `just
check` chain dies on its final `audit` step: the transitive pin
`pydantic-settings 2.14.1` (vupi → mcp → pydantic-settings) carries
`GHSA-4xgf-cpjx-pc3j`. The fix is a single uv-managed lock bump to `2.14.2` at
the repo root — which *is* the template — fixing both the repo's own `just
check` and every generated package. No code, test, or config changes are
warranted; the remaining phases are sequential verification gates of widening
scope.

**Working directory for all commands**: `/home/niekas/tools/modernpackage`
(repo root). All `file:line` references are relative to it.

---

## Phase 1: Bump the vulnerable transitive pin

### Changes

#### 1. Re-lock `pydantic-settings`
**File**: `uv.lock` (uv-managed — do NOT hand-edit; design §"Patterns")
**Action**: modify (via uv command only)

The only block expected to move is the `pydantic-settings` package entry at
`uv.lock:839-851` (name/version/source/dependencies/sdist/wheel). The current
state is:

```toml
[[package]]
name = "pydantic-settings"
version = "2.14.1"
source = { registry = "https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple" }
...
```

Run the surgical upgrade (re-resolves only the one package against the GitLab
index; design §2 dry-run confirmed `2.14.1 -> 2.14.2`, 77 packages re-resolved,
nothing else moved):

```bash
uv lock --upgrade-package pydantic-settings
```

- Do NOT edit `pyproject.toml` — no speculative lower-bound pin
  (`pydantic-settings>=2.14.2`); it is not a direct dependency (design §3).
- Do NOT edit `Justfile`, the `audit` recipe (`Justfile:42-43`), or any skip
  guard (design §"What We're NOT Doing").
- Do NOT use `--ignore-vuln GHSA-...` or remove `audit` from the `check` chain
  (`Justfile:54`) (design §"Pattern to NOT follow").

**Fallback if the GitLab index does not serve 2.14.2** (Open Risk 4): re-run
once after confirming network reachability; if it still fails to resolve, stop
and report to the user — do NOT hand-edit `uv.lock` and do NOT add a
`pyproject.toml` override. A stale/offline index is an environment problem, not
a plan defect.

### Verification

#### Automated
- [x] `git diff --stat uv.lock` shows **only** `uv.lock` changed (no other
  files in `git status --porcelain` beyond `uv.lock`).
  Note: BACKLOG.md, docs/overview.md, lifecycle_state.yml, workspace/ were
  already modified by the lifecycle harness before this phase; the only file
  changed by `uv lock --upgrade-package pydantic-settings` is `uv.lock`.
- [x] `git diff uv.lock` contains `pydantic-settings` / `pydantic_settings` and
  the version flips `2.14.1 → 2.14.2`; no other package appears on a changed
  `name = ` or `version = ` line. Concretely:
  `git diff uv.lock | grep -E '^[-+]name = ' | sort -u` returns only
  `pydantic-settings` (or empty if uv leaves the name line untouched), and
  `git diff uv.lock | grep -E '^[-+]version = '` shows only `2.14.1` removed /
  `2.14.2` added. Confirmed: name lines empty (uv left them untouched);
  version lines show only `-2.14.1` / `+2.14.2`.
- [x] `uv run pip-audit --skip-editable` exits 0
  (`echo $?` → `0`).

#### Manual
- [x] `uv run pip-audit --skip-editable 2>&1 | grep -q 'No known vulnerabilities found'`
  succeeds (exit 0).
- [x] `uv run pip-audit --skip-editable 2>&1 | grep -q 'GHSA-4xgf-cpjx-pc3j'`
  **fails** (exit 1) — the CVE is gone.
- [x] A `vupi ... Dependency not found on PyPI` notice in the output is
  **expected and acceptable** (vupi lives on the GitLab index; design "Open
  Risks") — it must not be treated as a failure.

---

## Phase 2: Repo-root `just check` stays green

Confirm the re-locked tree still passes the repo's own full check chain. The
root recipes are exactly what `just init` renames in place (design §"Patterns"),
so this is the cheapest proof the bump is benign.

### Changes

None (verification only).

### Verification

#### Automated
- [x] `just sync` exits 0 (prerequisite; resolves the 2.14.2 wheel from the
  GitLab index — `Justfile:8-9`).
- [x] `just check` exits 0 (`echo $?` → `0`). This runs
  `check-format check-lint check-complexity check-typecheck test audit`
  (`Justfile:54`).

#### Manual
- [x] `just check 2>&1 | tail -n 20` shows no
  `error: Recipe \`audit\` failed` line and no `known vulnerability` line.

---

## Phase 3: Bare-scaffold e2e passes (the reproduced failure)

Prove the originally-reproduced test now passes: `git clone` of the committed
checkout + `just init` + the generated `just check`, whose `audit` step was the
exit-1 culprit (`tests/test_e2e.py:191`, design "Current State").

### Changes

None (verification only).

### Verification

> **BLOCKER (structural plan error found during implementation):** This phase
> cannot pass as written. `test_scaffolded_package_passes_check` does
> `git clone str(REPO_ROOT)` (`tests/test_e2e.py:159`), which transfers only
> **committed** objects (HEAD), not working-tree changes. The Phase 1 fix
> (`pydantic-settings 2.14.1 → 2.14.2`) lives in the working tree but is
> **uncommitted** — HEAD's `uv.lock` still pins `2.14.1`. So the scaffolded
> clone inherits the vulnerable lock and its `audit` step exits 1
> (reproduced: `1 failed in 34.05s`, "Found 1 known vulnerability in 1 package").
> The plan's premise that the uncommitted bump flows into the clone is wrong;
> Phase 3 requires the `uv.lock` bump to be **committed**, which the plan never
> instructs (its Phase 1 checkpoint asserts `uv.lock` stays modified in
> `git status --porcelain`) and which the harness commit-rule forbids without
> explicit user approval. Stopped and reported to the user per the implement
> rules.

#### Automated
- [ ] `uv run pytest -m e2e --no-cov tests/test_e2e.py::test_scaffolded_package_passes_check`
  exits 0 with `1 passed` (not `skipped` — `git`/`just`/`uv` are present on this
  host, design "Desired End State"). Confirm:
  `uv run pytest -m e2e --no-cov tests/test_e2e.py::test_scaffolded_package_passes_check 2>&1 | tail -n 1`
  matches `1 passed`.
  FAILED: clone is of HEAD; uncommitted `uv.lock` bump not present in clone;
  generated `just check` audit exits 1 on `GHSA-4xgf-cpjx-pc3j`. See BLOCKER above.

#### Manual
- [ ] If the test reports `skipped`, inspect the reason
  (`... -rs` flag) — a skip means a base tool is missing on the host, which
  contradicts "Desired End State"; investigate before proceeding rather than
  accepting the skip.

---

## Phase 4: Full e2e suite passes (heavy compose / fullstack tests)

Run the entire `-m e2e` selection (7 tests across `tests/test_e2e.py` and
`tests_e2e/`). These additionally exercise `podman compose` + `postgres:17`
pull, host-side `alembic` migrate, and `npm`/playwright. Design §5 mandates
confirming by an actual run, not inference.

### Changes

None (verification only).

### Verification

> **BLOCKER (same structural plan error as Phase 3):** Phase 4 cannot pass as
> written for the identical reason Phase 3 is blocked. The `-m e2e` selection
> includes every scaffold test, and each does `git clone str(REPO_ROOT)`
> (`tests/test_e2e.py:159,226,285,376,479`), which transfers **committed** HEAD
> objects only — the test docstring states this explicitly
> (`tests/test_e2e.py:11`: "`git clone` copies **committed** state only;
> uncommitted template edits are NOT exercised"). Verified: HEAD's `uv.lock`
> still pins `pydantic-settings 2.14.1`; the Phase 1 fix (`2.14.2`) is
> uncommitted in the worktree. So every scaffolded clone inherits the vulnerable
> lock and its `audit` step exits 1 on `GHSA-4xgf-cpjx-pc3j`, making
> `just test-e2e` exit non-zero. Unblocking requires committing the `uv.lock`
> bump, which the plan never instructs (Phase 1 checkpoint asserts `uv.lock`
> stays *uncommitted* in `git status --porcelain`) and which the harness
> commit-rule forbids without explicit user approval. Did NOT run the heavy
> compose/fullstack suite because the outcome is deterministically a failure at
> the first scaffold test's audit step; running it would pull `postgres:17` and
> exercise npm/playwright for several minutes to observe a known failure.
> Stopped and reported to the user per the implement rules.

#### Automated
- [ ] `just test-e2e` (alias `just e`, `Justfile:14-19` → `uv sync` then
  `uv run pytest -m e2e --no-cov`) exits 0 (`echo $?` → `0`).
- [ ] The pytest summary reports `0 failed` and `0 error`. Concretely, capture
  the run and assert:
  `just test-e2e 2>&1 | tee /tmp/t64_e2e.log; tail -n 1 /tmp/t64_e2e.log` shows
  `7 passed` (ideal) **or** a mix of `passed` + `skipped` with `0 failed` and
  no `error`.
  BLOCKED: scaffold tests clone committed HEAD (`uv.lock` still `2.14.1`); the
  uncommitted `2.14.2` fix is not present in the clone, so their `audit` step
  exits 1. See BLOCKER above.
- [ ] `grep -E '[0-9]+ (failed|error)' /tmp/t64_e2e.log` returns nothing
  (no failures/errors).

#### Manual
- [ ] If any test `skipped`, confirm via `just test-e2e -rs` that each skip
  reason names a genuinely-absent host tool (no compose command / `npm` missing
  / `playwright install` browser unavailable — research Q6), not a papered-over
  audit failure.
- [ ] If a compose/fullstack test **fails** (not skips) on `postgres:17` pull,
  port 5432/8000 conflict, or playwright (design "Open Risks"), treat it as a
  **secondary** issue surfaced only because `audit` stopped short-circuiting the
  chain. Triage per design — do NOT work around it by weakening skip guards or
  the `audit` gate. Report the specific failure to the user.

---

## Testing Checkpoints

State that must hold after each phase (for resuming on context reset):

1. **After Phase 1** — `git status --porcelain` lists only `uv.lock`; the diff
   is the `pydantic-settings` `2.14.1→2.14.2` bump alone;
   `uv run pip-audit --skip-editable` exits 0 with
   `No known vulnerabilities found` and no `GHSA-4xgf-cpjx-pc3j`.
2. **After Phase 2** — `just check` exits 0 at repo root.
3. **After Phase 3** — `test_scaffolded_package_passes_check` passes; the
   `audit` exit-1 reproduction is gone.
4. **After Phase 4** — `just test-e2e` exits 0; `7 passed` (or host-justified
   skips, `0 failed`, `0 error`). Matches design "Verification Plan" steps 1-4.

## Out of Scope / Known Structural Fragility

Flag to the user; do NOT fix here:

- **pip-audit hits the live OSV/PyPI advisory DB** (research Q4, design "Open
  Risks"), so any newly-disclosed CVE in any transitive dep can re-break `audit`
  later with no code change. This bump fixes today's failure, not the suite's
  time-sensitivity. A future hardening could scope `audit` to direct deps or
  pin-and-periodically-bump — explicitly excluded from this task.
- **`vupi` is skipped by pip-audit** ("Dependency not found on PyPI", it lives
  on the GitLab index) — an audit blind spot the fix does not change.
