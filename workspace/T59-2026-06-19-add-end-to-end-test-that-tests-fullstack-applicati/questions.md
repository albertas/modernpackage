# Research Questions

## Context
Focus on the end-to-end test suite under `tests/` (especially the pytest `e2e`
marker and any tests that scaffold a real package), the CLI scaffolding code in
`modernpackage/main.py` that handles the `--fullstack`/`--reactjs`/`--backend`
flags, and the `backend_template/` and `frontend_template/` directories together
with their generated `Justfile` recipes.

## Questions
1. How is the existing end-to-end test suite structured — how are tests marked,
   selected/excluded by default, and invoked (e.g. which Justfile recipes run
   them), and what setup/skip guards do they use for required external tools?

2. What does the current fullstack end-to-end test exercise step by step, and
   which scaffolding functions, generated commands, and assertions does it cover
   versus leave unexercised?

3. How does the `--fullstack`/`--reactjs` flag flow from CLI argument parsing
   through to template injection, and what is the full sequence of operations
   that produces a fullstack package (metadata, strip, inject, init, staging)?

4. What does the generated fullstack package contain and how is it meant to be
   run — what Justfile recipes exist for the backend and frontend, how are the
   backend service, database, and frontend dev/build/test steps invoked, and how
   are they wired together?

5. How do the backend template's application, health, and database modules work,
   and how is the database integration exercised (migrations, health/readiness
   endpoints, container/compose setup)?

6. How does the frontend template define and run its tests and its connection to
   the backend (test runner configuration, API schema synchronization, and any
   build or dev-server tooling)?
