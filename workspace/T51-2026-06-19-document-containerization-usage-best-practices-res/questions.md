# Research Questions

## Context
Focus on two areas. First, the repository's own conventions: the `docs/` directory and how its
pages are structured/cross-linked, the project's toolset and configuration (`pyproject.toml`,
`Justfile`, `uv.lock`, Python version, any private package index), and whether any container
artifacts already exist in-repo. Second, current (year 2026) external best practices for
containerizing a `uv`-managed Python project where Podman is the primary runtime and the
configuration must remain Docker-compatible.

## Questions
1. How are the existing pages under `docs/` structured and cross-referenced (headings, linking
   conventions, tone, code-block style), and is there already a containerization document or any
   container artifacts (`Containerfile`, `Dockerfile`, `compose.yml`, `.dockerignore`) in the repo?
2. What does this project's toolchain and configuration look like that a container build must
   accommodate — the Python version requirement, dependency management via `uv`/`uv.lock`,
   `Justfile` recipes, and any private/authenticated package index declared in `pyproject.toml`?
3. What are the current recommended practices for authoring container images for a `uv`-managed
   Python project — installing/pinning `uv`, multi-stage builds, layer caching, `.dockerignore`,
   build-time environment variables, and venv activation at runtime?
4. What are the current practices for running containers with Podman while keeping configuration
   Docker-compatible — rootless containers and UID mapping, SELinux volume labels, Docker CLI/
   manifest parity, the Docker-API socket, and the Compose provider options?
5. What are the current container security best practices relevant to such a project — running as
   a non-root user, handling build-time and runtime secrets (including credentials for a private
   package index), and image vulnerability scanning?
6. What are the current practices for container healthchecks/readiness and for defining portable
   local multi-service stacks via the Compose Specification, including service networking and
   startup ordering between dependent services?
