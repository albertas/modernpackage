# Research Questions

## Context
Focus on the end-to-end test suite for the package scaffolder, the backend
template it injects (`backend_template/`), the migration/Alembic setup in that
template, and the test/Justfile/pyproject configuration that controls how
end-to-end tests are discovered and run. The relevant code lives in
`tests/`, `backend_template/`, `modernpackage/main.py`, `Justfile`, and
`pyproject.toml`.

## Questions
1. How are end-to-end tests currently located, marked, and discovered? Trace
   the pytest configuration (markers, `addopts`, coverage, `norecursedirs`) and
   the `Justfile` recipes that select end-to-end tests versus the regular test
   run, and identify what would change if such tests lived in a separate
   top-level directory.

2. How does an existing end-to-end test scaffold a backend-only application and
   bring it up against a real database? Trace the full flow from package
   generation (the `main._*` helpers used) through the `compose.yml` services
   (db, migrate, app) and how readiness is awaited.

3. How is the application's health/readiness check implemented and exercised,
   and how does it verify database connectivity? Trace the readiness probe
   endpoint, the engine/session wiring it depends on, and any host-side HTTP
   assertions made against it in existing tests.

4. How is the Alembic migration environment configured in the backend template,
   and how does autogeneration discover the schema? Trace `migrations/env.py`,
   the declarative `Base`/metadata, the naming convention, and what
   `DATABASE_URL` it reads at migration time.

5. What `Justfile` targets does the generated backend package expose for
   creating and applying migrations, where are they defined, and what exact
   commands do they run?

6. How are database tables/models defined and registered with the shared
   metadata in the backend template, and what existing examples (if any) of
   table definitions exist that a new table would follow?

7. What patterns do the existing end-to-end tests use for environment skip
   guards, compose-command detection, HTTP probing, and stack teardown that a
   new end-to-end test should reuse?
