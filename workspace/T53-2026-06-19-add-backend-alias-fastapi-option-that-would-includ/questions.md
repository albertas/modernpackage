# Research Questions

## Context
Focus on the `modernpackage` CLI scaffolder (`modernpackage/main.py`), its test
suite (`tests/`), the project `Justfile`, `pyproject.toml`, and the reference
material under `docs/` (especially `fastapi_backend.md`, `containerization.md`,
and `overview.md`). The relevant areas are command-line option parsing, the
clone-and-mutate pipeline that produces a generated package, the Justfile recipe
conventions, the testing conventions, and the documented backend/container
guidance.

## Questions
1. How are command-line options and flags defined and validated in
   `parse_args`, how are boolean/store-true flags and option aliases expressed,
   and how do parsed argument values flow from `main` through
   `init_new_package` into the rest of the scaffolding logic?

2. How does the scaffolder transform the cloned template tree after cloning —
   trace the full pipeline that rewrites metadata, removes files
   (`_strip_scaffolding`), writes stub files, and how the dry-run preview mirrors
   each of those actions? What mechanism, if any, exists for *adding* new files
   or directories into the generated package?

3. What are the conventions for `Justfile` recipes in this project, how does the
   `just init` recipe rename the `modernpackage` token across generated files,
   and how does the scaffolder rely on that literal token surviving into stub
   files? How are new recipes and their dependencies (e.g. `sync`) structured?

4. How is scaffolder behavior tested — what patterns exist for mocking the
   subprocess/`Popen`/`run` seam on the module, how are the `e2e`-marked tests
   structured, and what coverage and lint gates (`pyproject.toml`,
   `--cov-fail-under`, ruff `ALL`, mypy strict) must generated and scaffolder
   code satisfy?

5. What does the `docs/` reference material specify about a FastAPI + SQLAlchemy
   async + asyncpg + Alembic backend — application structure, lifespan/DI,
   migration safety, and health-check endpoint semantics — and how do these
   documents cross-reference one another and the existing `pyproject.toml`
   dependency-group conventions?

6. What does `docs/containerization.md` document about the Containerfile, the
   app + Postgres compose stack, migration-gating service ordering, and
   container-level healthchecks that a generated backend would need to include?
