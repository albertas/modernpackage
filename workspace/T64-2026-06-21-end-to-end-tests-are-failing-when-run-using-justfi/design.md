# Design Discussion

## Current State

The `e2e`-marked suite is collected and dispatched correctly — discovery is **not**
the problem (research.md "Open Areas"). `just e` → `test-e2e` runs
`uv run pytest -m e2e --no-cov` (`Justfile:17-19`), which overrides the default
`-m 'not e2e'` selector (`pyproject.toml:40`) and collects exactly 7 tests
(verified: `7/153 tests collected`).

The failure is at **runtime**, reproduced here against
`tests/test_e2e.py::test_scaffolded_package_passes_check` (`tests/test_e2e.py:191`):

- Each e2e test `git clone`s the committed checkout, runs `just init`, then asserts
  the generated package's `just check` returns 0 (research Q3).
- `check` = `check-format check-lint check-complexity check-typecheck test audit`
  (`Justfile:54`). Format, lint, complexity, typecheck, and test **all pass**.
- The chain dies on the final step, `audit` → `uv run pip-audit --skip-editable`
  (`Justfile:42-43`):

  ```
  Found 1 known vulnerability in 1 package
  Name              Version ID                  Fix Versions
  pydantic-settings 2.14.1  GHSA-4xgf-cpjx-pc3j 2.14.2
  error: Recipe `audit` failed on line 43 with exit code 1
  ```

`pydantic-settings 2.14.1` is **transitive**: `vupi>=0.0.10` (`pyproject.toml:36`)
→ `mcp` → `pydantic-settings` (`uv.lock` line ~530 lists it under `mcp`;
the pin is at `uv.lock:838-840`). Because the e2e test clones the **committed**
state (including `uv.lock`) and `just init` keeps the lock, every generated package
inherits the vulnerable pin, so `just check` fails for **all 7** e2e tests (each one
runs the same `audit` step before any compose/npm work).

## Desired End State

`just e` (equivalently `just test-e2e`) exits 0 with all 7 e2e tests passing (or
legitimately skipped where a host tool is genuinely absent — but on this host
`git/just/uv/npm/podman/nproc` are all present, so they should run, not skip).

Verify with:
```
just test-e2e            # all 7 selected, 0 failed
uv run pip-audit --skip-editable   # "No known vulnerabilities found" (vupi still skipped: not on PyPI)
```

## Patterns to Follow

- **Lock-pin via uv, don't edit `uv.lock` by hand.** The lock is uv-managed
  (`uv.lock:838-848` shows registry/sdist/wheel hashes). Fix with
  `uv lock --upgrade-package pydantic-settings`; dry-run confirms a clean
  single-line resolution `2.14.1 -> 2.14.2`, 77 packages re-resolved, nothing else
  moved.
- **Dependencies resolve through the GitLab index**, not plain PyPI
  (`pyproject.toml:103-106`); the `pydantic-settings` source is that mirror
  (`uv.lock:840`). The fix must resolve there — the dry-run already proved it does.
- **The repo root IS the template** (research "Cross-Cutting"): the same
  `Justfile`/`pyproject.toml`/`uv.lock` that `just check` runs at repo root are
  what `just init` renames in place. Fixing the root lock fixes both the repo's own
  `just check` and every scaffolded package — one change, both surfaces.
- **Graceful host-boundary skips already exist** (`tests/test_e2e.py:151-153`,
  compose/npm/playwright guards, research Q6). Do not add new skips to paper over
  the audit failure — the vuln is real and must be fixed, not skipped.

### Pattern to NOT follow

- Do **not** silence pip-audit with `--ignore-vuln GHSA-...`. That hides a real,
  already-fixed CVE and would rot (the ignore lingers after the fix ships).
- Do **not** remove `audit` from the `check` chain (`Justfile:54`). The template's
  value proposition is that generated packages get a security gate; removing it
  changes scaffold behavior and is out of scope.

## Design Decisions

1. **Root cause = the audit vulnerability, not test/discovery logic** — reproduced
   directly (`tests/test_e2e.py:191` assertion `1 == 0`, recipe `audit` exit 1).
   No pytest-config, marker, `sys.path`, or scaffolding-helper change is warranted;
   research confirmed those paths are clean.

2. **Fix = `uv lock --upgrade-package pydantic-settings` (→ 2.14.2)** — minimal and
   surgical (CLAUDE.md §3). 2.14.2 satisfies `mcp`'s existing range (the dry-run
   resolved without touching `mcp` or anything else), so no source-level constraint
   is needed. Assumption: the GitLab index serves the 2.14.2 wheel — supported by
   the successful dry-run resolution.

3. **No explicit lower-bound pin added to `pyproject.toml`** — `pydantic-settings`
   is not a direct dependency; adding `pydantic-settings>=2.14.2` as an override
   would introduce a dep the project doesn't otherwise declare, to constrain a
   transitive of a tool (vupi). Kept out to avoid speculative config (CLAUDE.md §2).
   The regression risk is recorded under Open Risks instead.

4. **Leave `vupi` in the generated package's dev group** — vupi is what drags
   `mcp`→`pydantic-settings` into every scaffold, so removing it would also remove
   the vuln. But that is a scaffolding-surface change (which tools ship in a
   generated package) far beyond "make the failing tests green," so it is excluded.

5. **Verify the heavier tests with a full run, not by assumption** — the bare
   scaffold test was reproduced; the backend/fullstack tests
   (`tests_e2e/*`, `tests/test_e2e.py:353,452`) share the same `audit` gate and
   should unblock with the same fix, but they additionally exercise
   `podman compose` + `postgres:17` pull + `npm`/playwright. Confirm green by
   actually running `just test-e2e` end-to-end, not by inference.

## What We're NOT Doing

- Not touching pytest config, markers, `addopts`, `norecursedirs`, `__init__.py`
  layout, or the `tests/` vs `tests_e2e/` asymmetry (`pyproject.toml:40-44,77-79`) —
  discovery works.
- Not refactoring the duplicated infra helpers across `tests/test_e2e.py` and
  `tests_e2e/_scaffold.py` (research "Cross-Cutting"); intentional duplication,
  unrelated to the failure.
- Not editing `backend_template`/`frontend_template`, scaffolding helpers in
  `modernpackage/main.py`, or the `just init` flow.
- Not removing/weakening the `audit` step or any e2e skip guard.
- Not hand-editing `uv.lock`.

## Open Risks

- **pip-audit hits the live OSV/PyPI advisory DB** (research Q4), so the e2e suite
  is inherently time-sensitive: any *newly disclosed* vuln in any transitive dep
  will re-break `audit` later, with no code change. Bumping `pydantic-settings`
  fixes today's failure but does not make the suite immune. Worth flagging to the
  user as a structural fragility (a future hardening could pin-and-periodically-bump
  or scope audit to direct deps — explicitly out of scope here).
- **`vupi` is "Dependency not found on PyPI"** in pip-audit output (it lives on the
  GitLab index) and is therefore *skipped* by the audit, not scanned. The fix does
  not change that; just noting the audit's blind spot.
- **Secondary failures in compose/fullstack tests** may surface only once `audit`
  stops short-circuiting the chain — e.g. `postgres:17` image pull, port 5432/8000
  conflicts, playwright browser install, or network flakiness (research Q6). These
  are guarded by skips where the *tool* is missing, but an in-test runtime error
  (not a missing tool) would still fail. The full `just test-e2e` run in
  verification will reveal any of these; address them only if they appear.
- **Re-locking may move 2.14.1→2.14.2 only**, but a stale/offline GitLab index on
  CI could fail the `uv sync` prerequisite (`Justfile:18`). The dry-run succeeded
  on this host; CI parity is assumed, not verified.

## Verification Plan (success criteria)

1. `uv lock --upgrade-package pydantic-settings` → diff shows only the
   `pydantic-settings` bump in `uv.lock`. → verify: `git diff uv.lock` is minimal.
2. `uv run pip-audit --skip-editable` → no known vulnerabilities. → verify: exit 0.
3. `just test-e2e` → 7 passed (or host-justified skips). → verify: exit 0.
4. Repo's own `just check` still green (same lock now drives it). → verify: exit 0.
