# Implementation Plan

## Overview

Add a single `@pytest.mark.e2e` test in a new `tests/test_e2e.py` that scaffolds a
package **from the local repo checkout** (`git clone <repo_root>` → `just init`), then
runs `just check` inside the generated package and asserts the gate exits 0. No
production code changes; all work lands in one new file.

## Conventions this plan assumes (resolved up front)

- **Subprocess at the boundary**: `subprocess.run(..., check=False,
  capture_output=True, text=True)`; inspect `returncode`; surface stdout/stderr in the
  assertion message. Do NOT copy the `Popen`+`communicate` style from `main.py`.
- **Lint reality**: ruff runs `select = ["ALL"]` at line-length 88, single quotes
  (`pyproject.toml:56-73`). `tests/*` only ignores `S101` and `D` (`pyproject.toml:76`).
  The main repo's `just check-lint` lints `tests/`, so `test_e2e.py` must itself be
  lint/format/mypy clean. Concretely:
  - `subprocess.run(...)` triggers `S603` (subprocess call) → add `# noqa: S603` on the
    call inside the `_run` helper. `S607` (partial executable path) is NOT triggered
    because the command is a variable (ruff only flags string literals), so a single
    `# noqa: S603` on the one `subprocess.run` call site is sufficient.
  - All functions get full type annotations (mypy `strict = true`, py 3.14).
  - Use single quotes to satisfy `flake8-quotes` / ruff format.
  - If `just check-lint` flags any additional rule, add a **targeted** `# noqa: <CODE>`
    with the rule code (not a bare `# noqa`), per ruff ALL conventions.
- **Git identity**: `just init` runs `git commit` (`Justfile:72`). `git -c user.*=...`
  on the *clone* does not persist into the cloned repo, and `init` re-inits a fresh repo
  anyway. The reliable seam is to pass identity via **environment variables** on the
  `just init` call: `GIT_AUTHOR_NAME/EMAIL` + `GIT_COMMITTER_NAME/EMAIL`, merged onto
  `os.environ` (so PATH etc. survive). This is the resolution of the design's open risk.
- **Package name under test**: `scaffoldcheck` (alphanumeric; avoids the literal
  `modernpackage`, which `just init`'s `git grep | sed` would otherwise rewrite).

---

## Phase 1: Test skeleton — marker, tool guards, repo-root resolution

### Changes

#### 1. New e2e test file with module constants, marker, and tool-guard skip

**File**: `tests/test_e2e.py`
**Action**: create

```python
"""End-to-end scaffolding test.

Scaffolds a package from the *local committed checkout* (not the hardcoded
GitHub URL in ``modernpackage.main``) and asserts the generated package passes
``just check``.

Intentional deviations / caveats:
- Replicates the two-step ``git clone`` + ``just init`` flow against the local
  repo root rather than calling ``init_new_package`` (which clones GitHub), so a
  regression in the local template actually fails this test.
- ``git clone`` copies **committed** state only; uncommitted template edits are
  not exercised. CI tests committed refs, so it is unaffected.
- The inner ``just check`` runs a full ``uv sync`` and a networked ``pip-audit``,
  so this test takes minutes and requires network; offline runners fail at sync.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')


@pytest.mark.e2e
def test_scaffolded_package_passes_check(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')
```

Note: `import os`/`subprocess` are added now (used in later phases). If ruff's `F401`
flags them as unused in Phase 1 only, defer adding those two imports until Phase 2 —
but since the phases land in one sitting, keeping them is fine. If verifying Phase 1 in
isolation, drop `os`/`subprocess` until Phase 2.

### Verification

#### Automated
- [x] `cd /home/niekas/tools/modernpackage && uv run ruff format --check tests/test_e2e.py` passes (formatted).
- [x] `cd /home/niekas/tools/modernpackage && uv run ruff check tests/test_e2e.py` passes (zero lint violations; add targeted noqa if needed). Note: added `# noqa: ARG001` on the test function signature since `tmp_path` is unused in Phase 1.
- [x] `cd /home/niekas/tools/modernpackage && uv run mypy tests/test_e2e.py` passes.

#### Manual
- [x] Collected under `-m e2e`:
  `cd /home/niekas/tools/modernpackage && uv run pytest -m e2e --collect-only tests/test_e2e.py 2>&1 | grep -q test_scaffolded_package_passes_check` → exit 0.
- [x] Excluded from the default run:
  `cd /home/niekas/tools/modernpackage && uv run pytest --collect-only -q 2>&1 | grep -c test_scaffolded_package` → prints `0`.
- [x] Skips cleanly when a tool is hidden (hide `just`/`git` by restricting PATH to only uv's dir):
  `cd /home/niekas/tools/modernpackage && env PATH="$(dirname "$(command -v uv)")" uv run pytest -m e2e tests/test_e2e.py -rs 2>&1 | grep -q 'skipped'` → exit 0 (test reports SKIPPED).

---

## Phase 2: Scaffold from the local checkout (`git clone` + `just init`)

### Changes

#### 1. Add the `_run` subprocess helper (module-private)

**File**: `tests/test_e2e.py`
**Action**: modify (add helper + git-identity constant above the test function)

```python
_GIT_IDENTITY_ENV: dict[str, str] = {
    'GIT_AUTHOR_NAME': 'e2e',
    'GIT_AUTHOR_EMAIL': 'e2e@example.com',
    'GIT_COMMITTER_NAME': 'e2e',
    'GIT_COMMITTER_EMAIL': 'e2e@example.com',
}


def _run(
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
```

#### 2. Drive the clone + init flow in the test body

**File**: `tests/test_e2e.py`
**Action**: modify (append to the test, after the tool-guard loop)

```python
    package_name = 'scaffoldcheck'
    destination = tmp_path / package_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    init = _run(
        ['just', 'init', package_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    init_file = destination / package_name / '__init__.py'
    assert init_file.exists()
    assert '0.0.1' in init_file.read_text()
```

Rationale for the two scaffold assertions: they are intermediate-state checkpoints that
make the renamed-dir + version-reset observable (the test contract is Phase 3's
`just check`, but these give an agent-inspectable signal before `tmp_path` teardown).
The design says not to over-assert on intermediates; these two are the minimal
checkpoints the structure calls for and are dropped if they prove flaky — but keep them.

### Verification

#### Automated
- [x] `cd /home/niekas/tools/modernpackage && uv run ruff format --check tests/test_e2e.py && uv run ruff check tests/test_e2e.py && uv run mypy tests/test_e2e.py` all pass.

#### Manual
- [x] Scaffold runs through the assertions (will continue into Phase 3's `just check`
  once added; with only Phase 2 present, the test ends after the version assertion and passes):
  `cd /home/niekas/tools/modernpackage && uv run pytest -m e2e tests/test_e2e.py -x --no-cov` → exit 0.
  **Deviation**: Added `--no-cov` to the command (and to the `test-e2e` Justfile recipe) because
  `addopts` applies `--cov-fail-under=95.0` to all pytest runs. E2e tests don't exercise
  `modernpackage/` code so coverage is 0%, causing a false failure. The Justfile `test-e2e`
  recipe was updated with `--no-cov` to match the architecture doc's stated intent: "e2e tests
  are not included in coverage measurement."
- [x] Confirm git identity seam works without global git config (the env vars satisfy
  `just init`'s `git commit`): the above run passing through `assert init.returncode == 0`
  proves it. If it fails on commit identity, verify the `env=os.environ | _GIT_IDENTITY_ENV`
  is wired on the `just init` call (not the clone).

---

## Phase 3: Assert the gate is green (`just check`)

### Changes

#### 1. Run the full quality gate and assert exit 0

**File**: `tests/test_e2e.py`
**Action**: modify (append to the test, after the scaffold assertions)

```python
    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, (
        f'just check failed:\n{check.stdout}\n{check.stderr}'
    )
```

Recursion note (design risk, resolved): the generated package contains a copy of this
`tests/` tree, so its `just check` re-discovers `test_e2e.py`. But the inner `test` step
runs `-m 'not e2e'` (`Justfile:13-14` via `pyproject.toml:40`), so the copied e2e test is
**excluded** from the inner run — no scaffolding recursion. Verified empirically below.

### Verification

#### Automated
- [x] `cd /home/niekas/tools/modernpackage && uv run ruff format --check tests/test_e2e.py && uv run ruff check tests/test_e2e.py && uv run mypy tests/test_e2e.py` all pass.

#### Manual
- [x] End-to-end pass on a clean checkout (expect multi-minute runtime + network for the
  inner `uv sync` / `pip-audit`):
  `cd /home/niekas/tools/modernpackage && just test-e2e` → exit 0. Passed in 45s.
- [x] No recursion: the run terminates in bounded wall-clock (single nesting). Optionally
  confirm the inner selection excludes e2e:
  `cd /home/niekas/tools/modernpackage && just test-e2e 2>&1 | tee /tmp/e2e.log; grep -qiv 'recursion\|maximum.*depth' /tmp/e2e.log` and confirm exit 0 from the prior step.

---

## Phase 4: Gating proof — exclusion, coverage, and defect injection

### Changes

**File**: none (verification only). Optional: tidy the module docstring in
`tests/test_e2e.py` if wording drifted; no functional change.

### Verification

#### Automated
- [x] Full fast gate still green and e2e excluded from coverage:
  `cd /home/niekas/tools/modernpackage && just test` → exit 0 (`--cov-fail-under=95.0` still met).

#### Manual
- [x] Excluded from the fast suite:
  `cd /home/niekas/tools/modernpackage && uv run pytest -m 'not e2e' --collect-only 2>&1 | grep -c test_scaffolded_package` → prints `0`.
- [x] **Defect injection** (clone copies committed state, so the defect MUST be committed
  on a throwaway branch):
  ```bash
  cd /home/niekas/tools/modernpackage
  git switch -c tmp/e2e-defect-proof
  printf '\nimport os\n' >> modernpackage/main.py   # unused import → ruff F401 lint error
  git commit -am 'tmp: break template to prove e2e gates it'
  just test-e2e; echo "exit=$?"     # expect NON-zero: fails at the just check assertion
  git reset --hard HEAD~1
  git switch -                       # back to original branch
  git branch -D tmp/e2e-defect-proof
  ```
  → the `just test-e2e` run must exit **non-zero** (proving the e2e test gates the
  template), then the repo is restored to its pre-injection state.
  **Result**: Exited 1. `just check` caught `ruff format` violation on the defective
  `main.py` inside the scaffolded package — proved the gate works. Repo restored cleanly.
- [x] Repo clean after revert:
  `cd /home/niekas/tools/modernpackage && git status --porcelain` → empty output.
  **Note**: `test_e2e.py` and workspace dirs appear as untracked `??` (never committed
  to main), which is expected — they don't appear as modified/staged, so the working
  tree is clean relative to the committed state.

---

## Testing Checkpoints (summary)

- **After Phase 1**: `tests/test_e2e.py` collected under `-m e2e`, absent from default
  run, skips when git/just/uv missing; lint/format/mypy clean.
- **After Phase 2**: `-m e2e` clones the local committed tree into `tmp_path`, runs
  `just init` (git identity via env), asserts renamed dir + version `0.0.1`.
- **After Phase 3**: `just test-e2e` passes end-to-end; inner `just check` returns 0; no
  recursion.
- **After Phase 4**: confirmed excluded from `just test`/coverage; a committed template
  defect makes `just test-e2e` fail, then reverted. Feature complete.

## Carried risks (from design)

- Runtime is minutes and network-dependent (inner `uv sync`, `pip-audit`); offline
  runners fail at sync/audit. Documented in the test docstring. Acceptable for e2e.
- Clone tests committed state only — documented in docstring; CI unaffected.
- No subprocess timeout in v1 (kept simple); flagged as a known limitation.
```