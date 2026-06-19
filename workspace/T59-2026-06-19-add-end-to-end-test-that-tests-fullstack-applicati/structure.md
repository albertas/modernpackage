# Structure Outline

## Approach

Add one new `@pytest.mark.e2e` test, `test_fullstack_package_runs_end_to_end`,
to `tests/test_e2e.py`. It scaffolds a fullstack package through the existing
production injection path, brings the stack up via the shipped `compose.yml`
(`db` + `migrate` + `app`), then proves real runtime behavior: host-side HTTP
against `/livez` + `/readyz`, `generate-client` against the live backend, and
`frontend-build` against the regenerated client. Two small module-private helpers
(compose-command detection, HTTP GET) are added first so each later slice is
runnable on its own. Teardown (`compose down -v`) always runs in `try/finally`.

Each phase appends to the single test (or its helpers) and is exercised by
`just test-e2e`. Slices are ordered so an early failure still leaves the prior
slices independently green.

---

## Phase 1: Compose-command detection + HTTP helper (foundations)

Add two module-private helpers to `tests/test_e2e.py`. No test body yet — these
are the seams the runtime slices depend on. Both degrade gracefully at the
process/network boundary (design "Patterns to Follow"; CLAUDE.md error-handling).

**Files**: `tests/test_e2e.py`

**Key changes**:
- `_detect_compose_command() -> list[str] | None` — probes, in order,
  `['docker', 'compose']`, `['podman', 'compose']`, `['podman-compose']` by
  running `<cmd> version` with `check=False`; returns the first whose
  `returncode == 0`, else `None` (design decision 4).
- `_http_get(url: str, timeout: float = 30.0) -> tuple[int, str]` — stdlib
  `urllib.request` GET (design decision 5); returns `(status_code, body)`.
  Raises only on connection failure; HTTP error statuses are returned, not
  raised, so callers can assert on them.
- `_REQUIRED_RUNTIME_TOOLS: tuple[str, ...] = (*REQUIRED_TOOLS, 'npm')` — module
  constant reused by Phase 2's skip guard.

**Verify**: `uv run pytest tests/test_e2e.py -m e2e --no-cov -k runs_end_to_end`
collects without error (still 0 runtime tests). Add a throwaway assertion or a
Python one-liner — `uv run python -c "from tests.test_e2e import
_detect_compose_command as d; print(d())"` — prints a list (e.g.
`['docker', 'compose']`) on a machine with compose, or `None` otherwise, without
raising. `just check` still passes (helpers are lint/type clean).

---

## Phase 2: Bring the stack up + backend HTTP assertions

Add `test_fullstack_package_runs_end_to_end`: scaffold via the verbatim
sequence, `compose up -d --wait --build`, then assert `/livez` and `/readyz` over
real HTTP. Wrap the compose lifecycle in `try/finally` with `compose down -v` so
this slice never leaks containers, the `pgdata` volume, or port 8000
(design decision 7).

**Files**: `tests/test_e2e.py`

**Key changes**:
- `test_fullstack_package_runs_end_to_end(tmp_path: Path) -> None` — new
  `@pytest.mark.e2e` test.
- Skip guard: loop `_REQUIRED_RUNTIME_TOOLS` → `pytest.skip`; then
  `compose = _detect_compose_command()`; `if compose is None: pytest.skip(...)`.
- Scaffold sequence reused verbatim from
  `test_scaffolded_fullstack_package_passes_check` (`test_e2e.py:295-316`):
  `git clone` → `_write_package_metadata` → `_strip_scaffolding` →
  `_inject_templates(fullstack=True)` → `just init` with
  `os.environ | _GIT_IDENTITY_ENV`.
- Compose run against the backend dir (`destination / module_name` — where
  `compose.yml` lands): `_run([*compose, 'up', '-d', '--wait', '--build'], cwd=backend_dir)`
  inside `try`; assert `returncode == 0`.
- HTTP assertions: `_http_get('http://127.0.0.1:8000/livez')` → `(200, body)`
  with `'pass'` in body; `_http_get('http://127.0.0.1:8000/readyz')` → status
  `200` (real `SELECT 1`, design pillar 1).
- `finally: _run([*compose, 'down', '-v'], cwd=backend_dir)`.

**Verify**: `just test-e2e` runs the test green on a compose+Node host; on a host
without compose it reports `skipped`, not `failed`. After the run,
`docker compose ls` (or `podman ps -a`) shows no leftover project containers and
`docker volume ls` shows no `pgdata` volume. Manually:
`uv run pytest -m e2e --no-cov -k runs_end_to_end -v` exits 0 (or skipped).

---

## Phase 3: Regenerate the API client against the live backend

With the stack up (Phase 2), run `just frontend-install` then
`just generate-client` so `@hey-api/openapi-ts` fetches the live
`http://localhost:8000/openapi.json` and rewrites `frontend/src/client/`. Assert
the regenerated client references the real operations — i.e. it is no longer the
hand-written placeholder (design pillar 2).

**Files**: `tests/test_e2e.py`

**Key changes** (added inside the Phase 2 `try`, after HTTP assertions, while the
backend is still up):
- `_run(['just', 'frontend-install'], cwd=destination)` first — `generate-client`
  does not depend on it (research Q4; `test_e2e.py:321-323`). Assert
  `returncode == 0`.
- `_run(['just', 'generate-client'], cwd=destination)`; assert `returncode == 0`.
- Read `destination / 'frontend' / 'src' / 'client'` output and assert stable
  substrings `'livez'` and `'readyz'` appear (assert on substrings, not exact
  generated structure — Open Risks; design decision 4 of "Open Risks"). Confirm
  the placeholder marker (e.g. the hand-written `Record<string, unknown>` /
  regenerate comment from `src/client/index.ts:1-4`) is gone.

**Verify**: `just test-e2e -k runs_end_to_end` passes. Manually, after a run with
teardown disabled for inspection, `grep -rl livez <pkg>/frontend/src/client`
returns at least one file and that file is not the 4-line placeholder. The test
fails loudly if `generate-client` could not reach the backend (proves the
backend-up ordering matters — design "Patterns to NOT follow", item 3).

---

## Phase 4: Build the frontend against the regenerated client

Run `just frontend-build` (`tsc --noEmit && vite build`) and assert it succeeds
and emits `frontend/dist/` — proving the regenerated client type-checks and
bundles (design pillar 3). This is the last runtime slice; the backend can be
torn down before or after the build (build reads no live URL).

**Files**: `tests/test_e2e.py`

**Key changes** (after Phase 3, still before `finally` or moved after teardown
since build needs no live backend):
- `_run(['just', 'frontend-build'], cwd=destination)`; assert `returncode == 0`
  with an f-string carrying `stdout`/`stderr`.
- Assert `(destination / 'frontend' / 'dist').is_dir()` and that it is non-empty
  (e.g. `index.html` exists).

**Verify**: `just test-e2e -k runs_end_to_end` passes end-to-end. Manually:
`test -f <pkg>/frontend/dist/index.html` succeeds after a non-teardown run; the
build step output contains `vite` build summary lines (e.g. `dist/`). Full suite
`just test-e2e` is green and `just check` (no e2e) remains green.

---

## Testing Checkpoints

State that should hold after each phase, for resuming after a context reset:

- **After Phase 1**: `_detect_compose_command()` and `_http_get()` exist, are
  lint/type-clean (`just check` green), and importable/callable without raising.
  No new runtime test yet.
- **After Phase 2**: `test_fullstack_package_runs_end_to_end` exists and is green
  on a compose+Node host; skips cleanly elsewhere. `compose up --wait` proves
  db+migrate+app readiness; `/livez` returns 200 `pass`, `/readyz` returns 200.
  Teardown leaves no containers/volumes/port-8000 binding.
- **After Phase 3**: `generate-client` runs against the live backend; the
  regenerated `frontend/src/client/` references `livez`/`readyz` and is no longer
  the placeholder.
- **After Phase 4**: `frontend-build` succeeds against the regenerated client and
  emits a non-empty `frontend/dist/`. `just test-e2e` fully green; `just check`
  unaffected.

## Notes / Risks carried from design

- **Single-test caveat**: this is one test built up across phases, not four
  independent features. The vertical seam per phase is "scaffold → run a real
  service layer → assert real behavior"; each phase exercises one of the three
  design pillars and is independently runnable via `-k runs_end_to_end`.
- **Port 8000 contention** (compose binds a fixed host port): if `just test-e2e`
  is flaky under parallelism, flag for planning a project-scoped compose project
  name or port override (design Open Risks). Not addressed here.
- **Runtime cost**: pulls `postgres:17`, builds the app image, runs `npm ci` +
  `vite build` — minutes-long and network-dependent; mitigated by skip guards and
  documented in the test docstring (matching `test_e2e.py:1-15`).
