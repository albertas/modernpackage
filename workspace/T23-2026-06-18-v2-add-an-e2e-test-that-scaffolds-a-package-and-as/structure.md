# Structure Outline

## Approach

Add one `@pytest.mark.e2e` test in a new `tests/test_e2e.py` that replicates the
two-step scaffolding flow (`git clone` → `just init`) **against the local repo
checkout** (not the hardcoded GitHub URL), then runs `just check` inside the
generated package and asserts the gate is green. No production code changes. The
test uses `subprocess.run(..., check=False, capture_output=True, text=True)` at
the boundary and the built-in `tmp_path` fixture for isolation.

Because this is a single test, the slices are incremental cuts of the *same*
test function — each leaves a runnable test whose assertions reach one step
further down the real scaffold/gate pipeline, so each phase is independently
verifiable via `just test-e2e`.

All work lands in one new file: `tests/test_e2e.py`. (Production `main.py`,
`Justfile`, and `pyproject.toml` are untouched.)

---

## Phase 1: Test skeleton — marker, tool guards, repo-root resolution

Establish the e2e test as a collectable, properly-excluded unit. The test exists,
is marked, skips cleanly when toolchain is absent, and resolves the repo root
relative to the test file (not `Path.cwd()`).

**Files**: `tests/test_e2e.py` (new)

**Key changes**:
- `REPO_ROOT: Path = Path(__file__).resolve().parent.parent` — module constant.
- `REQUIRED_TOOLS: tuple[str, ...] = ("git", "just", "uv")` — module constant.
- `def test_scaffolded_package_passes_check(tmp_path: Path) -> None` — the e2e
  test, decorated `@pytest.mark.e2e`. Body so far: guard loop
  `for tool in REQUIRED_TOOLS: if shutil.which(tool) is None: pytest.skip(...)`.
  Module docstring documents the intentional deviations (local clone vs GitHub,
  committed-state-only, network/runtime cost).

**Verify**:
- `cd <repo>` then `uv run pytest -m e2e --collect-only tests/test_e2e.py`
  lists `test_scaffolded_package_passes_check` (exit 0).
- `uv run pytest --collect-only -q 2>&1 | grep -c test_scaffolded_package` prints
  `0` — confirms the default `-m 'not e2e'` selector excludes it.
- Skip path: `env PATH="$(dirname "$(command -v uv)")" uv run pytest -m e2e
  tests/test_e2e.py -rs` reports the test as **skipped** (git/just hidden).

---

## Phase 2: Scaffold from the local checkout (`git clone` + `just init`)

Drive the real two-step flow into `tmp_path`: clone the committed local tree, run
`just init <name>`, and handle the `git commit` identity requirement so `init`
succeeds on a machine with no global git config.

**Files**: `tests/test_e2e.py`

**Key changes**:
- `def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]` —
  helper wrapping `subprocess.run(command, cwd=cwd, check=False,
  capture_output=True, text=True)`.
- In the test: `package_name = "scaffoldcheck"`; `destination = tmp_path /
  package_name`.
- Clone with throwaway identity injected so `init`'s `git commit` works:
  `_run(["git", "-c", "user.email=e2e@example.com", "-c", "user.name=e2e",
  "clone", str(REPO_ROOT), str(destination)], cwd=tmp_path)`. If `git init`/commit
  inside the recipe still picks up missing identity, set `GIT_AUTHOR_*`/
  `GIT_COMMITTER_*` via `env=` on the `just init` call (investigate per design
  risk).
- `_run(["just", "init", package_name], cwd=destination)`; assert `returncode == 0`
  with `result.stderr` in the message.
- Scaffold assertions (intermediate-state checkpoints):
  `assert (destination / package_name / "__init__.py").exists()` and
  `assert "0.0.1" in (destination / package_name / "__init__.py").read_text()`.

**Verify**:
- `uv run pytest -m e2e tests/test_e2e.py -x` passes through the scaffold
  assertions (the renamed package dir + reset version confirm clone+init ran).
- The two `assert ... __init__.py` lines make the renamed-dir / version-reset
  state agent-inspectable without reaching into `tmp_path` after teardown.

---

## Phase 3: Assert the gate is green (`just check`)

Run the full quality gate inside the generated package and assert it exits 0,
embedding stdout/stderr for debuggability. This is the test's contract.

**Files**: `tests/test_e2e.py`

**Key changes**:
- `result = _run(["just", "check"], cwd=destination)` (reuse Phase 2 `_run`).
- `assert result.returncode == 0, f"just check failed:\n{result.stdout}\n{result.stderr}"`.
- Confirm no scaffolding recursion: the inner `just check` → `test` runs
  `-m 'not e2e'`, so the copied `test_e2e.py` is excluded (design risk —
  verify empirically here).

**Verify**:
- `just test-e2e` (i.e. `uv run pytest -m e2e`) passes end-to-end on a clean
  checkout (exit 0). Expect multi-minute runtime + network (inner `uv sync` /
  `pip-audit`).
- Recursion check: inspect the inner run's selection by adding `-s` and
  confirming the failure message (if any) does not reference a nested e2e
  invocation; or assert wall-clock terminates (single nesting only).

---

## Phase 4: Gating proof — exclusion, coverage, and defect injection

Prove the test does what it claims: excluded from the fast suite, doesn't touch
the coverage gate, and actually fails when the template regresses. Mostly
verification; no new test code (optional: tidy the docstring).

**Files**: none (verification only); optional doc tweak to `tests/test_e2e.py`.

**Verify**:
- Exclusion: `uv run pytest -m 'not e2e' --collect-only 2>&1 | grep -c
  test_scaffolded_package` prints `0`.
- Coverage unaffected: `just test` passes with `--cov-fail-under=95.0` still
  green (e2e excluded from coverage via `-m 'not e2e'`).
- **Defect injection** (must be committed — clone copies committed state only):
  on a throwaway branch, introduce a lint error in `modernpackage/main.py`
  (e.g. `import os` unused), `git commit -am "tmp: break template"`, run
  `just test-e2e` and confirm it **fails** at the `just check` assertion, then
  `git reset --hard HEAD~1` to revert. This proves the e2e test gates the
  template rather than passing vacuously.

---

## Testing Checkpoints

- **After Phase 1**: `tests/test_e2e.py` exists; `test_scaffolded_package_passes_check`
  is collected under `-m e2e`, absent from the default run, and skips when
  git/just/uv are missing.
- **After Phase 2**: Running `-m e2e` clones the local committed tree into
  `tmp_path` and runs `just init` successfully (git identity handled); renamed
  package dir and version `0.0.1` are asserted.
- **After Phase 3**: `just test-e2e` passes end-to-end — `just check` returns 0
  inside the generated package, with no scaffolding recursion.
- **After Phase 4**: Confirmed excluded from `just test` / coverage, and a
  deliberately-committed template defect makes `just test-e2e` fail (then
  reverted). Feature complete.

### Notes / risks carried from design
- Clone uses **committed** state — uncommitted template edits are not tested
  (documented in the test docstring; CI tests committed refs, so unaffected).
- `just init`'s `git commit` needs an identity — injected via `git -c` / env;
  verify the exact seam during Phase 2.
- Runtime is minutes and **network-dependent** (inner `uv sync`, `pip-audit`);
  offline runners fail at sync/audit — acceptable for an e2e test, noted in a
  comment.
