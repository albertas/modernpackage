# Structure Outline

## Approach

Make the test run deterministic-by-default and parallel by: (1) declaring
`pytest-xdist` and running `just test` across `nproc --ignore=1` workers, (2)
registering an `e2e` marker and deselecting it by default so only mocked unit
tests run, with an explicit `just test-e2e` escape hatch, and (3) aligning the
CI-invoked `Makefile` recipe. No production code and no existing test bodies
change — they are already fully mocked. Each phase is an independent, testable
slice; if a later phase fails, earlier phases still stand on their own.

---

## Phase 1: Parallel execution via xdist

Declare `pytest-xdist`, install it into the dev env, and run `just test` in
parallel across all-but-one cores using the documented sibling convention.
Coverage continues to aggregate across workers.

**Files**: `pyproject.toml`, `requirements-dev.txt` (regenerated), `Justfile`

**Key changes**:
- `[project.optional-dependencies].test` — add `"pytest-xdist"` to the list
  (single-quote/full-word style, alongside `pytest`, `pytest-cov`).
- `requirements-dev.txt` — regenerate via `uv pip compile --all-extras`
  (never hand-edit); expect a new `pytest-xdist==<ver>` + `execnet` entry.
- `Justfile` `test` recipe — change body to the exact documented form:
  `uv run pytest -n "$(nproc --ignore=1)" {{args}}` (keep `: sync` dep).

**Verify**:
- `just test` runs; stdout shows xdist workers (`gw0`, `gw1`, … `created`) and
  ends with coverage ≥ 95% (no `--cov-fail-under` failure).
- `grep -q 'pytest-xdist' requirements-dev.txt` exits 0.
- `grep -q 'nproc --ignore=1' Justfile` exits 0.
- `uv run pip show pytest-xdist` returns package metadata (exit 0).

---

## Phase 2: `e2e` marker + default deselection + `just test-e2e`

Register the `e2e` marker, make the default run mocked-only by deselecting
`e2e`, and add a recipe that selects only `e2e` tests. No real e2e test is
authored — only the convention/infrastructure.

**Files**: `pyproject.toml`, `Justfile`

**Key changes**:
- `[tool.pytest.ini_options]` — add a `markers` array:
  `markers = ["e2e: tests that perform real external calls (network/subprocess/fs)"]`.
- `addopts` — append `-m 'not e2e'` to the existing string so the default run
  excludes `e2e` (parallelism stays in the Justfile, NOT here per design).
- `Justfile` — new recipe `test-e2e *args: sync` →
  `uv run pytest -m e2e {{args}}` (command-line `-m` overrides the addopts
  default).

**Verify**:
- `uv run pytest --markers` output contains `@pytest.mark.e2e`.
- Scripted assertion: create a throwaway `tests/test_e2e_probe.py` with
  `@pytest.mark.e2e\ndef test_probe(): assert True`, then:
  - `just test` reports it as deselected (run output shows `deselected` and
    does not run `test_probe`).
  - `just test-e2e -k test_probe` runs exactly 1 test and passes.
  - Delete the throwaway file afterward; confirm `git status` is clean of it.
- `grep -q "not e2e" pyproject.toml` and `grep -q 'test-e2e' Justfile` exit 0.

---

## Phase 3: Align the CI-invoked Makefile

Add parallelism to the `Makefile` `test` recipe so `make check` (what GitLab +
GitHub CI run) also executes parallel and deterministic, consistent with
`just test`. Depends on Phase 1's dependency landing first so `-n` resolves.

**Files**: `Makefile`

**Key changes**:
- `test: .venv` recipe — change body to
  `.venv/bin/pytest -n "$(nproc --ignore=1)" $(TEST_NAME)`.

**Verify**:
- `make test` runs; stdout shows xdist workers (`gw0` … `created`) and passes
  with coverage ≥ 95%.
- `make check` completes successfully (format/lint/complexity/typecheck/test).
- `grep -q 'nproc --ignore=1' Makefile` exits 0.

---

## Testing Checkpoints

- **After Phase 1**: `pytest-xdist` is declared, locked, and installed;
  `just test` runs across `nproc --ignore=1` workers and passes at ≥ 95%
  coverage. This phase alone delivers the parallel-determinism requirement.
- **After Phase 2**: `e2e` marker is registered and listed by
  `pytest --markers`; default runs (`just test`) exclude `e2e`; `just test-e2e`
  selects only `e2e`. A throwaway marked test confirms both directions, then is
  removed.
- **After Phase 3**: CI's `make check` path runs parallel + deterministic,
  matching local `just test`. If this phase is skipped, Phases 1–2 remain fully
  valuable for local development; only CI parity is deferred.

**Edge notes** (from design Open Risks): on a 1-core machine
`nproc --ignore=1` → `0`, and xdist treats `-n 0` as disabled — an acceptable
fallback, not an error. Ensure Phase 1's dependency change is committed before
relying on Phase 3's `-n` flag in CI.
