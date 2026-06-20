# Research Questions

## Context
Focus on the scaffolding CLI that clones a template and injects optional backend
and frontend templates (`modernpackage/main.py`), the React/Vite frontend
template (`frontend_template/`), the FastAPI backend template
(`backend_template/`), and the test/CI/orchestration setup across the repository
(`tests/`, `Justfile`, compose files, `docs/`).

## Questions
1. How does the scaffolding CLI inject the frontend and backend templates into a
   generated package — which functions copy template trees, append
   dependencies, and append Justfile recipes, and what controls whether each
   template is included?

2. What is the structure of the React/Vite frontend template — how is the root
   component rendered and tested, how is the dev server configured (including any
   proxying to the backend), and how is the typed API client generated and
   consumed?

3. What HTTP endpoints does the FastAPI backend template expose, what payloads
   and status codes do they return, and how does each interact with the
   database?

4. What test setups already exist across the templates and the repository —
   frontend unit tests, backend tests, and the end-to-end scaffolding test —
   and how is each configured, discovered, and run?

5. How are containerization and database orchestration defined for a generated
   package (Containerfile, compose services, healthchecks, migrations), and how
   does the existing end-to-end test bring up and probe the full stack?

6. How are Justfile recipes and CI pipelines structured for both this repository
   and a generated package, and which checks run by default versus on demand
   (e.g. checks that require Node, a database, or a container runtime)?
