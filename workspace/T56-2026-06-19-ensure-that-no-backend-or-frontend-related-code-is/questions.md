# Research Questions

## Context
Focus on the scaffolding CLI in `modernpackage/main.py`, the `backend_template/`
and `frontend_template/` directories, the generated package's `pyproject.toml`
and `Justfile`, and the test suite in `tests/`. The relevant flow is how the
tool clones the source repository, mutates that clone, and optionally injects
template trees and dependencies based on CLI options.

## Questions
1. How does the scaffolder produce a generated package from the source
   repository — trace the full sequence of steps that clone, strip, rename,
   inject, and commit the tree, and identify which steps run unconditionally
   versus which are gated on a CLI option.
2. What is removed from a cloned tree before it becomes a generated package,
   where is that removal list defined, and how does the stripping logic behave
   when a listed path is absent?
3. How do the `--backend`/`--fastapi` and `--fullstack`/`--reactjs` options
   change the generated package — which files, directories, runtime/dev
   dependencies, and Justfile recipes are added, and from where do they
   originate?
4. Across the repository (`pyproject.toml`, `Justfile`, `README.md`, `docs/`,
   and modules under `modernpackage/`), where are FastAPI, SQLAlchemy, Alembic,
   asyncpg, uvicorn, React, Vite, or other backend/frontend names and
   dependencies declared or referenced?
5. What do the existing tests in `tests/test_main.py` and `tests/test_e2e.py`
   assert about the contents of a generated package, and which assertions
   distinguish a no-flag package from a `--backend` or `--fullstack` package?
6. How are dependencies and Justfile recipes appended into a generated
   package's `pyproject.toml` and `Justfile`, and what is contained in the
   source repository's own `pyproject.toml` and `Justfile` by default?
