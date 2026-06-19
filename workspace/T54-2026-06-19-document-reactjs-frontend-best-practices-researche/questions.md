# Research Questions

## Context
This research spans two areas. First, the current (year 2026) state of the
ReactJS frontend ecosystem as documented online — Vite, TypeScript, testing,
data fetching, and API client generation. Second, the existing repository's
documentation conventions and backend template under `docs/` and
`backend_template/`, which any new frontend documentation should align with.

## Questions
1. What is the currently recommended way to scaffold and structure a ReactJS
   application with Vite (project layout, TypeScript configuration, environment
   variables, dev server, and production build), and what conventions are
   considered standard in 2026?

2. What approaches exist for automatically synchronizing a frontend with a
   backend's API schema — for example generating a typed TypeScript client or
   types from an OpenAPI specification — and what tools, generators, and
   workflows are commonly used?

3. How does the existing FastAPI `backend_template` expose its API contract
   (e.g. OpenAPI schema), and how is the backend currently documented in
   `docs/` (structure, sections, citation style, depth)?

4. What are the prevailing patterns for unit and component testing of React
   applications (test runners such as Vitest, component testing libraries,
   mocking of network/API calls, coverage), and how are they configured
   alongside Vite?

5. What patterns are recommended for data fetching, server-state management, and
   client-state management in React applications (e.g. query/caching libraries,
   form handling, error and loading states)?

6. What tooling is considered standard for React frontend code quality and
   delivery in 2026 — linting, formatting, type checking, and continuous
   integration — and how does it parallel the Python tooling already used in
   this repository (`just`, lint/format/typecheck/test gates)?
