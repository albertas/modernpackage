# Structure Outline

## Approach

The deliverable — an e2e test that scaffolds a package from the local template
and asserts `just check` passes — **already exists** as
`test_scaffolded_package_passes_check` (`tests/test_e2e.py:50-74`). Per the
design, scope is **verify-and-harden, not author**: confirm the test conforms to
conventions, confirm it does not regress the default suite, then run it to green.
Touch the file only if verification surfaces a real defect. Because there is no
new feature to build, the "vertical slices" below are independent verification
checkpoints, each runnable unattended and each valuable on its own if a later
phase fails.

---

## Phase 1: Static Conformance of the e2e File

Confirm `tests/test_e2e.py` passes format/lint/complexity/typecheck in isolation
— the cheapest, network-free gate, catching style/type regressions before any
subprocess run.

**Files**: `tests/test_e2e.py` (inspect only; edit only on failure)
**Key changes**: none expected. Existing surface to preserve:
- `_run(command: list[str], cwd: Path, env: dict[str, str] | None) -> subprocess.CompletedProcess[str]` — subprocess boundary helper (`check=False, capture_output=True, text=True`)
- `_GIT_IDENTITY_ENV: dict[str, str]`, `REPO_ROOT: Path`, `REQUIRED_TOOLS: tuple[str, ...]` — module-private constants
- `test_scaffolded_package_passes_check(tmp_path: Path) -> None` — `@pytest.mark.e2e`-marked

**Verify** (all network-free, run from repo root):
- `uv run ruff format --check tests/test_e2e.py` → exit 0
- `uv run ruff check tests/test_e2e.py` → exit 0
- `uv run ruff check --select C901 tests/test_e2e.py` → exit 0
- `uv run mypy tests/test_e2e.py` → exit 0

---

## Phase 2: Default-Suite Integrity (e2e stays excluded)

Confirm the e2e file does not leak into or regress the default run: the `e2e`
marker keeps the test out of `pytest`/`just test`, and the ≥95% coverage gate
still holds.

**Files**: `pyproject.toml:40-43` (marker + `-m 'not e2e'` + coverage; inspect
only), `Justfile:13-17,52` (inspect only)
**Key changes**: none expected. Invariants to confirm:
- `addopts = "... --cov-fail-under=95.0 -m 'not e2e'"` excludes the e2e test by default
- `just check` → `... test ...` inherits `-m 'not e2e'`, so the inner `just check` does **not** recurse into the e2e test

**Verify**:
- `uv run pytest -m 'not e2e' --collect-only -q` → output does **not** list `test_scaffolded_package_passes_check`
- `uv run pytest -m e2e --collect-only -q` → output **does** list `test_scaffolded_package_passes_check` (exactly one e2e item)
- `just check` → exit 0 and stdout contains `Required test coverage of 95.0% reached` (or equivalent pass line); default suite green

---

## Phase 3: End-to-End Execution (the deliverable's guarantee)

Run the actual e2e test against a networked Python-3.14 host with `git`/`just`/
`uv` present and confirm it scaffolds + passes the inner `just check`. This is
the task's core guarantee.

**Files**: none changed (execution only)
**Key changes**: none expected. The test exercises, in order: `git clone REPO_ROOT`
→ `just init scaffoldcheck` (with `_GIT_IDENTITY_ENV`) → assert
`scaffoldcheck/__init__.py` exists and contains `0.0.1` → `just check` exit 0.

**Verify**:
- `just test-e2e` → exit 0, summary shows `1 passed` and no `skipped`
- If it **skips** (`required tool not on PATH` or offline): record the honest
  outcome "test exists and is correct; cannot run here" per the design; do not
  edit the test. Pre-check tools via `command -v git just uv` and Python version
  via `python --version` (expect 3.14) before declaring a true skip vs. a real failure.

---

## Phase 4 (Conditional): Harden a Surfaced Defect

Only if Phase 1–3 surfaces a **real** defect (not an environment skip), apply the
minimal surgical fix to `tests/test_e2e.py`, then re-verify the failing phase.

**Files**: `tests/test_e2e.py`
**Key changes**: minimal, scoped to the observed defect; preserve all patterns in
the design's "Patterns to Follow" (subprocess boundary, tool-skip, git-identity
injection, marker discipline, `_`-prefixed privates). Do **not** switch to the
GitHub-clone production path, add fixtures/`conftest.py`, or add assertions on
`just init` internals.

**Verify**: re-run the verify commands of the phase that failed; all green. Then
re-run Phase 2's `just check` to confirm no default-suite regression.

---

## Out of Scope (from design — do not implement)

- Wiring `just test-e2e` into CI (`.gitlab-ci.yml`, `.github/`) — flagged as the
  single material gap but explicitly deferred (Open Risk).
- Rewriting/restructuring the test, changing scaffolding (`main.py`, `init`/`check`
  recipes), or the `e2e` marker / `-m 'not e2e'` default.
- A second e2e variant exercising the GitHub-clone production path.

---

## Testing Checkpoints

- **After Phase 1**: `tests/test_e2e.py` passes ruff format/lint/C901 and mypy
  in isolation. Safe to resume from here knowing static conformance holds.
- **After Phase 2**: e2e test is collected only under `-m e2e`, never by default;
  `just check` green with ≥95% coverage and no self-recursion.
- **After Phase 3**: `just test-e2e` is green on a networked Py-3.14 host (or a
  documented, tool/network-justified skip) — the deliverable's guarantee is
  demonstrated.
- **After Phase 4 (only if triggered)**: the surfaced defect is fixed with a
  minimal diff and both the failing phase and `just check` are green again.
