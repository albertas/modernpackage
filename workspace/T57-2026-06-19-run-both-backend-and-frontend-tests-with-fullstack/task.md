# T57: Run both backend and frontend tests when a `--fullstack` scaffold is created

The `modernpackage` scaffolder can generate a `--fullstack` project that bundles
both a FastAPI backend and a React frontend. This task ensures that, after a
`--fullstack` scaffold is generated, both the backend test suite (pytest) and
the frontend test suite (Vitest) are executed and pass — verified through the
project's end-to-end test layer so regressions in either template are caught.
