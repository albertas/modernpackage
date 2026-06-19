# Research Findings

Scope: external state of the ReactJS frontend ecosystem (2026) plus the existing
repo's `docs/` conventions and `backend_template/` API contract. Versions below
are as reported by web research dated June 2026; repo claims carry `file:line`.

---

## Q1: Scaffolding & structuring a Vite + React app (2026 conventions)

### Findings
- **Scaffold command**: `npm create vite@latest` (interactive) or non-interactive
  `npm create vite@latest my-app -- --template react-ts` (also `react-swc-ts`).
  Equivalents: `yarn create vite`, `pnpm create vite`, `bun create vite`.
  Source: [Vite Getting Started](https://vite.dev/guide/).
- **Current versions**: Vite **8.x** (released 2026-03-12), React **19**. Vite 8
  replaced esbuild+Rollup with Rust-based **Rolldown**; `@vitejs/plugin-react` v6
  dropped Babel for **Oxc**. Node 20.19+/22.12+ required.
  Source: [Vite 8 announcement](https://vite.dev/blog/announcing-vite8).
- **Templates**: `react`, `react-ts`, `react-swc`, `react-swc-ts`. Default
  `react-ts` now uses Oxc internally; `react-swc-ts` uses SWC. Both Rust-based, no
  meaningful speed gap. Custom Babel plugins (e.g. React Compiler 1.0) require
  `@rolldown/plugin-babel` added manually.
- **Generated layout**: `index.html` at project root, `src/main.tsx` (entry via
  `ReactDOM.createRoot`), `src/App.tsx`, `public/`, `src/assets/`,
  `src/vite-env.d.ts` (`/// <reference types="vite/client" />`). Dev server on
  `:5173`. Default scripts: `dev`, `build`, `preview`, `lint`.
- **Folder conventions** (no single enforced standard; progressive model from
  Robin Wieruch's [React Folder Structure 2026](https://www.robinwieruch.de/react-folder-structure/)):
  small → `components/ hooks/ utils/ assets/`; medium adds `context/ types/
  services/`; large → **feature-based** `features/<name>/{components,hooks,utils,
  index.ts}` with shared code in top-level dirs. Rule: code flows shared→features,
  features don't import each other. PascalCase component files, camelCase hooks,
  `index.ts` barrel exports.
- **TypeScript config split** (since Vite 4/5, still current): `tsconfig.json`
  (references-only orchestrator), `tsconfig.app.json` (browser `src/`),
  `tsconfig.node.json` (`vite.config.ts`). Standard settings: `"strict": true`,
  `"moduleResolution": "bundler"`, `"jsx": "react-jsx"`, `"noEmit": true`,
  `"isolatedModules": true` (required by Oxc), `noUnusedLocals/Parameters`.
  Path aliases via `resolve.tsconfigPaths: true` (Vite 8 built-in) or manual
  `resolve.alias` + `paths`. Source: [Vite Features](https://vite.dev/guide/features).
- **Env vars**: `.env`, `.env.local`, `.env.[mode]`, `.env.[mode].local` (load
  order, `.local` git-ignored). Only `VITE_`-prefixed vars exposed to client via
  `import.meta.env`; also `MODE`, `PROD`, `DEV`, `BASE_URL`, `SSR`. All values are
  strings. Types augmented in `vite-env.d.ts` via `ImportMetaEnv`. Modes via
  `--mode staging`. Source: [Env & Mode](https://vite.dev/guide/env-and-mode).
- **Dev server**: native-ESM HMR + React Fast Refresh (auto-wired); `server.proxy`
  in `vite.config.ts` (`changeOrigin`, `rewrite`, `ws`, `^`-prefixed regex keys);
  `strictPort`. Source: [Server Options](https://vite.dev/config/server-options).
- **Production build**: `vite build` → `dist/`; Rolldown bundler
  (`build.rolldownOptions`, old `rollupOptions` deprecated); default target
  `'baseline-widely-available'`; automatic code splitting on dynamic `import()`;
  `manualChunks`; `vite preview` serves `dist/` on `:4173`.
  Source: [Building for Production](https://vite.dev/guide/build).

---

## Q2: Synchronizing frontend with backend API schema (OpenAPI → TS)

### Findings
- **openapi-typescript** (v7, types-only `.d.ts`, no runtime) + **openapi-fetch**
  (6 kb typed fetch wrapper) + **openapi-react-query** (TanStack hooks). `--check`
  flag enables CI drift detection. [openapi-ts.dev](https://openapi-ts.dev/introduction),
  [GitHub](https://github.com/openapi-ts/openapi-typescript).
- **@hey-api/openapi-ts (Hey API)** — plugin-based; emits `types.gen.ts`,
  `sdk.gen.ts`, `schemas.gen.ts`, optional client (fetch/axios/ky) and a
  `@tanstack/react-query` plugin that produces `queryOptions()`/`mutationOptions()`
  **factories, not hooks**. **FastAPI's own docs name Hey API as the primary
  recommended TS generator**; the `full-stack-fastapi-template` uses it.
  [heyapi.dev](https://heyapi.dev/), [FastAPI Generating Clients](https://fastapi.tiangolo.com/advanced/generate-clients/).
- **Orval** (v8.18, 2026-06) — single `orval.config.ts`; `client` option emits
  plain functions or **one hook per operation** for `react-query`/`swr`/`vue-query`
  etc., plus models, optional Zod schemas, and **MSW mocks with Faker**.
  `mode: 'tags-split'`, `--watch`. [orval.dev](https://orval.dev/).
- **openapi-generator-cli** (`typescript-axios`/`typescript-fetch`) — original
  language-agnostic generator, **requires Java 11+**; emits API classes + models,
  no hooks/Zod/mocks. [openapi-generator.tech](https://openapi-generator.tech/).
- **swagger-typescript-api** (v13, pure Node, EJS-templated) and **Kubb** (v4/v5,
  modular plugins: ts/client/react-query/zod/faker/msw) round out the field.
- **Workflows**: source spec from a running backend's URL (FastAPI serves
  `/openapi.json`) **or** a committed `openapi.json` exported via Python
  `app.openapi()`. npm scripts (`generate-client`/`orval`) regenerate; watchers
  (`chokidar` on spec) auto-regen. **CI enforcement** in 3 patterns: regenerate &
  commit, `git diff --exit-code`, or rely on `tsc --noEmit` surfacing drift as
  type errors. FastAPI chain: `Pydantic → OpenAPI 3.1 → TS types`.
  Sources: [Vinta monorepo guide](https://www.vintasoftware.com/blog/nextjs-fastapi-monorepo),
  [FastAPI full-stack template (DeepWiki)](https://deepwiki.com/fastapi/full-stack-fastapi-template/5.3-openapi-client-generation).

---

## Q3: How `backend_template` exposes its contract & how `docs/` documents it

### Findings — API contract (Part A)
- App factory `create_app()` at `backend_template/modernpackage/app.py:29-33` calls
  `FastAPI(lifespan=lifespan)` at `app.py:31` with **no** `title`/`version`/
  `openapi_url`/`docs_url` args. FastAPI defaults therefore apply: title `"FastAPI"`,
  version `"0.1.0"`, OpenAPI auto-served at `/openapi.json`, `/docs`, `/redoc`. No
  explicit OpenAPI configuration anywhere.
- Lifespan (`app.py:18-26`) builds the async engine + `async_sessionmaker`
  (`expire_on_commit=False`) into `app.state`; disposes engine on shutdown.
  `app.include_router(health_router)` at `app.py:32`.
- Routes on `APIRouter()` (`health.py:15`): `GET /livez` (`health.py:32-35`,
  returns `{'status':'pass'}`, annotated `dict[str,str]`) and `GET /readyz`
  (`health.py:38-48`, `Annotated[bool, Depends(database_ready)]`, 200 pass /
  `JSONResponse` 503 fail at `health.py:44-46`). **No Pydantic `BaseModel`
  response models exist** — plain dicts/`JSONResponse`.
- DB layer (`db.py`): `database_url()` (`db.py:41-43`) reads `DATABASE_URL`,
  default `db.py:23`; `get_db` async generator (`db.py:51-57`); `DbSessionDep`
  alias (`db.py:60`); `Base` (`db.py:35-38`).
- Tests `backend_template/tests/test_app.py`: 6 sync-`TestClient` tests using
  `app.dependency_overrides[database_ready]` (`test_app.py:52-67`) and fake
  engines (`test_app.py:17-38`).
- `compose.yml:3-38` defines `app`/`migrate`/`db` (postgres:17, `pg_isready`
  healthcheck); `Containerfile` two-stage (uv builder + slim runtime), CMD
  `uvicorn modernpackage.app:create_app --factory` (`Containerfile:26`), stdlib
  HEALTHCHECK on `/readyz` (`Containerfile:24-25`).

### Findings — `docs/` conventions (Part B)
- 10 files under `docs/`. Index is `overview.md` (prose + file table at
  `overview.md:21-29` + `just` reference at `overview.md:34-53`). Every sectional
  doc opens with a bare `[overview.md](overview.md)` link near line 1-3
  (`fastapi_backend.md:3`, `containerization.md:3`).
- **`docs/fastapi_backend.md`** = the doc a frontend doc should mirror. 534 lines.
  One H1 `# modernpackage — FastAPI Backend` (line 1) + context paragraph
  (lines 3-9) + **six H2 sections separated by `---`**: App Structure & DI (11),
  SQLAlchemy 2.0 Async (107), Alembic (218), Dependencies & Containerization
  (322), Testing with DI Overrides (369), Health Checks (468). Each H2 has H3
  subsections **ending with `### Anti-patterns to Avoid`** (e.g. `:97`, `:208`,
  `:313`, `:459`).
- **Citation style**: `fastapi_backend.md` cites code via **embedded fenced code
  blocks** (Python/YAML/bash), **not** `file:line`. External refs are inline
  parenthetical markdown links (`:21-22`, `:114-115`). Version numbers cited
  inline ("since FastAPI 0.95.0"). Bolded concept name opens each H3 body.
- Contrast: `specification.md` and `architecture.md` use explicit `file:line`
  citations (`architecture.md:523` cites `main.py:592`); `containerization.md`
  mirrors `fastapi_backend.md`'s snippet style exactly.

---

## Q4: Unit & component testing of React apps (Vitest)

### Findings
- **Vitest 4.1.x** (June 2026) is the Vite-native runner; reuses Vite config,
  transformers, plugins. `test` block lives in `vite.config.ts` (recommended) or a
  `vitest.config.ts` that **fully overrides** unless combined via `mergeConfig`
  from `vitest/config`. [vitest.dev/config](https://vitest.dev/config/).
- Key options: `environment` (`'node'` default; `'jsdom'` or faster `'happy-dom'`
  for components — install separately); `globals: false` default (set `true` for
  Jest-style globals + RTL auto-cleanup, add `"vitest/globals"` to tsconfig
  types); `setupFiles` (runs before each test file).
- **React Testing Library 16.3.x** (`@testing-library/dom` now a peer dep,
  install explicitly; React 19 support since v16.1). `render()`/`screen`, queries
  `getBy*`/`queryBy*`/`findBy*`, `data-testid` escape hatch.
  **@testing-library/user-event 14.x** — `userEvent.setup()`, all methods async.
  **@testing-library/jest-dom 6.9.x** — matchers via setup-file import
  `import '@testing-library/jest-dom/vitest'`.
- **Network mocking**: **MSW 2.14.x** is Vitest-docs-recommended. v2 API
  `http.get(...)` + `HttpResponse.json(...)`; Node integration `setupServer` from
  `msw/node` with `server.listen({onUnhandledRequest:'error'})`/`resetHandlers`/
  `close` in setup; `server.use()` per-test overrides. Module mocking via
  `vi.mock` (hoisted), `vi.fn`, `vi.spyOn`, `vi.importActual`. [mswjs.io](https://mswjs.io/docs/).
- **Coverage**: `@vitest/coverage-v8` (default) or `@vitest/coverage-istanbul`;
  since Vitest 3.2 v8 uses AST remapping ≈ Istanbul accuracy. Config under
  `test.coverage` with `provider`, `reporter`, `thresholds` (`lines/functions/
  branches/statements`, `perFile`). [Coverage guide](https://vitest.dev/guide/coverage).
- **Browser Mode** stable since Vitest 4.0 (real browsers via
  `@vitest/browser-playwright`); `vitest-browser-react` (v2.x, async `render()`,
  locators) is the purpose-built renderer. Playwright's `@playwright/
  experimental-ct-react` is a separate option.

---

## Q5: Data fetching, server-state & client-state management

### Findings
- **Core principle (recurring across 2026 sources)**: separate **server state**
  (remote-owned, stale-able → cache/refetch/invalidate) from **client state**
  (browser-owned UI state). Storing API responses in Redux/Zustand is named an
  anti-pattern. [NextFuture server-vs-client guide](https://nextfuture.io.vn/blog/react-server-state-vs-client-state-guide).
- **Server state — TanStack Query v5** (`@tanstack/react-query` 5.101, the
  standard). `useQuery(queryKey, queryFn)` → mutually-exclusive `isPending`/
  `isError`/`isSuccess` + separate `fetchStatus`. Array query keys drive cache
  separation. `staleTime` default 0, `gcTime` default 5 min (renamed from
  `cacheTime`). `useMutation` + `queryClient.invalidateQueries` in `onSuccess`.
  `useSuspenseQuery` delegates loading/error to Suspense + Error Boundaries.
  Alternatives: **SWR** (~4 kb, Vercel) and **RTK Query** (bundled in
  `@reduxjs/toolkit` 2.12). [TanStack Query v5](https://tanstack.com/query/v5/docs/framework/react/overview).
- **Client state**: **Zustand 5.0.x** (~3 kb `create()`/hook, leading choice for
  UI state); **Jotai 2.20.x** (atomic); **Redux Toolkit 2.12** (large/established
  apps, RTK Query for fetching); **React Context** for low-frequency tree-scoped
  state (theme/locale), >5 providers seen as a smell.
- **Forms**: **React Hook Form 7.79** (uncontrolled/ref-based, `useForm`/
  `register`/`handleSubmit`/`formState`) + **Zod 4.x** via `@hookform/resolvers`
  5.x (`zodResolver`, `z.infer` typing). **TanStack Form 1.33** emerging
  (headless, Standard Schema validation, deep TS inference). [react-hook-form.com](https://react-hook-form.com/), [zod.dev](https://zod.dev/).
- **Error/loading**: React Query `isPending`/`isLoading`/`isFetching`/`isError`;
  declarative `<Suspense fallback>` + `react-error-boundary`'s `<ErrorBoundary>`
  (nest ErrorBoundary outside Suspense); React 19 `use()` hook; TanStack
  `QueryErrorResetBoundary` for retry.

---

## Q6: Frontend code-quality & delivery tooling vs this repo's Python gates

### Findings — JS/TS ecosystem (2026)
- **Lint**: **ESLint v10** (2026-02-06, flat-config-only `eslint.config.js`; v9 EOL
  2026-08-06) + **typescript-eslint v8** (project-service auto-tsconfig discovery,
  presets `recommended`/`strict`/`stylistic` ± `-type-checked`) +
  `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`. The Vite `react-ts`
  template ships a flat `eslint.config.js` extending `js.recommended`,
  `tseslint.recommended`, `reactHooks['recommended-latest']`, `reactRefresh.vite`.
  Emerging Rust alternatives: **Biome v2.4** (lint+format one binary, type-aware
  rules without tsc) and **Oxlint v1.x** (lint-only, 50-100× faster).
  [typescript-eslint.io](https://typescript-eslint.io), [biomejs.dev](https://biomejs.dev).
- **Format**: **Prettier 3.8** standard (`eslint-config-prettier` disables
  conflicting rules); alternatives Biome (combined) or `@stylistic/eslint-plugin`.
- **Type check**: `tsc --noEmit` as a **separate gate** — Vite/esbuild strip types
  without checking, so type errors don't fail builds by default. TypeScript 7
  Go-native `tsgo` in preview.
- **package.json scripts** (de-facto standard): `dev`, `build`
  (`tsc --noEmit && vite build`), `preview`, `typecheck` (`tsc --noEmit`), `lint`
  (`eslint .`), `format` (`prettier --write .`), `format:check`, `test`/`test:run`
  (Vitest). `npm run` is the de-facto task runner (no universal `just` analog;
  Turborepo/Nx/Makefile for larger orchestration).
- **CI**: GitHub Actions / GitLab CI with parallel `lint`/`typecheck`/`test` jobs
  and a `build` job gated by `needs:`; `npm ci` for deterministic installs.
  Pre-commit via **husky v9** + **lint-staged v15** (per-file ESLint/Prettier;
  `tsc --noEmit` can't be staged-scoped so runs whole-project or in CI), or
  **simple-git-hooks** / **Lefthook**.

### Findings — parallel to this repo's Python gates
- Repo runner is **`just`** (`Justfile`), all recipes prefixed by a `sync`
  prerequisite running `uv sync` (`Justfile:14,20,23,26`). Aggregate gate
  `just check` = `check-format check-lint check-complexity check-typecheck test
  audit` (`Justfile:53`).
- Direct gate mapping (repo `Justfile` → JS/TS analog):
  - `check-format` → `ruff format --check` (`Justfile:29-30`) ↔ `prettier --check`
  - `check-lint` → `ruff check` (`Justfile:32-33`) ↔ `eslint .`
  - `check-complexity` → `ruff check --select C901` (`Justfile:35-36`) ↔ ESLint
    `complexity` rule (no separate JS step typically)
  - `check-typecheck` → `mypy` (`Justfile:38-39`) ↔ `tsc --noEmit`
  - `test` → `pytest -n nproc` (`Justfile:14-15`) ↔ `vitest run`
  - `audit` → `pip-audit` (`Justfile:41-42`) ↔ `npm audit`
- Ruff = combined lint+format (one tool) ↔ Biome on the JS side; the classic
  ESLint+Prettier split maps to two Python tools. The lint-vs-typecheck split is
  structurally identical in both ecosystems (whole-program analysis can't be
  per-file). Repo CI: `.gitlab-ci.yml:19-22` installs `uv`+`rust-just`, runs the
  single `just check`. Repo `overview.md:32-53` documents the `just` workflow.

---

## Cross-Cutting Observations
- The repo already standardizes on a **Rust-based combined lint+format tool
  (Ruff)** + **separate strict typecheck (mypy)** + **test** + **audit**, driven by
  a single aggregate `just check` gate (`Justfile:53`) called by CI
  (`.gitlab-ci.yml:22`). The 2026 JS/TS world offers the same gate shape via
  npm scripts; Biome is the nearest combined-tool analog to Ruff.
- FastAPI's auto-exposed `/openapi.json` (default in `app.py:31`) is exactly the
  input the Q2 generators consume — the contract is already machine-readable
  with no extra backend config, though the template defines **no Pydantic
  response models** (only `dict`/`JSONResponse`), so generated TS types for
  current endpoints would be minimal.
- `docs/fastapi_backend.md`'s house style (H1 + context + `[overview.md]` link +
  6 `---`-separated H2 sections, each closing with `### Anti-patterns to Avoid`,
  code shown via fenced snippets not `file:line`, inline version cites) is a
  concrete, reproducible template for any sibling doc.

## Open Areas
- Exact current **SWR** patch version unconfirmed (major 2.x). `@hookform/
  resolvers` × Zod v4 compatibility was under active work per a GitHub issue.
- The repo's `backend_template` has **no frontend code** and no existing
  `frontend_template/` — all frontend questions (Q1, Q2, Q4, Q5, Q6 JS side)
  are answered purely from external research, not repo precedent.
- No repo-side OpenAPI client generation exists today; Q2 findings are external.
