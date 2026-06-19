# Design Discussion

This task produces **one Markdown documentation file** — not code. The
deliverable is `docs/reactjs_frontend.md`, a vetted reference for a modern (2026)
Vite + React + TypeScript frontend that will later guide a `--fullstack` /
`--reactjs` scaffolding option. The design below decides the file's scope,
structure, and house style so the writing phase has zero open questions.

## Current State

- The repo is a self-replicating Python CLI scaffolder. It scaffolds Python
  packages and, via `--backend`/`--fastapi`, a FastAPI service. **No frontend
  template, no `frontend_template/`, and no React code exist today**
  (research.md:271-273).
- The FastAPI backend already exposes a machine-readable API contract for free:
  `FastAPI(lifespan=lifespan)` with no overrides means OpenAPI is auto-served at
  `/openapi.json`, `/docs`, `/redoc` (`app.py:31`, research.md:96-98). However the
  template defines **no Pydantic response models** — only `dict`/`JSONResponse`
  (`health.py:32-48`, research.md:104-106) — so generated TS types for current
  endpoints would be minimal (research.md:259-262).
- `docs/` holds 10 files indexed by `overview.md`. The doc to mirror is
  `docs/fastapi_backend.md` (534 lines): one H1 + context paragraph + a bare
  `[overview.md](overview.md)` link near the top + **six `---`-separated H2
  sections, each closing with `### Anti-patterns to Avoid`** (research.md:123-129).
- House citation style in `fastapi_backend.md`: code shown via **embedded fenced
  code blocks** (not `file:line`), external refs as inline parenthetical markdown
  links, version numbers cited inline ("since FastAPI 0.95.0")
  (research.md:130-133). Sibling `containerization.md` mirrors this exactly.
- The repo's quality model is **Rust combined lint+format (Ruff) + separate strict
  typecheck (mypy) + test + audit**, driven by one aggregate `just check`
  (`Justfile:53`) called by CI (`.gitlab-ci.yml:22`) (research.md:231-248).

## Desired End State

A single file `docs/reactjs_frontend.md` (~450-550 lines, comparable to
`fastapi_backend.md`) that documents 2026 best practices for the future generated
frontend. Verification (this is documentation, so checks are editorial):

1. Opens with one H1 + context paragraph + `[overview.md](overview.md)` link,
   exactly like `fastapi_backend.md:1-9`.
2. Six `---`-separated H2 sections, each ending in `### Anti-patterns to Avoid`.
3. Every tool/library named with its 2026 version from research (e.g. Vite 8.x,
   React 19, Vitest 4.1, TanStack Query v5, ESLint v10).
4. Code shown via fenced blocks (config snippets, npm scripts), not `file:line`.
5. The API-sync section explicitly connects to the backend's `/openapi.json`
   contract so the fullstack story is coherent.
6. A new row for `reactjs_frontend.md` is conceptually ready for `overview.md`'s
   file table (research.md:21-29) — but see "What We're NOT Doing".

## Patterns to Follow

- **Document skeleton** — mirror `fastapi_backend.md:1-9`: H1 `# modernpackage —
  ReactJS Frontend`, a 3-5 line context paragraph framing the `--fullstack`/
  `--reactjs` flag, then the `[overview.md](overview.md)` link
  (research.md:120-122).
- **Section rhythm** — six H2 blocks separated by `---`, each with H3 subsections,
  the **last H3 always `### Anti-patterns to Avoid`** (research.md:127-129,
  263-266). This is the single most important structural pattern.
- **Citation style** — fenced code snippets for `vite.config.ts`, `tsconfig`,
  `package.json` scripts, ESLint flat config, Vitest setup; inline parenthetical
  links for external sources; inline version numbers (research.md:130-133).
- **Tooling parallelism** — explicitly map JS/TS gates to the repo's Python gates
  (research.md:236-248): `prettier --check`↔`check-format`, `eslint .`↔`check-lint`,
  `tsc --noEmit`↔`check-typecheck`, `vitest run`↔`test`, `npm audit`↔`audit`.
- **Pattern NOT to follow**: do **not** use `file:line` citation style here even
  though `architecture.md`/`specification.md` do (research.md:134-136) — the doc
  being mirrored (`fastapi_backend.md`) uses snippets, and there is no frontend
  source to cite anyway.

## Design Decisions

1. **Filename `docs/reactjs_frontend.md`** — mirrors `fastapi_backend.md` naming
   and the task's explicit "mirroring `docs/fastapi_backend.md`" instruction.
2. **Six H2 sections mapped to the six research questions** — (1) Scaffolding &
   Project Structure (Vite 8 + React 19 + TS, layout, env, dev server, build);
   (2) API Schema Synchronization (OpenAPI → typed TS client); (3) Testing
   (Vitest + RTL + MSW); (4) Data & State Management (TanStack Query + Zustand +
   RHF/Zod); (5) Code Quality & Tooling (ESLint/Prettier/tsc, npm scripts);
   (6) CI & Delivery. This keeps the 6-section house shape while covering all
   research. Q1/Q6 split keeps each section near `fastapi_backend.md` length.
3. **Recommend ONE primary stack, mention alternatives briefly** — a scaffolder
   needs a single vetted choice, not a menu. Primary picks: Vite `react-ts`
   template; **Hey API (`@hey-api/openapi-ts`)** for client generation (FastAPI's
   own recommended generator and used by `full-stack-fastapi-template`,
   research.md:67-70); Vitest + React Testing Library + MSW; TanStack Query v5
   (server state) + Zustand (client state) + React Hook Form + Zod; ESLint v10
   flat config + Prettier 3.8; `tsc --noEmit` as separate gate. Alternatives
   (Orval, openapi-typescript, SWR, RTK Query, Jotai, Biome) get one-line mentions.
4. **Bias the API-sync section toward the FastAPI backend** — emphasize the
   `Pydantic → OpenAPI 3.1 → TS` chain (research.md:85) and CI drift enforcement
   (`tsc --noEmit` / `git diff --exit-code`, research.md:84). Note the current
   template's missing Pydantic response models as a callout so the fullstack
   reader knows to add them (research.md:259-262).
5. **Document an `npm run`-based gate set, acknowledge no `just` analog** — show
   `dev`/`build`/`preview`/`typecheck`/`lint`/`format`/`test` scripts and note
   `npm run` is the de-facto runner (research.md:220-224), while drawing the
   explicit parallel to `just check`.
6. **Hold open questions with best-judgment defaults** — where research flagged
   uncertainty (SWR patch version, `@hookform/resolvers`×Zod v4, research.md:269-270),
   present the recommendation without pinning a fragile patch version and note it
   as "verify at scaffold time."

## What We're NOT Doing

- **Not writing any frontend code, `frontend_template/`, or scaffolder changes.**
  This task delivers documentation only; the `--fullstack`/`--reactjs` flag
  implementation is future work.
- **Not editing `overview.md`'s index table, `Justfile`, CI config, or the
  backend template.** Scope is the single new doc. (Adding the index row can be a
  trivial follow-up; flagged, not done here, per CLAUDE.md §3 surgical changes.)
- **Not producing an exhaustive tool survey.** One vetted stack + brief
  alternatives, not a comparison matrix.
- **Not covering SSR/Next.js, routing libraries, styling/CSS frameworks, or
  e2e/Playwright in depth** — out of the research scope (which centered on Vite
  SPA + unit testing). Browser-mode testing gets at most a one-line mention.

## Open Risks

- **Version drift**: every pinned 2026 version (Vite 8.x, ESLint v10, Vitest 4.1,
  etc.) will age. Mitigation: cite versions inline as "as of 2026" and phrase
  recommendations around tools, not exact patches.
- **Generator choice durability**: Hey API is the FastAPI-blessed pick today
  (research.md:67-70), but the space is active (Orval, Kubb, openapi-typescript).
  Mitigation: recommend Hey API as primary, list alternatives so a future swap is
  low-cost.
- **Backend contract gap**: the current FastAPI template's lack of Pydantic
  response models means generated types are thin (research.md:259-262). The doc
  must call this out, or the fullstack workflow will look richer than it is.
- **Doc length balance**: covering six questions risks exceeding
  `fastapi_backend.md`'s 534 lines. Mitigation: keep alternatives terse; favor
  one canonical snippet per concept.
