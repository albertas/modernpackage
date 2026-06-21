# Structure Outline

## Approach

Two independent root causes, fixed as separate vertical slices. (A) Scaffolded
packages leak `tests_e2e/` because it's absent from `_SCAFFOLDING_PATHS_TO_DELETE`
— add it and lock with an absence assertion. (B) Runtime tests pass the
docker-only `up --wait` flag, which podman rejects — replace with a backend-agnostic
`_wait_for_ready(url, timeout)` poll of `/readyz`, mirrored into both test files.
Each phase targets a distinct subset of the seven failing/affected e2e tests and
is independently verifiable.

---

## Phase 1: Stop `tests_e2e/` leaking into scaffolds

Add `tests_e2e` to the scaffolding deletion tuple so stripped/scaffolded packages
ship no `tests_e2e/`, and lock the regression with an absence assertion. Fixes the
three `*_passes_check` tests (their inner `just test` currently dies on
`ImportError: cannot import name 'main'` from leaked `tests_e2e/` modules).

**Files**: `modernpackage/main.py`, `tests/test_e2e.py`

**Key changes**:
- `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:519-526`) — append `'tests_e2e'`
  to the tuple. Loop already tolerates absent entries (no new logic).
- `test_scaffolded_package_has_no_backend_or_frontend` (`test_e2e.py:282-292`) —
  extend the existing forbidden-paths absence block to assert
  `not (package_dir / 'tests_e2e').exists()`.

**Verify**:
- Unit-level: `uv run pytest tests/test_e2e.py::test_scaffolded_package_has_no_backend_or_frontend -m e2e --no-cov` passes.
- Manual (agent-executable): scaffold a no-extras package to a tmp dir via
  `_strip_scaffolding`, then assert `test -d <pkg>/tests_e2e` returns non-zero
  (directory absent) and `uv run pytest --collect-only -q` inside the scaffold
  lists only stub/template tests with no `tests_e2e` import error in output.
- End-to-end (network-permitting): `just test-e2e -k passes_check` — all three
  `*_passes_check` tests green.

---

## Phase 2: Backend-agnostic readiness poll in `tests/test_e2e.py`

Replace `--wait` with a `_wait_for_ready` helper and use it in the one runtime
test defined in `tests/test_e2e.py`. Establishes the polling helper that Phase 3
mirrors. Fixes `test_fullstack_package_runs_end_to_end`.

**Files**: `tests/test_e2e.py`

**Key changes**:
- New helper `_wait_for_ready(url: str, timeout: float = 120.0) -> None` — GET
  `url` (`/readyz`) in a `time.monotonic()` deadline loop; wrap `_http_get` in
  `try/except (URLError, OSError)`, sleep a short interval between polls, return
  on HTTP 200, raise (e.g. `AssertionError`/`RuntimeError`) with the last
  status/body on timeout. Reuses `_http_get` (`test_e2e.py:91-104`) — stdlib
  `urllib`, no `httpx`.
- `test_fullstack_package_runs_end_to_end` (`test_e2e.py:476`) — change up call to
  `[*compose, 'up', '-d', '--build']`; after asserting `up.returncode == 0`,
  call `_wait_for_ready('http://127.0.0.1:8000/readyz')` before the existing
  `/livez` + `/readyz` assertions. Update the docstring that attributed readiness
  to `--wait` (`test_e2e.py:427-431,479-480`).
- `down -v` teardown (`finally`) unchanged.

**Key signatures**:
- `_wait_for_ready(url: str, timeout: float = 120.0) -> None` — new

**Verify**:
- `uv run pytest tests/test_e2e.py::test_fullstack_package_runs_end_to_end -m e2e --no-cov`
  passes on this podman host (skips cleanly if `_detect_compose_command()` is
  None or Playwright install fails).
- Manual (agent-executable): grep `tests/test_e2e.py` for `--wait` returns no
  matches; grep confirms `_wait_for_ready` is called before the first
  `_http_get('.../readyz')` HTTP assertion.

---

## Phase 3: Mirror readiness poll into `tests_e2e/`

Mirror `_wait_for_ready` into `tests_e2e/_scaffold.py` (intentional duplication,
per `_scaffold.py:1-6`) and use it in the two `tests_e2e/` runtime tests. Fixes
`test_backend_package_runs_end_to_end` and `test_fullstack_feature_runs_end_to_end`.

**Files**: `tests_e2e/_scaffold.py`, `tests_e2e/test_backend_e2e.py`,
`tests_e2e/test_fullstack_feature_e2e.py`

**Key changes**:
- `_scaffold.py` — add `_wait_for_ready(url: str, timeout: float = 120.0) -> None`
  identical to Phase 2's (mirror, do not consolidate).
- `test_backend_e2e.py:51` and `test_fullstack_feature_e2e.py:54` — change up call
  to `[*compose, 'up', '-d', '--build']`; import `_wait_for_ready` from `_scaffold`
  (alongside existing `_http_get`/`_run` imports) and call it on
  `http://127.0.0.1:8000/readyz` after the `up.returncode == 0` assert, before HTTP
  checks / migration exercises. `down -v` teardown unchanged.

**Key signatures**:
- `_scaffold._wait_for_ready(url: str, timeout: float = 120.0) -> None` — new (mirror)

**Verify**:
- `uv run pytest tests_e2e/ -m e2e --no-cov` — both runtime tests pass (or skip on
  capability gaps).
- Manual (agent-executable): grep `tests_e2e/` for `--wait` returns no matches;
  the `_wait_for_ready` bodies in `tests/test_e2e.py` and `tests_e2e/_scaffold.py`
  are byte-identical (`diff <(sed -n '/_wait_for_ready/,/^def /p' ...)`).
- Full suite: `just test-e2e` green end-to-end on this host.

---

## Testing Checkpoints

- **After Phase 1**: `_SCAFFOLDING_PATHS_TO_DELETE` contains `'tests_e2e'`; a manual
  scaffold has no `tests_e2e/`; the three `*_passes_check` tests pass (network
  permitting); `has_no_backend_or_frontend` asserts `tests_e2e` absence.
- **After Phase 2**: no `--wait` in `tests/test_e2e.py`; `_wait_for_ready` exists and
  gates the one runtime test there; `test_fullstack_package_runs_end_to_end` green.
- **After Phase 3**: no `--wait` anywhere; `_wait_for_ready` mirrored in `_scaffold.py`
  and used by both `tests_e2e/` runtime tests; full `just test-e2e` green (capability
  skips allowed for missing tools / Playwright).

**Resumption note**: Phases are independent — if Phase 3 fails (e.g. unverified
podman-compose `depends_on` ordering, see design Open Risks), Phases 1–2 remain
valuable and green. Verify one runtime test end-to-end on this podman host during
Phase 2 to de-risk the `depends_on` / `--build`-without-`--wait` assumptions before
mirroring in Phase 3.
