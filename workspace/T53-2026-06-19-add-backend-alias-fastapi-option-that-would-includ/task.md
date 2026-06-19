# Task

Add a `--backend` option (with alias `--fastapi`) to the `modernpackage`
scaffolder that, when set, includes a fully functional FastAPI backend in the
generated package. The backend must use FastAPI, SQLAlchemy 2.0 async with
asyncpg, Alembic migrations, and containerization, expose a health endpoint that
reports database health, and add `just makemigration` / `just migrate` recipes —
following the conventions documented under `docs/`.
