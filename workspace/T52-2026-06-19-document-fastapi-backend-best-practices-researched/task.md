# Task

Produce a new `docs/` reference page documenting current (year 2026) best practices for building a
production-grade FastAPI backend, covering FastAPI application structure, SQLAlchemy 2.0 async with
asyncpg, Alembic migrations, uv-based dependency management, containerization, and dependency
injection for tests. The document is forward-looking (no backend code exists in the repo yet) and
exists to inform a planned `--backend`/`--fastapi` scaffolder option that will emit a fully
functional backend with a database-health endpoint and Justfile migration targets.
