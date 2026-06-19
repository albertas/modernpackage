# Research Questions

## Context
Focus on the `modernpackage/` CLI package (especially `main.py`), the
`backend_template/` and `frontend_template/` directories, the `tests/` suite,
the `Justfile`, and the design/spec documents under `docs/`. The areas of
interest are how command-line options are parsed and threaded into the package
initialization flow, and how template trees are copied and wired into a
generated project.

## Questions
1. How does the CLI parse its command-line options in `main.py`, and how do the
   parsed option values flow through `init_new_package` into the steps that
   build a generated package?
2. What is the end-to-end sequence of operations that `init_new_package`
   performs on a freshly cloned package (clone, metadata, stripping, template
   injection, `just init`, `just check`), and in what order do they run?
3. How are files removed from or retained in a generated package by default —
   what does `_strip_scaffolding` delete, and which paths are always removed
   versus conditionally re-added?
4. How are the `backend_template/` and `frontend_template/` trees copied into a
   generated package, and how are their dependencies, Justfile recipes, and the
   `just init` rename/version-reset steps coordinated with the injected files?
5. What is the structure and content of `backend_template/` (FastAPI app, async
   database setup, Alembic migrations, container files, health endpoints) and of
   `frontend_template/` (Vite, Vitest, generated API client, scripts)?
6. How is the scaffolding behavior currently tested — what do `tests/test_main.py`
   and `tests/test_e2e.py` cover, and how do the backend and frontend template
   projects run their own tests and checks?
7. What guidance do the documents under `docs/` provide about the backend,
   frontend, containerization, and API-schema-synchronization conventions the
   templates are expected to follow?
