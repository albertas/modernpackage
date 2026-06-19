# Research Questions

## Context
Focus on current (year 2026) best practices for asynchronous Python web service backends built with
FastAPI, SQLAlchemy 2.0, asyncpg, and Alembic, managed with the `uv` toolchain and run in containers.
Prioritize authoritative, recent sources (official docs, maintainer guidance, widely-cited community
references) and note where recommendations have shifted in recent releases. Also consult the existing
repository docs (`docs/containerization.md`, `docs/architecture.md`) to align terminology and avoid
duplicating already-documented container guidance.

## Questions
1. How are production FastAPI applications structured today — project/package layout, router and
   module organization, settings/configuration management, application lifecycle (lifespan/startup),
   and how is FastAPI's dependency-injection system used to provide shared resources such as database
   sessions?
2. What are the recommended patterns for integrating SQLAlchemy 2.0 in async mode with the asyncpg
   driver — engine and async session creation, session-per-request scoping, connection pooling
   configuration, declarative model/base setup, and transaction handling?
3. How is Alembic configured and operated for an async SQLAlchemy/asyncpg project — environment
   setup for async engines, autogenerate workflows and their limitations, migration naming and
   ordering conventions, and how migrations are run and tested?
4. What are current conventions for managing an async backend's dependencies and reproducible builds
   with `uv` (lockfiles, dependency groups, syncing in CI/containers), and how is such a service
   containerized alongside a PostgreSQL database (multi-stage images, compose-based local stacks,
   migration execution at deploy/startup)?
5. What patterns exist for testing FastAPI applications using dependency-injection overrides —
   substituting database sessions/engines, providing isolated or transactional test databases,
   async test clients, and fixture strategies for setup and teardown?
6. How are operational health-check endpoints implemented in FastAPI services, particularly ones that
   report database connectivity/health, and what conventions exist for liveness vs. readiness probes?
