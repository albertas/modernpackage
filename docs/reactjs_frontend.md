# modernpackage — ReactJS Frontend

[overview.md](overview.md)

When scaffolded with the `--fullstack` flag (or `--reactjs` alias), `modernpackage` will generate
a modern Vite + React 19 + TypeScript single-page application wired to the FastAPI backend's
auto-generated OpenAPI contract. This document describes the 2026 best practices that the future
generated frontend template follows — scaffolding, API-schema synchronization, testing, state
management, code quality, and CI. For the backend it pairs with, see [fastapi_backend.md](fastapi_backend.md).

## Scaffolding & Project Structure

### Scaffolding the App

**Vite create.** Start with `npm create vite@latest` to scaffold a non-interactive Vite 8.x project.
Vite 8.x (released 2026-03-12) runs on Rust-based Rolldown bundler and ships with React 19 support
via `@vitejs/plugin-react` v6 on Oxc. Requires Node 20.19+ or 22.12+.

```bash
npm create vite@latest my-app -- --template react-ts
cd my-app && npm install
```

One alternative: the `react-swc-ts` template uses SWC instead of Oxc; both are Rust-based with
negligible speed differences. Custom Babel plugins (e.g., React Compiler 1.0) require
`@rolldown/plugin-babel` added manually. See ([Vite Getting Started](https://vite.dev/guide/)).

### Generated Layout

**Project shape.** The generated layout follows the Vite standard: `index.html` at the root contains
`<div id="root"></div>` and a script tag; `src/main.tsx` calls `ReactDOM.createRoot()`; `src/App.tsx`
is the root component; `public/` and `src/assets/` hold static and bundled assets; `src/vite-env.d.ts`
contains Vite client types. The dev server runs on `:5173` by default. Scaffolding includes standard
npm scripts: `dev`, `build`, `preview`, `lint`, and `format`.

### Feature-based Folders

**Feature-based folders.** Progressive organization scales with app size: small projects use
`components/ hooks/ utils/ assets/` at the root; large projects adopt `features/<name>/{components,hooks,utils,index.ts}`
with shared code in top-level directories. The cardinal rule: **code flows from shared to features;
features must never import from each other.** Use PascalCase for component files, camelCase for hooks,
and `index.ts` for barrel exports. See ([React Folder Structure 2026](https://www.robinwieruch.de/react-folder-structure/)).

### TypeScript Config Split

**Three tsconfigs.** Vite 8 projects define a three-file TypeScript configuration:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

`tsconfig.json` is the orchestrator (no direct sources); `tsconfig.app.json` covers the browser
application in `src/`; `tsconfig.node.json` covers build tooling (`vite.config.ts`). Standard
settings: `"strict": true`, `"moduleResolution": "bundler"`, `"jsx": "react-jsx"`, `"noEmit": true`,
`"isolatedModules": true` (required by Oxc), `"noUnusedLocals"`, `"noUnusedParameters"`. Enable
path aliases via `resolve.tsconfigPaths: true` (built into Vite 8) or manual `resolve.alias` with
matching `paths` in tsconfig.

### Environment Variables

**VITE_ prefix.** Only environment variables prefixed `VITE_` reach the client via `import.meta.env`;
additionally Vite provides `MODE`, `PROD`, `DEV`, `BASE_URL`, and `SSR` (all strings). Load order:
`.env`, `.env.local`, `.env.[mode]`, `.env.[mode].local` (`.local` files are git-ignored). Augment
types in `src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

See ([Env & Mode](https://vite.dev/guide/env-and-mode)).

### Dev Server & Production Build

**Proxy and build.** Configure the dev server to proxy `/api` requests to the FastAPI backend
(default `http://localhost:8000`) so the frontend can use relative paths:

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

Running `vite build` generates `dist/` using Rolldown (old `rollupOptions` is deprecated; configure
via `build.rolldownOptions`). Dynamic `import()` calls trigger automatic code splitting. `vite preview`
serves the production build locally on `:4173`.

### Anti-patterns to Avoid

- Non-`VITE_` secrets (private keys, API tokens) placed in client code — they end up in the bundle
  and are exposed to the browser.
- Cross-feature imports between `features/<name>` directories — breaks modular separation and creates
  hard-to-trace circular dependencies.
- A single monolithic `tsconfig.json` instead of the app/node split — causes build-time type errors
  and makes it unclear which rules apply where.
- Relying on `vite build` to type-check — Oxc and esbuild strip types without validating them;
  use `tsc --noEmit` as a separate gate.

---

## API Schema Synchronization

### The Pydantic → OpenAPI → TS Chain

**One source of truth.** The contract flows `Pydantic models → OpenAPI 3.1 → TypeScript types`.
The FastAPI backend auto-serves its schema at `/openapi.json`, `/docs`, and `/redoc` with no
extra configuration (`FastAPI(lifespan=lifespan)` applies defaults). The frontend's code generator
consumes that contract to emit typed clients, so any backend schema change immediately surfaces
as a TypeScript compile error on the frontend.

### Generating the Client (Hey API)

**Hey API.** Recommend `@hey-api/openapi-ts` as the primary generator. FastAPI's own documentation
names it the recommended TypeScript generator, and the `full-stack-fastapi-template` uses it. It
emits `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, and optionally a fetch/axios/ky client.
The `@tanstack/react-query` plugin produces `queryOptions()` and `mutationOptions()` factories,
integrating seamlessly with server-state management.

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
{
  "scripts": {
    "generate-client": "openapi-ts"
  }
}
```

See ([Hey API](https://heyapi.dev/)) and ([FastAPI — Generating Clients](https://fastapi.tiangolo.com/advanced/generate-clients/)).

### Drift Enforcement in CI

**Fail on drift.** Three patterns enforce schema drift: regenerate the client and commit the diff;
verify that `git diff` finds no uncommitted changes after regeneration; or let `tsc --noEmit` surface
drift as type errors. The most common approach:

```bash
npm run generate-client
git diff --exit-code src/client
```

### Backend Contract Gap

**Callout.** The current `backend_template` defines no Pydantic `response_model`s — endpoints return
plain `dict` or `JSONResponse` — so generated TypeScript types are minimal for existing endpoints.
To unlock rich typed clients, add Pydantic response models to backend routes first. See
[fastapi_backend.md](fastapi_backend.md) for patterns.

### Anti-patterns to Avoid

- Hand-writing TypeScript interfaces that duplicate the backend schema — they drift silently and
  must be kept in sync manually.
- Generating against a stale committed `openapi.json` without a refresh step — backend changes
  won't be reflected in the client until regeneration.
- Skipping CI drift checks — silent schema mismatches cause runtime errors in production.

Terse alternatives: `openapi-typescript` + `openapi-fetch`/`openapi-react-query` (with `--check`
for CI); Orval (one hook per operation with MSW mock generators); Kubb (modular plugin architecture);
`openapi-generator-cli` (Java 11+ required).

---

## Testing

### Vitest Configuration

**Vite-native runner.** Vitest 4.1.x reuses Vite's config, transformers, and plugins, so it runs
tests identically to how the browser sees the code. Add a `test` block to `vite.config.ts` or
create a separate `vitest.config.ts` that merges configs:

```ts
/// <reference types="vitest/config" />
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',     // or faster 'happy-dom' (install separately)
      globals: true,            // Jest-style globals; auto-cleanup after each test
      setupFiles: './src/test/setup.ts',
    },
  })
);
```

With `globals: true`, also add `"vitest/globals"` to tsconfig `types`. See ([Vitest config](https://vitest.dev/config/)).

### Setup File (RTL + MSW)

**Shared setup.** A single setup file initializes React Testing Library and Mock Service Worker:

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

Versions (as of 2026): Vitest 4.1.x, React Testing Library 16.3.x (React 19 support since v16.1;
`@testing-library/dom` is now a peer dependency — install explicitly), `@testing-library/user-event` 14.x
(`userEvent.setup()` and all methods are async), `@testing-library/jest-dom` 6.9.x, MSW 2.14.x
(v2 uses `http.get(...)` + `HttpResponse.json(...)`; call `server.use()` for per-test handler overrides).
See ([MSW docs](https://mswjs.io/docs/)).

### Coverage

**v8 provider.** Use `@vitest/coverage-v8` (default; AST-based remapping is accurate since Vitest 3.2)
or `@vitest/coverage-istanbul`. Configure under `test.coverage` with `provider`, `reporter` (html/lcov/text),
and `thresholds` (set `lines`/`functions`/`branches`/`statements` and `perFile` flags).

### Browser-Mode Testing

**Real browsers.** Browser Mode (stable since Vitest 4.0) runs tests in real browsers via `@vitest/browser-playwright`
or `@vitest/browser-webdriver`. Use it when jsdom/happy-dom can't replicate browser APIs (geolocation, WebGL).

### Anti-patterns to Avoid

- Testing implementation details (component state, instance methods) instead of user-visible behavior.
- Failing to reset MSW handlers between tests — `server.resetHandlers()` in `afterEach` prevents
  test pollution.
- Overusing `data-testid` instead of accessible role and text queries — accessible queries make
  tests more resilient to refactors and reinforce accessible markup.

---

## Data & State Management

### Server State vs Client State

**Two kinds of state.** The 2026 principle: separate **server state** (remote-owned, cacheable,
potentially stale) from **client state** (browser-owned UI state). Storing API responses in Redux
or Zustand is an anti-pattern — they belong in a query cache. See ([server-vs-client guide](https://nextfuture.io.vn/blog/react-server-state-vs-client-state-guide)).

### Server State — TanStack Query

**TanStack Query v5.** `@tanstack/react-query` 5.101.x is the standard for caching and fetching.
Array query keys separate cache entries; `staleTime` defaults to 0 (immediately stale), `gcTime`
to 5 minutes (data evicts after 5 min without active subscribers).

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

Status is split into `isPending`/`isError`/`isSuccess` (mutually exclusive) plus separate `fetchStatus`
(for distinguishing stale-while-revalidate). `useSuspenseQuery` delegates to `<Suspense>` boundaries
and Error Boundaries. Alternatives: SWR (~4 kb, Vercel); RTK Query (bundled in `@reduxjs/toolkit` 2.12).
See ([TanStack Query v5](https://tanstack.com/query/v5/docs/framework/react/overview)).

### Client State — Zustand

**Zustand.** Zustand 5.0.x (~3 kb) is the leading minimalist store for UI state (sidebar open/closed,
modal visibility, theme):

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

Alternatives: Jotai 2.20.x (atomic); Redux Toolkit 2.12 (large/established apps); React Context for
low-frequency tree-scoped state (theme, locale) — more than ~5 providers signals poor separation.

### Forms — React Hook Form + Zod

**RHF + Zod.** React Hook Form 7.79.x (uncontrolled, ref-based) + Zod 4.x via `@hookform/resolvers` 5.x:

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
  // render form...
}
```

Note: pin majors, not fragile patches — `@hookform/resolvers` × Zod v4 compatibility was under
active development; **verify at scaffold time.** TanStack Form 1.33.x is an emerging headless alternative.

### Anti-patterns to Avoid

- Storing server responses in Zustand or Redux instead of letting TanStack Query cache them —
  double management and stale-data bugs.
- More than ~5 nested Context providers — a strong smell of state organization problems.
- Manual `useState` + `useEffect` fetching instead of a query library — loses caching, request deduplication,
  and automatic retry.

---

## Code Quality & Tooling

### npm Scripts

**The de-facto runner.** `npm run` is the standard task runner in the Node ecosystem (no universal
`just` analog). Standard frontend scripts:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "lint": "eslint .",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "test": "vitest run",
    "test:watch": "vitest",
    "generate-client": "openapi-ts"
  }
}
```

### Lint & Format

**ESLint flat config.** ESLint v10 (released 2026-02-06; v9 EOL 2026-08-06) is flat-config-only.
Pair with typescript-eslint v8, `eslint-plugin-react-hooks`, and `eslint-plugin-react-refresh`:

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

Prettier 3.8.x is the formatter. Add `eslint-config-prettier` to disable conflicting ESLint rules.
`tsc --noEmit` is a **separate gate** — Vite, esbuild, and Oxc strip types without validating them.
Alternatives: Rust-based Biome v2.4 (combined lint+format, one binary); Oxlint v1.x (lint-only,
50–100× faster than ESLint). See ([typescript-eslint](https://typescript-eslint.io)) and ([Biome](https://biomejs.dev)).

### Mapping to `just check`

**Same gate shape.** The repo's `just check` aggregates Python gates; map frontend gates to them:

| Repo gate (`just`) | Python tool           | JS/TS analog        |
| ------------------ | --------------------- | ------------------- |
| `check-format`     | `ruff format --check` | `prettier --check`  |
| `check-lint`       | `ruff check`          | `eslint .`          |
| `check-typecheck`  | `mypy`                | `tsc --noEmit`      |
| `test`             | `pytest -n nproc`     | `vitest run`        |
| `audit`            | `pip-audit`           | `npm audit`         |

Ruff is a combined lint+format tool (like Biome on the JS side); the classic ESLint+Prettier split
maps to two separate Python tools. The lint-vs-typecheck distinction is structurally identical in both ecosystems.

### Anti-patterns to Avoid

- Relying on `vite build` to catch type errors — it strips types without checking.
- ESLint and Prettier rule conflicts — fix with `eslint-config-prettier`.
- Committing code without running lint/typecheck gates.

---

## CI & Delivery

### Deterministic Installs

**npm ci.** Use `npm ci` (not `npm install`) in CI for reproducible installs from `package-lock.json`.

### Parallel CI Jobs

**Lint/typecheck/test in parallel, build gated.** Run checks in parallel and gate the build:

```yaml
# .gitlab-ci.yml
lint:
  stage: test
  script: ["npm ci", "npm run lint"]

typecheck:
  stage: test
  script: ["npm ci", "npm run typecheck"]

test:
  stage: test
  script: ["npm ci", "npm run test"]

build:
  stage: build
  needs: ["lint", "typecheck", "test"]
  script: ["npm ci", "npm run build"]
```

(GitHub Actions is equivalent using `needs:`.)

### Pre-commit Hooks

**husky + lint-staged.** husky v9 + lint-staged v15 run per-file ESLint and Prettier on staged files;
`tsc --noEmit` can't be staged-scoped (it's whole-program), so run it project-wide in CI or as a
pre-push hook:

```json
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"]
  }
}
```

Alternatives: simple-git-hooks, Lefthook.

### Anti-patterns to Avoid

- Non-deterministic `npm install` in CI — use `npm ci`.
- Running `build` before lint/typecheck/test pass — gate it with `needs:`.
- Trying to staged-scope `tsc --noEmit` — it's whole-program; run it project-wide.
