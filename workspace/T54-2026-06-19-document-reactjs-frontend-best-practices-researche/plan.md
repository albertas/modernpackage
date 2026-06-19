# Implementation Plan

## Overview

Write one new Markdown file `docs/reactjs_frontend.md` (~450–550 lines) that documents 2026
best practices for a future Vite 8 + React 19 + TypeScript frontend, mirroring the house style
of `docs/fastapi_backend.md` exactly: H1 + context paragraph + `[overview.md](overview.md)` link,
then six `---`-separated H2 sections, each closing with `### Anti-patterns to Avoid`.

**Scope reminders (from design.md "What We're NOT Doing"):**
- Documentation only. Do **not** create `frontend_template/`, write React/TS code, or change the scaffolder.
- Do **not** edit `overview.md`'s index table, `Justfile`, CI config, or the backend template.
- One vetted stack + terse alternatives, not a comparison matrix.
- No SSR/Next.js, routing, CSS frameworks, or e2e depth. Browser-mode testing gets one line.

**House-style rules to obey throughout (from research.md:130–133, verified against `docs/fastapi_backend.md`):**
- Code shown via fenced code blocks (```ts / ```bash / ```json / ```yaml), **never** `file:line` citations.
- External references as inline parenthetical Markdown links: `([Vite 8 announcement](https://vite.dev/blog/announcing-vite8))`.
- Version numbers cited inline ("as of 2026", "Vite 8.x", "since v16.1").
- Each H3 body **opens with a bolded concept name**, e.g. `**Feature-based folders.** ...`.
- The last H3 of every H2 section is exactly `### Anti-patterns to Avoid`.

All file paths below are relative to the repo root `/home/niekas/tools/modernpackage/`. The plan
builds the single file `docs/reactjs_frontend.md` incrementally; each phase appends/edits the same file.

---

## Phase 1: Skeleton & Section Scaffold

Establish the document frame that all later phases fill in. This freezes the structural contract.

### Changes

#### 1. Create the document skeleton
**File**: `docs/reactjs_frontend.md`
**Action**: create

Write the H1, a 3–5 line context paragraph framing the `--fullstack`/`--reactjs` flag, the
`[overview.md](overview.md)` link on line 3, then the six H2 headings each followed by a `---`
separator and an `### Anti-patterns to Avoid` stub. Mirror `docs/fastapi_backend.md:1-9` exactly
(H1 on line 1, blank line 2, `[overview.md](overview.md)` on line 3, blank line 4, context paragraph).

```markdown
# modernpackage — ReactJS Frontend

[overview.md](overview.md)

When scaffolded with the `--fullstack` flag (or `--reactjs` alias), `modernpackage` will generate
a modern Vite + React 19 + TypeScript single-page application wired to the FastAPI backend's
auto-generated OpenAPI contract. This document describes the 2026 best practices that the future
generated frontend template follows — scaffolding, API-schema synchronization, testing, state
management, code quality, and CI. For the backend it pairs with, see [fastapi_backend.md](fastapi_backend.md).

## Scaffolding & Project Structure

### Anti-patterns to Avoid

---

## API Schema Synchronization

### Anti-patterns to Avoid

---

## Testing

### Anti-patterns to Avoid

---

## Data & State Management

### Anti-patterns to Avoid

---

## Code Quality & Tooling

### Anti-patterns to Avoid

---

## CI & Delivery

### Anti-patterns to Avoid
```

**Note on separator count**: six H2 sections joined by `---` separators yields exactly **5** `---`
lines (one between each adjacent pair). Do not place a `---` after the final section.

### Verification
#### Automated
- [x] `grep -c '^## ' docs/reactjs_frontend.md` returns `6`
- [x] `grep -c '^### Anti-patterns to Avoid' docs/reactjs_frontend.md` returns `6`
- [x] `grep -c '^---$' docs/reactjs_frontend.md` returns `5`

#### Manual
- [x] `head -1 docs/reactjs_frontend.md` outputs exactly `# modernpackage — ReactJS Frontend`
- [x] `sed -n '3p' docs/reactjs_frontend.md` outputs exactly `[overview.md](overview.md)`
- [x] `head -3 docs/reactjs_frontend.md | grep -q 'overview.md'` exits 0

---

## Phase 2: Scaffolding & Project Structure (Q1)

Fill section 1: Vite 8 + React 19 + TS scaffold command, generated layout, feature-based folder
conventions, tsconfig split, env vars, dev server/proxy, production build, then its anti-patterns.

### Changes

#### 1. Replace the section-1 stub with full content
**File**: `docs/reactjs_frontend.md`
**Action**: modify (replace the `## Scaffolding & Project Structure` block, keeping the H2 heading
and ending with `### Anti-patterns to Avoid`)

Suggested H3 subsections, each opening with a bolded concept name:

- `### Scaffolding the App` — `**Vite create.**` Non-interactive scaffold; cite Vite 8.x (released
  2026-03-12, Rust-based Rolldown bundler, `@vitejs/plugin-react` v6 on Oxc), React 19, Node 20.19+/22.12+.

  ```bash
  npm create vite@latest my-app -- --template react-ts
  cd my-app && npm install
  ```

  One line: `react-swc-ts` is the SWC variant; both Rust-based with no meaningful speed gap. Custom
  Babel plugins (e.g. React Compiler 1.0) require `@rolldown/plugin-babel` added manually.
  Link: `([Vite Getting Started](https://vite.dev/guide/))`.

- `### Generated Layout` — `**Project shape.**` Describe `index.html` at root, `src/main.tsx`
  (`ReactDOM.createRoot`), `src/App.tsx`, `public/`, `src/assets/`, `src/vite-env.d.ts`
  (`/// <reference types="vite/client" />`). Dev server on `:5173`; default scripts `dev`/`build`/`preview`/`lint`.

- `### Feature-based Folders` — `**Feature-based folders.**` Progressive model
  ([React Folder Structure 2026](https://www.robinwieruch.de/react-folder-structure/)): small →
  `components/ hooks/ utils/ assets/`; large → `features/<name>/{components,hooks,utils,index.ts}`
  with shared code in top-level dirs. Rule: **code flows shared→features; features don't import each
  other.** PascalCase component files, camelCase hooks, `index.ts` barrel exports.

- `### TypeScript Config Split` — `**Three tsconfigs.**` Explain the triplet and show the orchestrator:

  ```json
  // tsconfig.json — references-only orchestrator
  {
    "files": [],
    "references": [
      { "path": "./tsconfig.app.json" },
      { "path": "./tsconfig.node.json" }
    ]
  }
  ```

  `tsconfig.app.json` covers browser `src/`; `tsconfig.node.json` covers `vite.config.ts`. Standard
  settings: `"strict": true`, `"moduleResolution": "bundler"`, `"jsx": "react-jsx"`, `"noEmit": true`,
  `"isolatedModules": true` (required by Oxc), `noUnusedLocals`/`noUnusedParameters`. Path aliases via
  `resolve.tsconfigPaths: true` (built into Vite 8) or manual `resolve.alias` + tsconfig `paths`.

- `### Environment Variables` — `**VITE_ prefix.**` Only `VITE_`-prefixed vars reach the client via
  `import.meta.env` (also `MODE`/`PROD`/`DEV`/`BASE_URL`/`SSR`); all values are strings. Load order:
  `.env`, `.env.local`, `.env.[mode]`, `.env.[mode].local` (`.local` git-ignored). Augment types:

  ```ts
  // src/vite-env.d.ts
  /// <reference types="vite/client" />
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL: string;
  }
  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
  ```

  Link: `([Env & Mode](https://vite.dev/guide/env-and-mode))`.

- `### Dev Server & Production Build` — `**Proxy and build.**` Show the dev proxy that forwards
  `/api` to the FastAPI backend and the build:

  ```ts
  // vite.config.ts
  import { defineConfig } from 'vite';
  import react from '@vitejs/plugin-react';

  export default defineConfig({
    plugins: [react()],
    resolve: { tsconfigPaths: true },
    server: {
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
  });
  ```

  `vite build` → `dist/` (Rolldown; configure via `build.rolldownOptions`, old `rollupOptions`
  deprecated); automatic code splitting on dynamic `import()`; `vite preview` serves `dist/` on `:4173`.

- `### Anti-patterns to Avoid` — bullets: non-`VITE_` secrets placed in client code (exposed in the
  bundle); cross-feature imports between `features/<name>` dirs; a single god `tsconfig.json` instead
  of the app/node split; relying on `vite build` to type-check (esbuild/Oxc strip types without checking).

### Verification
#### Automated
- [x] `grep -q 'react-ts' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'Vite 8' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'tsconfig.app.json' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'VITE_' docs/reactjs_frontend.md` exits 0

#### Manual
- [x] Section 1 contains ≥2 fenced code blocks: `awk '/^## Scaffolding & Project Structure$/{f=1} f&&/^## API Schema Synchronization$/{exit} f' docs/reactjs_frontend.md | grep -c '^```'` returns an even number `≥ 4` (≥2 open/close pairs)
- [x] `grep -q 'import.meta.env' docs/reactjs_frontend.md` exits 0

---

## Phase 3: API Schema Synchronization (Q2)

Fill section 2: the OpenAPI → TS chain wired to the FastAPI backend. Recommend Hey API as primary,
connect explicitly to backend `/openapi.json`, document CI drift enforcement, and call out the
backend's missing Pydantic response models.

### Changes

#### 1. Replace the section-2 stub with full content
**File**: `docs/reactjs_frontend.md`
**Action**: modify

Suggested H3 subsections:

- `### The Pydantic → OpenAPI → TS Chain` — `**One source of truth.**` State the chain
  `Pydantic → OpenAPI 3.1 → TS types`. The FastAPI backend auto-serves its contract at `/openapi.json`,
  `/docs`, `/redoc` with no extra config (`FastAPI(lifespan=lifespan)` applies defaults). The frontend
  consumes that contract to generate typed clients, so backend changes surface as TS type errors.

- `### Generating the Client (Hey API)` — `**Hey API.**` Recommend `@hey-api/openapi-ts` as primary
  (FastAPI's own docs name it the recommended TS generator; the `full-stack-fastapi-template` uses it).
  It emits `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, an optional client (fetch/axios/ky), and a
  `@tanstack/react-query` plugin producing `queryOptions()`/`mutationOptions()` factories.

  ```ts
  // openapi-ts.config.ts
  import { defineConfig } from '@hey-api/openapi-ts';

  export default defineConfig({
    input: 'http://localhost:8000/openapi.json', // or a committed ./openapi.json
    output: 'src/client',
    plugins: ['@hey-api/client-fetch', '@tanstack/react-query'],
  });
  ```

  ```json
  // package.json (scripts excerpt)
  {
    "scripts": {
      "generate-client": "openapi-ts"
    }
  }
  ```

  Links: `([Hey API](https://heyapi.dev/))`, `([FastAPI — Generating Clients](https://fastapi.tiangolo.com/advanced/generate-clients/))`.

- `### Drift Enforcement in CI` — `**Fail on drift.**` Three patterns: regenerate-and-commit; verify
  no uncommitted changes; or let `tsc --noEmit` surface drift as type errors.

  ```bash
  # CI: regenerate the client and fail if it differs from what's committed
  npm run generate-client
  git diff --exit-code src/client
  ```

- `### Backend Contract Gap` — `**Callout.**` The current `backend_template` defines **no Pydantic
  response models** — endpoints return plain `dict`/`JSONResponse` — so generated TS types for current
  endpoints are minimal. To get rich typed clients, add Pydantic `response_model`s to backend routes
  first. (Cross-reference [fastapi_backend.md](fastapi_backend.md).)

- `### Anti-patterns to Avoid` — bullets: hand-writing TS interfaces that duplicate the backend schema;
  generating against a stale committed `openapi.json` without a refresh step; skipping CI drift checks
  so backend changes silently break the client at runtime.

One-line alternatives (in prose, terse): openapi-typescript (+openapi-fetch/openapi-react-query, `--check`
for CI drift), Orval (one hook per operation + MSW mocks), Kubb (modular plugins), openapi-generator-cli
(requires Java 11+).

### Verification
#### Automated
- [x] `grep -q 'hey-api\|Hey API' docs/reactjs_frontend.md` exits 0
- [x] `grep -q '/openapi.json' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'Pydantic' docs/reactjs_frontend.md` exits 0
- [x] `grep -qE 'git diff --exit-code|tsc --noEmit' docs/reactjs_frontend.md` exits 0

#### Manual
- [x] `grep -q 'openapi-typescript\|Orval\|Kubb' docs/reactjs_frontend.md` exits 0 (alternatives present)
- [x] `grep -q 'no Pydantic\|missing Pydantic\|no Pydantic response\|no.*response models' docs/reactjs_frontend.md` exits 0 (backend gap callout present)

---

## Phase 4: Testing (Q4)

Fill section 3: Vitest 4.1 + React Testing Library + MSW, jsdom/happy-dom environment, setup files,
coverage, one-line browser-mode mention.

### Changes

#### 1. Replace the section-3 stub with full content
**File**: `docs/reactjs_frontend.md`
**Action**: modify

Suggested H3 subsections:

- `### Vitest Configuration` — `**Vite-native runner.**` Vitest 4.1.x reuses the Vite config,
  transformers, and plugins. Put the `test` block in `vite.config.ts` (or a `vitest.config.ts` that
  fully overrides unless merged via `mergeConfig` from `vitest/config`).

  ```ts
  // vite.config.ts (test block)
  /// <reference types="vitest/config" />
  export default defineConfig({
    // ...plugins, server...
    test: {
      environment: 'jsdom',   // or faster 'happy-dom' (install separately)
      globals: true,          // Jest-style globals + RTL auto-cleanup
      setupFiles: './src/test/setup.ts',
    },
  });
  ```

  Note `globals: true` also requires adding `"vitest/globals"` to tsconfig `types`. Link:
  `([Vitest config](https://vitest.dev/config/))`.

- `### Setup File (RTL + MSW)` — `**Shared setup.**`

  ```ts
  // src/test/setup.ts
  import '@testing-library/jest-dom/vitest';
  import { afterAll, afterEach, beforeAll } from 'vitest';
  import { setupServer } from 'msw/node';
  import { handlers } from './handlers';

  export const server = setupServer(...handlers);

  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
  ```

  Versions inline: Vitest 4.1.x, React Testing Library 16.3.x (React 19 support since v16.1;
  `@testing-library/dom` is now a peer dep — install explicitly), `@testing-library/user-event` 14.x
  (`userEvent.setup()`, all methods async), `@testing-library/jest-dom` 6.9.x, MSW 2.14.x (v2 API
  `http.get(...)` + `HttpResponse.json(...)`; `server.use()` for per-test overrides). Links:
  `([MSW docs](https://mswjs.io/docs/))`.

- `### Coverage` — `**v8 provider.**` `@vitest/coverage-v8` (default; AST remapping ≈ Istanbul
  accuracy since Vitest 3.2) or `@vitest/coverage-istanbul`. Configure under `test.coverage` with
  `provider`, `reporter`, and `thresholds` (`lines`/`functions`/`branches`/`statements`, `perFile`).

- One-line browser-mode mention: Browser Mode is stable since Vitest 4.0 (real browsers via
  `@vitest/browser-playwright`, `vitest-browser-react` renderer) for the rare cases jsdom can't cover.

- `### Anti-patterns to Avoid` — bullets: testing implementation details instead of user-visible
  behavior; not resetting MSW handlers between tests (`server.resetHandlers()` in `afterEach`);
  overusing `data-testid` instead of accessible role/text queries.

### Verification
#### Automated
- [x] `grep -q 'Vitest 4' docs/reactjs_frontend.md` exits 0
- [x] `grep -qi 'msw' docs/reactjs_frontend.md` exits 0
- [x] `grep -qE 'jest-dom/vitest|setupServer' docs/reactjs_frontend.md` exits 0
- [x] `grep -qE 'jsdom|happy-dom' docs/reactjs_frontend.md` exits 0

#### Manual
- [x] `grep -q 'onUnhandledRequest' docs/reactjs_frontend.md` exits 0 (MSW strict-mode shown)
- [x] `grep -qi 'coverage-v8\|@vitest/coverage' docs/reactjs_frontend.md` exits 0

---

## Phase 5: Data & State Management (Q5)

Fill section 4: the server-state vs client-state principle, TanStack Query v5 (server), Zustand
(client), React Hook Form + Zod (forms), error/loading patterns.

### Changes

#### 1. Replace the section-4 stub with full content
**File**: `docs/reactjs_frontend.md`
**Action**: modify

Suggested H3 subsections:

- `### Server State vs Client State` — `**Two kinds of state.**` State the core 2026 principle:
  separate **server state** (remote-owned, stale-able → cache/refetch/invalidate) from **client state**
  (browser-owned UI state). Storing API responses in Redux/Zustand is an anti-pattern. Link:
  `([server-vs-client guide](https://nextfuture.io.vn/blog/react-server-state-vs-client-state-guide))`.

- `### Server State — TanStack Query` — `**TanStack Query v5.**` `@tanstack/react-query` 5.101.
  Array query keys drive cache separation; `staleTime` default 0, `gcTime` default 5 min.

  ```ts
  import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

  function useTodos() {
    return useQuery({ queryKey: ['todos'], queryFn: fetchTodos });
  }

  function useAddTodo() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: createTodo,
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['todos'] }),
    });
  }
  ```

  Loading/error: mutually-exclusive `isPending`/`isError`/`isSuccess` plus separate `fetchStatus`;
  `useSuspenseQuery` delegates to `<Suspense>` + Error Boundaries. Alternatives (one line): SWR
  (~4 kb, Vercel), RTK Query (bundled in `@reduxjs/toolkit` 2.12). Link:
  `([TanStack Query v5](https://tanstack.com/query/v5/docs/framework/react/overview))`.

- `### Client State — Zustand` — `**Zustand.**` Zustand 5.0.x (~3 kb) is the leading choice for UI state.

  ```ts
  import { create } from 'zustand';

  interface UiStore {
    sidebarOpen: boolean;
    toggleSidebar: () => void;
  }

  export const useUiStore = create<UiStore>((set) => ({
    sidebarOpen: false,
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  }));
  ```

  Alternatives (one line): Jotai 2.20.x (atomic), Redux Toolkit 2.12 (large/established apps),
  React Context for low-frequency tree-scoped state (theme/locale) — more than ~5 providers is a smell.

- `### Forms — React Hook Form + Zod` — `**RHF + Zod.**` React Hook Form 7.79 (uncontrolled/ref-based)
  + Zod 4.x via `@hookform/resolvers` 5.x.

  ```ts
  import { useForm } from 'react-hook-form';
  import { zodResolver } from '@hookform/resolvers/zod';
  import { z } from 'zod';

  const schema = z.object({ email: z.string().email() });
  type FormValues = z.infer<typeof schema>;

  function SignupForm() {
    const { register, handleSubmit, formState } = useForm<FormValues>({
      resolver: zodResolver(schema),
    });
    // ...
  }
  ```

  Note: pin majors, not fragile patches — `@hookform/resolvers` × Zod v4 compatibility was under
  active work; **verify at scaffold time.** TanStack Form 1.33 is an emerging headless alternative.

- `### Anti-patterns to Avoid` — bullets: storing server responses in Zustand/Redux instead of a query
  cache; more than ~5 nested Context providers; manual `useState` + `useEffect` fetching instead of a
  query library (loses caching/dedup/retry).

### Verification
#### Automated
- [x] `grep -q 'TanStack Query\|@tanstack/react-query' docs/reactjs_frontend.md` exits 0
- [x] `grep -qi 'zustand' docs/reactjs_frontend.md` exits 0
- [x] `grep -qE 'zodResolver|react-hook-form' docs/reactjs_frontend.md` exits 0
- [x] `grep -qi 'server state' docs/reactjs_frontend.md` exits 0

#### Manual
- [x] `grep -q 'invalidateQueries' docs/reactjs_frontend.md` exits 0 (mutation pattern shown)
- [x] `grep -q 'verify at scaffold time' docs/reactjs_frontend.md` exits 0 (open-risk note present)

---

## Phase 6: Code Quality & Tooling + CI & Delivery (Q6) — sections 5 & 6

Fill the final two sections. Section 5: ESLint v10 flat config + Prettier 3.8 + `tsc --noEmit`,
npm scripts, explicit mapping to the repo's `just check` gates. Section 6: CI jobs (lint/typecheck/
test parallel, build gated), `npm ci`, pre-commit (husky + lint-staged).

### Changes

#### 1. Replace the section-5 stub (`## Code Quality & Tooling`)
**File**: `docs/reactjs_frontend.md`
**Action**: modify

Suggested H3 subsections:

- `### npm Scripts` — `**The de-facto runner.**` `npm run` is the de-facto task runner (no universal
  `just` analog).

  ```json
  // package.json (scripts)
  {
    "scripts": {
      "dev": "vite",
      "build": "tsc --noEmit && vite build",
      "preview": "vite preview",
      "typecheck": "tsc --noEmit",
      "lint": "eslint .",
      "format": "prettier --write .",
      "format:check": "prettier --check .",
      "test": "vitest run"
    }
  }
  ```

- `### Lint & Format` — `**ESLint flat config.**` ESLint v10 (2026-02-06, flat-config-only;
  v9 EOL 2026-08-06) + typescript-eslint v8 + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`.

  ```js
  // eslint.config.js
  import js from '@eslint/js';
  import tseslint from 'typescript-eslint';
  import reactHooks from 'eslint-plugin-react-hooks';
  import reactRefresh from 'eslint-plugin-react-refresh';

  export default tseslint.config(
    js.configs.recommended,
    tseslint.configs.recommended,
    reactHooks.configs['recommended-latest'],
    reactRefresh.configs.vite,
  );
  ```

  Prettier 3.8 is the formatter; add `eslint-config-prettier` to disable conflicting ESLint rules.
  `tsc --noEmit` is a **separate gate** — Vite/esbuild/Oxc strip types without checking. One line:
  Rust alternatives Biome v2.4 (lint+format one binary) and Oxlint v1.x (lint-only, 50–100× faster).
  Links: `([typescript-eslint](https://typescript-eslint.io))`, `([Biome](https://biomejs.dev))`.

- `### Mapping to `just check`` — `**Same gate shape.**` Map JS/TS gates to the repo's Python gates
  (the repo runs one aggregate `just check` = `check-format check-lint check-complexity check-typecheck
  test audit`). Present as a Markdown table:

  ```markdown
  | Repo gate (`just`)        | Python tool            | JS/TS analog        |
  | ------------------------- | ---------------------- | ------------------- |
  | `check-format`            | `ruff format --check`  | `prettier --check`  |
  | `check-lint`              | `ruff check`           | `eslint .`          |
  | `check-complexity`        | `ruff check -C901`     | ESLint `complexity` |
  | `check-typecheck`         | `mypy`                 | `tsc --noEmit`      |
  | `test`                    | `pytest -n nproc`      | `vitest run`        |
  | `audit`                   | `pip-audit`            | `npm audit`         |
  ```

  Note: Ruff = combined lint+format (one tool) ↔ Biome on the JS side; the classic ESLint+Prettier
  split maps to two Python tools. The lint-vs-typecheck split is structurally identical in both
  ecosystems (whole-program analysis can't be per-file).

- `### Anti-patterns to Avoid` (section 5) — bullets: relying on `vite build` to catch type errors
  (it strips types); ESLint and Prettier rule conflicts (fix with `eslint-config-prettier`);
  committing without running the lint/typecheck gates.

#### 2. Replace the section-6 stub (`## CI & Delivery`)
**File**: `docs/reactjs_frontend.md`
**Action**: modify

Suggested H3 subsections:

- `### Deterministic Installs` — `**npm ci.**` Use `npm ci` (not `npm install`) in CI for
  reproducible installs from `package-lock.json`.

- `### Parallel CI Jobs` — `**Lint/typecheck/test in parallel, build gated.**`

  ```yaml
  # .gitlab-ci.yml (illustrative — parallel checks, build gated by needs:)
  lint:      { stage: test, script: ["npm ci", "npm run lint"] }
  typecheck: { stage: test, script: ["npm ci", "npm run typecheck"] }
  test:      { stage: test, script: ["npm ci", "npm run test"] }
  build:
    stage: build
    needs: ["lint", "typecheck", "test"]
    script: ["npm ci", "npm run build"]
  ```

  (Mirror the repo's existing single-`just check` CI shape conceptually; GitHub Actions is equivalent
  with `needs:`.)

- `### Pre-commit Hooks` — `**husky + lint-staged.**` husky v9 + lint-staged v15 run per-file
  ESLint/Prettier on staged files; `tsc --noEmit` can't be staged-scoped, so it runs whole-project in
  CI (or as a pre-push hook). Alternatives one line: simple-git-hooks, Lefthook.

  ```json
  // package.json (lint-staged)
  {
    "lint-staged": {
      "*.{ts,tsx}": ["eslint --fix", "prettier --write"]
    }
  }
  ```

- `### Anti-patterns to Avoid` (section 6) — bullets: non-deterministic `npm install` in CI (use
  `npm ci`); running `build` before lint/typecheck/test pass (gate it with `needs:`); trying to
  staged-scope `tsc --noEmit` (it's whole-program — run it project-wide).

### Verification
#### Automated
- [x] `grep -qE 'eslint.config.js|flat config' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'tsc --noEmit' docs/reactjs_frontend.md` exits 0
- [x] `grep -q 'npm audit' docs/reactjs_frontend.md` exits 0
- [x] `grep -qE 'just check|check-format|check-typecheck' docs/reactjs_frontend.md` exits 0
- [x] `grep -qiE 'npm ci|lint-staged|husky' docs/reactjs_frontend.md` exits 0

#### Manual
- [x] `grep -q 'needs:' docs/reactjs_frontend.md` exits 0 (build gating shown)
- [x] `grep -q 'eslint-config-prettier' docs/reactjs_frontend.md` exits 0 (conflict-avoidance noted)

---

## Phase 7: Final Editorial Pass

Verify whole-document conformance to house style and length; fix any drifted versions; ensure each
H3 body opens with a bolded concept name (per `fastapi_backend.md` style).

### Changes

#### 1. Whole-file editorial review
**File**: `docs/reactjs_frontend.md`
**Action**: modify (only as needed to fix style/length/version issues found below)

- Confirm every H3 body's first sentence starts with a bolded concept name (`**...**`).
- Confirm versions are consistent throughout: Vite 8.x, React 19, Vitest 4.1.x, RTL 16.3.x,
  MSW 2.14.x, TanStack Query 5.101, Zustand 5.0.x, RHF 7.79, Zod 4.x, ESLint v10, typescript-eslint v8,
  Prettier 3.8, husky v9, lint-staged v15.
- Confirm no `file:line` citation style leaked into the prose.
- Confirm length is in the target band (~450–550 lines; hard band 400–600). If over, trim
  alternatives prose to one line each; if under, expand the thinnest section's prose (do not pad).

### Verification
#### Automated
- [x] `grep -c '^## ' docs/reactjs_frontend.md` returns `6`
- [x] `grep -c '^### Anti-patterns to Avoid' docs/reactjs_frontend.md` returns `6`
- [x] `grep -c '^---$' docs/reactjs_frontend.md` returns `5`
- [x] `grep -c '^```' docs/reactjs_frontend.md` returns an **even** number (no unclosed fenced blocks) — returns 32

#### Manual
- [x] `wc -l docs/reactjs_frontend.md` reports a line count between 400 and 600 (target 450–550) — returns 479
- [x] `grep -nE '\.(ts|tsx|py):[0-9]+' docs/reactjs_frontend.md` returns nothing (no `file:line` citations leaked)
- [x] Fallback used (no network/npx): fenced-block count is 32 (even ✓); `grep -c '^#' docs/reactjs_frontend.md` returns 38 (headings well-formed ✓)
- [x] Each H3 opens with a bold marker: verified via `grep -A2 '^### ' | paste - - -` — all 24 non-Anti-patterns H3s open with `**...**`; Anti-patterns H3s open with bullet lists (correct)

---

## Resolved Assumptions

- **Context-paragraph cross-link target**: the skeleton links to `[fastapi_backend.md](fastapi_backend.md)`
  in addition to the mandatory `[overview.md](overview.md)` on line 3, because the API-sync section depends
  on the backend's `/openapi.json` and the design calls for a coherent fullstack story. `fastapi_backend.md`
  itself links to `containerization.md` the same way, so this matches house style.
- **Flag naming**: `--fullstack` is the primary flag and `--reactjs` the alias, mirroring the backend doc's
  `--backend`/`--fastapi` phrasing. Both appear in structure.md and design.md.
- **No `overview.md` index row added** — design.md "What We're NOT Doing" explicitly defers it. Flagged as a
  trivial follow-up, not done here.
- **Patch versions left unpinned where research flagged churn** (SWR major 2.x; `@hookform/resolvers` × Zod v4)
  — phrased as "verify at scaffold time" per design decision 6.
- **CI snippet uses GitLab CI shape** (the repo's existing CI is `.gitlab-ci.yml`), with a one-line note that
  GitHub Actions is equivalent via `needs:`.
