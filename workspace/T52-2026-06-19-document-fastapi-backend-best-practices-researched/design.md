# Design Discussion

## Current State

`modernpackage` is a self-replicating CLI package scaffolder. It ships **no**
FastAPI/SQLAlchemy/Alembic/backend code today; the repo is a `uv`-managed package
that clones and rewrites itself (`research.md:5-9`). The relevant in-repo grounding is:

- **`docs/containerization.md`** — already documents the multi-stage `uv` build, the
  illustrative `Containerfile` (uv pin, bind-mount sync phases, `UV_*` env, `.venv` on
  `PATH`), the App+Postgres compose stack with `service_completed_successfully` migration
  gating, and the stdlib `/health` 200/503 `HEALTHCHECK` probe
  (`research.md:158-165`, `research.md:246-247`). This is the one doc whose terminology the
  new page must align with rather than restate.
- **`docs/overview.md`** — the documentation index with a "Documentation Files" table
  (`docs/overview.md:19-29`) that every docs page is linked from.
- **`pyproject.toml:30-40`** — uses the `[dependency-groups] dev = [...]` form (PEP 735),
  the exact pattern the backend uv guidance recommends (`research.md:143-144`).

The docs house-style is fixed and consistent across pages: an `# modernpackage — <Topic>`
H1, an `[overview.md](overview.md)` backlink on line 3, an explicit "forward-looking /
ships no X today" framing (`docs/containerization.md:1-9`), and `file:line` citations for
in-repo claims (`docs/specification.md:3`).

This task is the **research → design** handoff for `T52`. No backend exists; all six research
questions (`research.md`) are answered from authoritative external sources (FastAPI,
SQLAlchemy 2.0, asyncpg, Alembic, `uv`, Kubernetes/IETF), not observed repo patterns.

## Desired End State

A single new reference page, **`docs/fastapi_backend.md`**, (~current 2026 best practices)
documenting how to build a production-grade async FastAPI backend, so that a future
`--backend`/`--fastapi` scaffolder option can emit a working backend with a DB-health
endpoint and Justfile migration targets (`task.md:3-8`). The page covers the six research
axes: app structure/DI, SQLAlchemy 2.0 async + asyncpg, Alembic (async), `uv` deps +
containerization, DI-override testing, and health checks.

**Verification it is correct:**
- The page exists at `docs/fastapi_backend.md` and follows the house-style (H1, backlink,
  forward-looking note, `file:line` cites for in-repo references).
- It is linked from `docs/overview.md`'s "Documentation Files" table (`docs/overview.md:27`).
- Every technical recommendation traces to a `research.md` finding (no new unsourced claims).
- It **cross-references** `docs/containerization.md` for container/compose/migration/health
  mechanics instead of duplicating them.
- No backend code, `Containerfile`, `compose.yml`, or scaffolder logic is added — docs only.

## Patterns to Follow

- **Page skeleton** — mirror `docs/containerization.md:1-9`: H1 `# modernpackage — FastAPI
  Backend`, `[overview.md](overview.md)` on line 3, then a "ships no backend code today …
  forward-looking reference … illustrative templates, not committed files" paragraph.
- **Forward-looking framing** — `docs/containerization.md:1-9` is the exact precedent for
  documenting a capability the repo does not yet have.
- **External-source citation style** — `research.md` cites authoritative docs inline as
  named links (e.g. `research.md:30-31`, `research.md:54-56`); carry these through so the
  page is traceable.
- **In-repo citation style** — `docs/specification.md:3` ("Every architectural claim carries
  a `file:line` citation"); use `file:line` for any `pyproject.toml`/`containerization.md`
  reference.
- **Index registration** — add a row to the table at `docs/overview.md:19-29`, matching the
  existing one-line `**bold**: description` cell format.
- **Modern-API-only** — follow the "recent shifts" list (`research.md:252-257`): show
  lifespan (not `on_event`), `Annotated[..., Depends()]`, `DeclarativeBase`/`mapped_column`/
  `Mapped[]`/`async_sessionmaker`, `ASGITransport(app=...)`, pytest-asyncio `loop_scope`.

**Patterns NOT to follow (flag explicitly in the page):**
- `@app.on_event("startup"/"shutdown")` — deprecated since FastAPI 0.93.0 (`research.md:34-38`).
- `param: T = Depends(fn)` legacy style; pydantic `class Config` inner class (`research.md:39-41`,
  `research.md:27-29`).
- `sessionmaker(class_=AsyncSession)`, `declarative_base()`, `poolclass=QueuePool` for async,
  default `expire_on_commit=True` (`research.md:60-61`, `research.md:68-70`, `research.md:80-81`).
- httpx `app=` shortcut (removed 0.28); Starlette `TestClient` for async resource sharing;
  pytest-asyncio `event_loop` fixture (removed 1.0) (`research.md:188-197`, `research.md:206-213`).
- DB connectivity checks in **liveness** probes — causes cluster-wide restart loops; they
  belong in **readiness** (`research.md:230-235`).

## Design Decisions

1. **Filename `docs/fastapi_backend.md`** — snake_case matches every existing docs file
   (`containerization.md`, `backlog_formats.md`, `data_flows.md`). A single page (not a
   `docs/backend/` tree) matches the flat docs layout.
2. **One page, six sections mapped to the research questions** — `## Application Structure &
   DI`, `## SQLAlchemy 2.0 Async + asyncpg`, `## Alembic (Async Migrations)`, `## Dependencies
   & Containerization (uv)`, `## Testing with DI Overrides`, `## Health Checks`. Keeps the
   research-to-doc trace 1:1 and easy to verify.
3. **Cross-reference, don't duplicate, containerization** — the uv multi-stage build, compose
   App+Postgres stack, one-shot `migrate` service gating, and `HEALTHCHECK` probe already live
   in `docs/containerization.md` (`research.md:261-263`). The backend page links to it and adds
   only the backend-specific layer (Alembic env.py async bridge, migration-replica safety,
   readiness-vs-liveness DB check). Prevents drift between two docs.
4. **Illustrative code snippets, kept minimal** — short fenced examples for the load-bearing,
   easy-to-get-wrong idioms only (lifespan + `app.state`, `get_db` async-generator dependency,
   `async_sessionmaker(expire_on_commit=False)`, async `env.py` `run_sync` bridge, readiness
   `SELECT 1`). Not a full reference implementation — that is the scaffolder's job. Matches
   `containerization.md`'s "illustrative templates" stance.
5. **Document the `+asyncpg` cross-cutting thread once, reference it** — `postgresql+asyncpg://`,
   `expire_on_commit=False`, no-lazy-load/eager loaders, `NullPool` for short-lived processes,
   pgBouncer statement-cache caveat recur across Q2/Q3/Q5/Q6 (`research.md:258-260`). State
   each in its primary section and back-reference rather than repeat.
6. **Health section anchored to readiness-vs-liveness semantics** — lead with the K8s probe
   distinction and the "DB check belongs in readiness" rule (`research.md:230-235`), then the
   concrete `SELECT 1` + `asyncio.timeout` impl returning 503 (`research.md:220-229`), and link
   to the existing `containerization.md` `HEALTHCHECK` (`research.md:246-247`).
7. **Justfile migration targets noted, not specified** — the task mentions Justfile migration
   targets as a scaffolder deliverable (`task.md:8`); the page documents the *commands*
   (`alembic upgrade head`, `alembic check`, autogenerate) and notes they should become
   `just migrate` / `just makemigration` / `just migration-check` recipes, deferring exact
   recipe wording to scaffolder implementation.
8. **Pin version-sensitive claims to the release that introduced them** — e.g. lifespan
   (0.93.0), `Annotated` (0.95.0), pydantic-settings split (0.100), `compare_type` default
   (Alembic 1.12.0), `alembic check` (1.9.0), httpx `app=` removal (0.28) (`research.md:252-257`).
   Makes "current (2026)" claims auditable as releases move on.

## What We're NOT Doing

- **No backend code.** No `Containerfile`, `compose.yml`, `models.py`, `env.py`, FastAPI app,
  or tests are written. Docs only.
- **No scaffolder changes.** No `--backend`/`--fastapi` flag, no `modernpackage/` edits — this
  page only *informs* that future work (`task.md:6-8`).
- **No rewrite/migration of `docs/containerization.md`.** We link to it; we don't edit or
  restate its container/compose/health content (`research.md:261-263`).
- **No coverage of frameworks outside the research scope** — no Django, no Flask, no sync
  SQLAlchemy, no ORMs other than SQLAlchemy 2.0, no auth/observability/message-queue topics.
- **No exhaustive API tutorial.** This is a best-practices reference, not a step-by-step
  build guide; deep how-tos stay in the cited upstream docs.

## Open Risks

- **Source authority is uneven.** Official-doc coverage is strong, but some operational
  specifics (CI cache keys, exact probe thresholds, multi-replica migration locking) rest on
  widely-cited community references, not first-party docs (`research.md:272-274`). The page
  should attribute these honestly rather than present them as canonical.
- **Version drift.** "Current (2026)" recommendations are release-pinned; future releases may
  shift them. Decision 8 (pin-to-release) mitigates but does not eliminate this.
- **Terminology divergence from `containerization.md`.** If the new page and the existing one
  describe the migration/health flow with different words, readers get confused. Mitigation:
  Decision 3 — link, don't restate; reuse its exact terms.
- **No repo patterns to validate against.** All guidance is external best practice with zero
  in-repo backend precedent (`research.md:266-271`); the only in-repo anchors are
  `containerization.md` and `pyproject.toml`. Reviewers cannot check the page against a working
  backend until the scaffolder is built.
