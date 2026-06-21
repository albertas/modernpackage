# Design Discussion

## Current State

`just test-e2e` currently fails for two independent reasons (confirmed in this
environment — `podman 5.7.0` + `podman-compose 1.5.0`, no `docker`).

### Root cause 1 — `up --wait` is rejected by podman compose (runtime tests)
The three compose runtime tests invoke `[*compose, 'up', '-d', '--wait',
'--build']`:
- `tests/test_e2e.py:476` (`test_fullstack_package_runs_end_to_end`)
- `tests_e2e/test_backend_e2e.py:51` (`test_backend_package_runs_end_to_end`)
- `tests_e2e/test_fullstack_feature_e2e.py:54` (`test_fullstack_feature_runs_end_to_end`)

`_detect_compose_command` (`tests/test_e2e.py:67-88`) probes the portability set
`docker compose → podman compose → podman-compose` (`tests/test_e2e.py:60-64`)
with `<cmd> version` and returns the first that exits 0. Here that resolves to
`['podman', 'compose']`. But `--wait` is **docker-compose-only**; `podman compose
up --wait` errors `unrecognized arguments: --wait` / exit 2 (research Q3). The
detection layer treats podman as available while the up-flag layer assumes
docker semantics, so `assert up.returncode == 0` (`tests/test_e2e.py:477`) fails
before any HTTP check. Verified empirically.

### Root cause 2 — `tests_e2e/` leaks into scaffolded packages (`passes_check` tests)
`_strip_scaffolding` deletes the paths in `_SCAFFOLDING_PATHS_TO_DELETE`
(`modernpackage/main.py:519-526`): `modernpackage/main.py`, `tests/test_e2e.py`,
`docs`, `BACKLOG.md`, `backend_template`, `frontend_template`. The newer
`tests_e2e/` directory (added in commits T61/T62) was **never added to this
list**. So a scaffolded package still ships `tests_e2e/test_backend_e2e.py`,
`tests_e2e/test_fullstack_feature_e2e.py`, and `tests_e2e/_scaffold.py`. Those
modules do `from <module> import main` (e.g. `_scaffold.py:15`), but `main.py`
was just stripped — pytest collection raises `ImportError: cannot import name
'main'`, the inner `just test` exits 1, and `just check` fails. This breaks all
three `*_passes_check` tests (`tests/test_e2e.py:123,190,326`). Reproduced
empirically: a manually scaffolded no-extras package fails inner pytest with
exactly this ImportError on both `tests_e2e/` modules.

## Desired End State

`just test-e2e` passes (or cleanly skips on capability gaps — missing tools,
unavailable Playwright browsers) on a podman-only host:
- The three runtime tests bring the stack up, observe `/livez` and `/readyz`
  return 200 from the host, and exercise migrations — without relying on a
  docker-only flag.
- The three `*_passes_check` tests produce a scaffold whose `just check` passes;
  scaffolded packages contain **no** `tests_e2e/` directory.

**Verification:** `just test-e2e` green locally. Spot-check: a manual scaffold
(`_strip_scaffolding`) has no `tests_e2e/`, and its `just test` collects only the
stub/template tests. `test_scaffolded_package_has_no_backend_or_frontend` gains
a `tests_e2e` absence assertion to lock the regression.

## Patterns to Follow

- **Wholesale path removal**: add `'tests_e2e'` to the `_SCAFFOLDING_PATHS_TO_DELETE`
  tuple (`modernpackage/main.py:519-526`); the loop already tolerates absent
  entries (clone-shape-agnostic, per the comment at `main.py:514-518`). No new
  deletion logic.
- **Stdlib HTTP, no httpx**: readiness polling must reuse `_http_get`
  (`tests/test_e2e.py:91-104`) — stdlib `urllib`, mirroring the Containerfile
  healthcheck — not the backend-only `httpx` dep (design decision 5 in the file).
- **Graceful subprocess boundary**: `_run` uses `check=False, capture_output,
  text` (`tests/test_e2e.py:45-57`); keep asserting on `returncode` + captured
  output in failure messages.
- **Capability skips, not failures**: missing tool / `_detect_compose_command()
  is None` / Playwright install failure already `pytest.skip` (`test_e2e.py:539-545`).
  Readiness handling should fail loudly only on a real readiness timeout.
- **Absence-assertion pattern**: the no-extras test already asserts forbidden
  dirs/files are gone (`test_e2e.py:282-292`); extend it for `tests_e2e`.
- **Pattern to NOT follow blindly**: the helper duplication between
  `tests/test_e2e.py` and `tests_e2e/_scaffold.py` (`_detect_compose_command`,
  `_http_get`, `_run`, candidates) is intentional mirroring (`_scaffold.py:1-6`),
  but it means the readiness fix must land in **both** files. Do not consolidate
  into a shared module in this task (scope); just mirror, matching precedent.

## Design Decisions

1. **Replace `--wait` with explicit readiness polling (not docker-only branching)**:
   change the three call sites to `[*compose, 'up', '-d', '--build']` and add a
   `_wait_for_ready(url, timeout)` helper that GETs `/readyz` in a bounded retry
   loop until it returns 200. Chosen over "append `--wait` only when backend is
   docker" because polling is backend-agnostic, removes the docker-semantics
   assumption entirely, and works identically on docker and podman. The poll
   replaces the readiness guarantee the docstrings attributed to `--wait`
   (`test_e2e.py:427-431,479-480`).
2. **Poll `/readyz`, which proves the full chain**: `/readyz` returns 200 only
   when `SELECT 1` succeeds (`health.py:37-46`) and `app` only starts after `db`
   healthy + `migrate` completed (`compose.yml` depends_on, research Q4). A
   green `/readyz` therefore signals DB + app reachability without `--wait`.
3. **Catch connection-level errors in the poll loop**: `_http_get` re-raises
   non-HTTP failures (no `URLError` catch, `test_e2e.py:100-104`), so
   `_wait_for_ready` must wrap calls in `try/except (URLError, OSError)`, sleep,
   and retry until a deadline — early in startup the port refuses connections.
4. **Generous timeout (~120s) via `time.monotonic()` deadline**: the stack
   builds images and runs migrations on first `up`; cores vary. Use a monotonic
   deadline with a short sleep between polls. On timeout, fail with the last
   status/body for diagnosability.
5. **Mirror the helper in both files**: add `_wait_for_ready` to
   `tests/test_e2e.py` and `tests_e2e/_scaffold.py`, matching the existing
   intentional duplication (`_scaffold.py:1-6`), and import it in the two
   `tests_e2e/` runtime tests as they already import `_http_get`/`_run`.
6. **Add a `tests_e2e` absence assertion** to
   `test_scaffolded_package_has_no_backend_or_frontend` (`test_e2e.py:282-288`)
   to prevent silent re-introduction of the leak.
7. **Keep `down -v` unchanged**: supported by podman compose (research Q3); the
   `finally` teardown needs no edit.

## What We're NOT Doing

- Not consolidating the duplicated test helpers into a shared module (research
  Q2) — out of scope; mirror instead.
- Not installing or requiring docker; not changing `_detect_compose_command`
  ordering or the portability set.
- Not modifying `compose.yml` healthchecks/`depends_on`, the Containerfile
  healthcheck, or `/livez`/`/readyz` handlers.
- Not touching coverage config (`--cov-fail-under=95.0`), xdist worker counts,
  or the inner `just check` chain.
- Not changing migration recipes or the host DB-port exposure logic
  (`_expose_db_port`, `_scaffold.py:84-103`).

## Open Risks

- **podman-compose `depends_on` runtime semantics unverified**: the runtime
  tests have never passed on podman (they died at `--wait`), so whether
  podman-compose 1.5.0 honors `condition: service_completed_successfully` /
  `service_healthy` at `up` time is untested. If it does not order startup,
  polling `/readyz` still tolerates it (the loop waits for the app), but the
  migrate-before-app guarantee may not hold. Verify during implementation by
  running one runtime test end to end on this host.
- **`--build` without `--wait` returns immediately**: confirm `up -d --build`
  exits 0 on podman even while containers are still starting; the poll absorbs
  the latency, but a non-zero `up` (e.g. build failure) must still fail fast.
- **First-run image build time** may exceed the poll timeout on a cold cache;
  the timeout must cover build + migration + app start.
- **Network dependence persists** for the `passes_check` tests (`uv sync`,
  `pip-audit`, `npm ci`); these are pre-existing environmental needs, not part
  of this fix.

Next: run `/lifecycle:4_structure workspace/T63-2026-06-21-end-to-end-tests-seem-to-be-failing-fix-them/`
