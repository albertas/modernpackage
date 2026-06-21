# Research Questions

## Context
Focus on the end-to-end test suites in `tests/test_e2e.py` and the standalone
`tests_e2e/` directory (including `_scaffold.py`), the project's pytest/marker
configuration in `pyproject.toml`, the Justfile recipes that run tests, and the
scaffolding these tests exercise (`backend_template/`, `frontend_template/`, and
the generated `compose.yml`, `Justfile`, and migration tooling). Treat these as
black boxes to be characterized factually.

## Questions
1. How are end-to-end tests defined, marked, and invoked across `tests/` and
   `tests_e2e/` — what pytest markers and Justfile recipes select them, how are
   they excluded from the default test run, and which individual test functions
   exist in each module?

2. How do the end-to-end tests detect a container-compose backend and what exact
   compose subcommands and flags do they pass (for example `up -d --wait
   --build` and `down -v`)? Where is this compose-detection and compose-up logic
   defined, and is any of it duplicated between `tests/test_e2e.py` and
   `tests_e2e/_scaffold.py`?

3. Which concrete compose backends do the detection candidates (`docker
   compose`, `podman compose`, `podman-compose`) resolve to, and which `up`
   subcommand options does each backend support versus reject — particularly
   options used to block until services are healthy?

4. How does the generated `compose.yml` express service startup ordering and
   readiness (service healthchecks, `depends_on` conditions, the `migrate`
   service), and how do the tests depend on that readiness being signalled
   before they make HTTP assertions?

5. What does the scaffolded package's `just check` / `just test` recipe execute,
   and what determines whether the inner pytest run succeeds — including
   coverage thresholds and flags in `pyproject.toml` (`--cov-fail-under`,
   `--no-cov-on-fail`), the bundled template tests that ship in the scaffold, and
   the xdist `-n "$(nproc --ignore=1)"` worker configuration?

6. How do the tests verify a live application and database — which endpoints
   (`/livez`, `/readyz`) and migration recipes (`just makemigration`, `just
   migrate`) are exercised, how is the host able to reach the containerized
   Postgres and app (port exposure, `DATABASE_URL`), and where are those
   endpoints and recipes defined in the templates?
