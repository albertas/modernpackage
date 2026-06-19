# Research Questions

## Context
Focus on two areas. First, the existing documentation under `docs/` (its structure, formatting conventions, and the topics already covered) and the project's tooling surface — the `Justfile`, `pyproject.toml`, CI configuration (`.gitlab-ci.yml`, `.github/workflows/`), and how the project is built, run, and tested with `uv`. Second, current external (online) best practices for OCI containerization using Podman with Docker-compatible configuration, particularly as applied to Python applications managed with `uv`.

## Questions
1. How are the documentation files under `docs/` organized and formatted (heading conventions, code blocks, tables, cross-references), and how do existing reference documents present their guidance?
2. How does the project define and run its build, run, and test workflows today — what `Justfile` targets, `pyproject.toml` configuration, and `uv` commands exist, and how are they invoked?
3. How is the project's CI/CD configured (`.gitlab-ci.yml`, `.github/workflows/`), including the base images, installed tools, and the commands each pipeline runs?
4. What are current recommended practices for authoring container images for Python applications — Containerfile/Dockerfile structure, base image selection, multi-stage builds, layer caching, dependency installation with `uv`, and producing small, reproducible images?
5. What are the current best practices for using Podman specifically (rootless containers, `podman build`/`podman run`, `podman-compose` or Compose-spec files, and pod/quadlet usage), and which conventions keep Podman configuration compatible with Docker?
6. What are the recommended practices for container security, runtime configuration, and local-development ergonomics — non-root users, image scanning, environment/secret handling, healthchecks, volume mounts, and networking for a typical Python service?
7. What guidance exists for orchestrating multi-service local stacks (e.g., an application plus a database) with Compose-spec files in a way that runs identically under both Podman and Docker?
