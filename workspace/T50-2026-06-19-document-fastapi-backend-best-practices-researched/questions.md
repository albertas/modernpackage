# Research Questions

## Context
Focus on two areas. First, the repository's `docs/` directory: its file structure, navigation
and cross-linking conventions, and the existing `docs/containerization.md` reference. Second,
established external best practices for Python web-service backends built with FastAPI,
SQLAlchemy, asyncpg, Alembic, and the `uv` toolchain. Treat the external topics as a literature
review of current, widely-recommended conventions.

## Questions
1. How is the `docs/` directory organized — what header/backlink convention, hub-table
   registration, cross-linking style, and prose tone do existing files (especially
   `overview.md` and `containerization.md`) follow, and what does a new doc need to match them?

2. What does `docs/containerization.md` already cover regarding a service backend (base images,
   `uv` installation, multi-stage builds, healthchecks, database services, compose stacks), so
   that overlapping topics can be cross-referenced rather than duplicated?

3. What are the current recommended patterns for structuring a FastAPI application — project
   layout, routers/APIRouter organization, configuration/settings management, lifespan/startup
   handling, and FastAPI's own dependency-injection (`Depends`) system?

4. What are the established best practices for asynchronous database access with SQLAlchemy 2.x
   and the asyncpg driver — async engine and session factory setup, session lifecycle and
   request-scoped sessions, connection pooling, and declarative model definitions?

5. How is Alembic configured and operated for async SQLAlchemy projects — environment setup for
   an async engine, autogeneration of migrations, the makemigration/migrate workflow, and how
   migrations are typically exposed through task runners such as a Justfile?

6. What patterns exist for testing FastAPI backends using dependency injection — overriding
   dependencies via `app.dependency_overrides`, injecting a test database or session, fixture
   strategies (transaction rollback vs. fresh schema), and async test client setup?

7. How does the `uv` toolchain integrate with a FastAPI service — declaring runtime and dev
   dependencies, locking, running the server and migration commands, and aligning with the
   strict tooling conventions already used in this project (ruff, mypy, pytest, coverage)?
