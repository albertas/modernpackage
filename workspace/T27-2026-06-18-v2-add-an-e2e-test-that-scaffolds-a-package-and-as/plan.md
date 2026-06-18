# Implementation Plan

## Overview

The deliverable — an e2e test that scaffolds a package from the local template and
asserts the result passes `just check` — already exists as
`test_scaffolded_package_passes_check` (`tests/test_e2e.py:50-74`). Scope is
**verify-and-harden, not author**: confirm static conformance, confirm the test
stays out of the default suite, run it to green, and only edit the file if a real
defect surfaces.

> **Implementer note on commands.** This repo runs tooling through `uv` and the
> `Justfile`. Prefer `just <recipe>` where one exists (CLAUDE.md §5). The
> per-file `uv run ...` commands below are used only where a `just` recipe would
> pull in the whole `modernpackage tests` tree and obscure which file failed —
> they reproduce the exact tool invocation the recipe uses, scoped to one file.
> All commands run from the repo root `/home/niekas/tools/modernpackage` unless
> noted. Ruff line-length is 88 and McCabe max-complexity is 8
> (`pyproject.toml:57,79`) — cite these rather than generic defaults.

---

## Phase 1: Static Conformance of the e2e File

### Goal
Confirm `tests/test_e2e.py` passes format/lint/complexity/typecheck in isolation —
the cheapest, network-free gate. Catches style/type regressions before any
subprocess run.

### Changes

#### 1. e2e test module
**File**: `tests/test_e2e.py`
**Action**: inspect only — **no edit expected**.

Surface to preserve exactly (do not rename, reorder, or re-signature):

```python
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')
_GIT_IDENTITY_ENV: dict[str, str] = { 'GIT_AUTHOR_NAME': 'e2e', ... }

def _run(command: list[str], cwd: Path, env: dict[str, str] | None = None) \
        -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env,
                          check=False, capture_output=True, text=True)  # noqa: S603

@pytest.mark.e2e
def test_scaffolded_package_passes_check(tmp_path: Path) -> None:
    ...
```

Conventions already satisfied (verify, do not "improve"): module docstring
documents the intentional deviation (`test_e2e.py:1-15`), `_`-prefixed privates,
full-word identifiers, `# noqa: S603` on the subprocess call, tests-glob ignores
`S101`/`D` (`pyproject.toml:75-76`) so bare `assert` and missing docstrings are
allowed.

### Verification
#### Automated
- [x] `uv run ruff format --check tests/test_e2e.py` → exit 0
- [x] `uv run ruff check tests/test_e2e.py` → exit 0
- [x] `uv run ruff check --select C901 tests/test_e2e.py` → exit 0 (complexity ≤ 8)
- [x] `uv run mypy tests/test_e2e.py` → exit 0

#### Manual
- [x] `grep -q '@pytest.mark.e2e' tests/test_e2e.py` → exit 0 (marker present)
- [x] `grep -q 'check=False, capture_output=True, text=True' tests/test_e2e.py` → exit 0 (subprocess boundary intact) — NOTE: ruff formats kwargs multi-line (lines 44-46); grep for literal single-line string returns exit 1, but all three kwargs are confirmed present via `grep -n`
- [x] `grep -q 'shutil.which' tests/test_e2e.py` → exit 0 (tool-skip guard intact)

---

## Phase 2: Default-Suite Integrity (e2e stays excluded)

### Goal
Confirm the e2e file does not leak into or regress the default run: the `e2e`
marker keeps it out of `pytest` / `just test`, and the inner `just check` does not
recurse into it, and the ≥95% coverage gate still holds.

### Changes

#### 1. pytest config
**File**: `pyproject.toml:39-43`
**Action**: inspect only — **no edit expected**.

Invariant to confirm:
```toml
addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"
markers = ["e2e: tests that perform real external calls (network/subprocess/fs)"]
```
The trailing `-m 'not e2e'` excludes the e2e test by default; `just test-e2e`
overrides it with a later `-m e2e` (last `-m` wins).

#### 2. Justfile recipes
**File**: `Justfile:13-17,52`
**Action**: inspect only — **no edit expected**.

Invariant: `check: ... test ...` (`Justfile:52`) → `test` runs
`uv run pytest -n ... {{args}}` (`Justfile:13-14`) with no `-m` override, so it
inherits `addopts`' `-m 'not e2e'`. The inner `just check` therefore does **not**
recurse into the e2e test.

### Verification
#### Automated
- [x] `uv run pytest -m 'not e2e' --collect-only -q` → output does **not** contain `test_scaffolded_package_passes_check`
- [x] `uv run pytest -m e2e --collect-only -q` → output **does** contain `test_scaffolded_package_passes_check`, and lists exactly one item
- [x] `just check` → exit 0; default suite green with coverage ≥ 95%

#### Manual
- [x] `uv run pytest -m e2e --collect-only -q 2>/dev/null | grep -c 'test_scaffolded_package_passes_check'` → prints `1`
- [x] `uv run pytest -m 'not e2e' --collect-only -q 2>/dev/null | grep -c 'test_scaffolded_package_passes_check'` → prints `0`
- [x] `just check 2>&1 | grep -Eiq 'coverage of 95(\.0)?% reached|passed'` → exit 0 (coverage gate satisfied / suite passed)

---

## Phase 3: End-to-End Execution (the deliverable's guarantee)

### Goal
Run the real e2e test against a networked Python-3.14 host with `git`/`just`/`uv`
present and confirm it scaffolds and passes the inner `just check`. This is the
task's core guarantee.

### Changes
**Files**: none changed (execution only).

The test exercises, in order (`test_e2e.py:56-74`):
1. `git clone REPO_ROOT tmp_path/scaffoldcheck`
2. `just init scaffoldcheck` with `os.environ | _GIT_IDENTITY_ENV`
3. assert `scaffoldcheck/scaffoldcheck/__init__.py` exists and contains `0.0.1`
4. `just check` → exit 0

### Verification

#### Pre-checks (distinguish a true environment skip from a real failure)
Run these first; record their output in the implementation notes:
- [x] `command -v git just uv` → all three print a path (else the test will `pytest.skip`)
  - Output: `/usr/bin/git`, `/usr/bin/just`, `/home/niekas/.local/bin/uv`
- [x] `python --version` (or `uv run python --version`) → expect `Python 3.14.x`
  - Output: `Python 3.14.3`
- [x] network reachable (the inner `just check` runs `uv sync` + networked `pip-audit`): `uv run python -c "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=5)"` → exit 0
  - Output: exit 0 (network OK)

#### Automated
- [x] `just test-e2e` → exit 0; summary shows `1 passed` and `0 skipped`
  - NOTE: First run failed with exit 1 — not a test failure but a coverage gate failure (`--cov-fail-under=95.0` in `addopts` applied to the e2e run; e2e exercises code via subprocess so coverage ≈ 21%). Real defect → proceeded to Phase 4. After Phase 4 fix, `just test-e2e` exits 0 with `1 passed, 23 deselected`.

#### Manual
- [x] `just test-e2e 2>&1 | grep -Eq '1 passed'` → exit 0
- [x] `just test-e2e 2>&1 | grep -Eq '[1-9][0-9]* skipped'` → exit **1** (i.e. nothing was skipped)

#### Skip handling (honest-outcome path, per design Open Risks)
If `just test-e2e` reports `1 skipped` **and** a pre-check above failed
(tool missing, Python ≠ 3.14, or offline):
- [x] N/A — all pre-checks green, test ran and passed; skip path not triggered.

If `just test-e2e` **fails** (non-zero exit, `1 failed`) with all pre-checks
green → this is a real defect; proceed to Phase 4. ✓ Proceeded to Phase 4.

---

## Phase 4 (Conditional): Harden a Surfaced Defect

### Goal
Only if Phase 1–3 surfaces a **real** defect (not an environment skip), apply the
minimal surgical fix and re-verify the failing phase.

### Changes
**File**: `tests/test_e2e.py`
**Action**: modify — minimal, scoped to the observed defect only.

Constraints (from design "Patterns to Follow" / "What We're NOT Doing"):
- Preserve: subprocess boundary (`_run` with `check=False, capture_output=True,
  text=True`), tool-skip loop (`REQUIRED_TOOLS` + `shutil.which` + `pytest.skip`),
  git-identity injection (`os.environ | _GIT_IDENTITY_ENV`), `@pytest.mark.e2e`
  marker, `_`-prefixed privates, full-word identifiers.
- Do **not**: switch to the GitHub-clone production path (`main.py:87-92`); add a
  `conftest.py` or new fixtures (`tmp_path` suffices); add assertions on `just
  init` internals (rename/sed/git history) beyond the existing existence + `0.0.1`
  checks; change the `e2e` marker or the `-m 'not e2e'` default.
- Every changed line must trace to the observed failure (CLAUDE.md §3).

### Verification
**Deviation note**: the plan listed `tests/test_e2e.py` as the file to modify, but the defect was in the `Justfile` `test-e2e` recipe which inherited `--cov-fail-under=95.0` from `addopts`. The e2e test runs production code as a subprocess, so Python-level coverage stays near 21%. Minimal surgical fix: added `--no-cov` to the `test-e2e` recipe in `Justfile`. Every changed line traces to the observed failure (CLAUDE.md §3).

#### Automated
- [x] Re-run every automated command of the phase that failed → all exit 0
  - `just test-e2e` → exit 0; `1 passed, 23 deselected in 32.03s`
- [x] `just check` → exit 0 (no regression to the default suite from the edit)
  - Coverage: 100%; `23 passed in 4.56s`

#### Manual
- [x] `just test-e2e 2>&1 | grep -Eq '1 passed'` → exit 0
- [x] `git diff --stat tests/test_e2e.py` → `tests/test_e2e.py` not changed; only `Justfile` changed (+1 line, `--no-cov` added to `test-e2e` recipe)

---

## Out of Scope (do not implement)

- Wiring `just test-e2e` into CI (`.gitlab-ci.yml`, `.github/`) — the single most
  material gap, but explicitly deferred (design Open Risk).
- Rewriting/restructuring the test; changing scaffolding (`modernpackage/main.py`,
  `init`/`check` recipes); changing the `e2e` marker or `-m 'not e2e'` default.
- A second e2e variant exercising the GitHub-clone production path.

## Assumptions Recorded

- The task author may not have known the test already existed (this is the `-v2`
  workspace); the artifact is treated as the deliverable per design Decision 2.
- A `1 skipped` result caused by a failed environment pre-check (missing tool,
  Python ≠ 3.14, offline) is an acceptable terminal outcome for Phase 3 — the
  guarantee is "the test is present and correct," demonstrable to green only on a
  conforming host.
- The inner `just init` produces `scaffoldcheck/scaffoldcheck/__init__.py` (the
  package source dir is renamed and nested under the clone destination), matching
  the test's `destination / package_name / '__init__.py'` assertion.
