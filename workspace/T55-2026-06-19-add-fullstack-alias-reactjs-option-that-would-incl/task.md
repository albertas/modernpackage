# Task

Add a `--fullstack` CLI flag (with alias `--reactjs`) to the modernpackage
scaffolder that injects both the existing FastAPI backend and a new, fully
functional API-driven ReactJS frontend into the generated package. The frontend
must use Vite, ship unit tests, and automatically synchronize its API client
against the backend's OpenAPI schema. This extends the existing optional
scaffolding flags (`--backend`/`--fastapi`) so users can bootstrap a complete
full-stack application in one command.
