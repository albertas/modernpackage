# Structure Outline

## Approach

Write one Markdown file `docs/reactjs_frontend.md` (~450–550 lines) that mirrors
`docs/fastapi_backend.md`'s house style exactly: H1 + context paragraph +
`[overview.md](overview.md)` link, then **six `---`-separated H2 sections**, each
with H3 subsections and a closing `### Anti-patterns to Avoid`. Code shown via
fenced snippets (not `file:line`); tools cited with inline 2026 versions; one
vetted stack recommended, alternatives mentioned in one line.

Because the deliverable is a single document (no code layers), each "vertical
slice" is a **self-contained section that compiles into the final file and is
independently verifiable** via grep/line-count/markdown-lint probes. Phase 1
establishes the skeleton that all later sections attach to; each section phase
is independently valuable and individually checkable. The doc is built
incrementally and the same file is appended/edited per phase.

Target file: `/home/niekas/tools/modernpackage/workspace/T54-.../` work copy,
written to repo path `docs/reactjs_frontend.md`.

---

## Phase 1: Skeleton & Section Scaffold

Establish the document frame: H1, context paragraph framing the
`--fullstack`/`--reactjs` flag, `[overview.md](overview.md)` link, and the six
empty H2 headings separated by `---`, each with a placeholder
`### Anti-patterns to Avoid`. This is the structural contract every later phase
fills in.

**Files**: `docs/reactjs_frontend.md` (new)
**Key changes**:
- H1: `# modernpackage — ReactJS Frontend`
- Context paragraph (3–5 lines) + `[overview.md](overview.md)` on line 3
- Six H2 headings: `## Scaffolding & Project Structure`, `## API Schema
  Synchronization`, `## Testing`, `## Data & State Management`,
  `## Code Quality & Tooling`, `## CI & Delivery`
- Each H2 followed by `---` separator and an `### Anti-patterns to Avoid` stub

**Verify**:
- `grep -c '^## ' docs/reactjs_frontend.md` returns `6`
- `grep -c '^### Anti-patterns to Avoid' docs/reactjs_frontend.md` returns `6`
- `grep -c '^---$' docs/reactjs_frontend.md` returns `5`
- `head -3 docs/reactjs_frontend.md | grep -q 'overview.md'` (exit 0)
- `head -1 docs/reactjs_frontend.md` equals `# modernpackage — ReactJS Frontend`

---

## Phase 2: Scaffolding & Project Structure (Q1)

Fill section 1: Vite 8 + React 19 + TS scaffold command, generated layout,
feature-based folder conventions, tsconfig split, env vars, dev server/proxy,
production build. Closes with its anti-patterns.

**Files**: `docs/reactjs_frontend.md`
**Key changes** (fenced snippets):
- `npm create vite@latest my-app -- --template react-ts` (Vite 8.x, React 19,
  Node 20.19+/22.12+)
- `vite.config.ts` snippet with `server.proxy` + `resolve.tsconfigPaths`
- tsconfig triplet (`tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`)
  with `strict`, `moduleResolution: "bundler"`, `isolatedModules`
- `.env`/`VITE_`-prefix + `import.meta.env` note; `ImportMetaEnv` in `vite-env.d.ts`
- Anti-patterns: non-`VITE_` secrets in client, cross-feature imports, single
  god `tsconfig.json`

**Verify**:
- `grep -q 'react-ts' docs/reactjs_frontend.md` and `grep -q 'Vite 8' docs/reactjs_frontend.md`
- `grep -q 'tsconfig.app.json' docs/reactjs_frontend.md`
- `grep -q 'VITE_' docs/reactjs_frontend.md`
- Section 1 contains ≥1 fenced ```` ```ts ```` or ```` ```bash ```` block
  (`awk` between `## Scaffolding` and next `---`, assert ``` count ≥ 2)

---

## Phase 3: API Schema Synchronization (Q2)

Fill section 2: the OpenAPI → TS chain wired to the FastAPI backend. Recommend
Hey API as primary, connect explicitly to backend `/openapi.json`, document CI
drift enforcement, and call out the backend's missing Pydantic response models.

**Files**: `docs/reactjs_frontend.md`
**Key changes** (fenced snippets):
- `@hey-api/openapi-ts` config + `generate-client` npm script consuming
  `http://localhost:8000/openapi.json` or committed `openapi.json`
- Chain statement: `Pydantic → OpenAPI 3.1 → TS types`
- Drift enforcement: `tsc --noEmit` / `git diff --exit-code` pattern
- Callout: current `backend_template` has no Pydantic response models → thin types
- Alternatives one-liners: openapi-typescript, Orval, Kubb, openapi-generator-cli

**Verify**:
- `grep -q 'hey-api\|Hey API' docs/reactjs_frontend.md`
- `grep -q '/openapi.json' docs/reactjs_frontend.md`
- `grep -q 'Pydantic' docs/reactjs_frontend.md` (backend linkage present)
- `grep -qi 'git diff --exit-code\|tsc --noEmit' docs/reactjs_frontend.md`

---

## Phase 4: Testing (Q4)

Fill section 3: Vitest 4.1 + React Testing Library + MSW, jsdom/happy-dom
environment, setup files, coverage, one-line browser-mode mention.

**Files**: `docs/reactjs_frontend.md`
**Key changes** (fenced snippets):
- `test` block in `vite.config.ts` (`environment: 'jsdom'`, `globals`, `setupFiles`)
- Setup file: `import '@testing-library/jest-dom/vitest'` + MSW `setupServer`
  with `onUnhandledRequest: 'error'`
- Versions inline: Vitest 4.1.x, RTL 16.3.x, user-event 14.x, jest-dom 6.9.x,
  MSW 2.14.x; `@vitest/coverage-v8`
- Anti-patterns: testing implementation details, no MSW reset between tests,
  `data-testid` overuse

**Verify**:
- `grep -q 'Vitest 4' docs/reactjs_frontend.md` and `grep -qi 'msw' docs/reactjs_frontend.md`
- `grep -q 'jest-dom/vitest\|setupServer' docs/reactjs_frontend.md`
- `grep -q 'jsdom\|happy-dom' docs/reactjs_frontend.md`

---

## Phase 5: Data & State Management (Q5)

Fill section 4: server-state vs client-state principle, TanStack Query v5
(server), Zustand (client), React Hook Form + Zod (forms), error/loading
patterns.

**Files**: `docs/reactjs_frontend.md`
**Key changes** (fenced snippets):
- `useQuery`/`useMutation` + `queryClient.invalidateQueries` example
- `create()` Zustand store; `useForm` + `zodResolver` snippet
- Versions inline: TanStack Query 5.101, Zustand 5.0.x, RHF 7.79, Zod 4.x,
  `@hookform/resolvers` 5.x (note Zod v4 compat "verify at scaffold time")
- Alternatives one-liners: SWR, RTK Query, Jotai, TanStack Form
- Anti-patterns: storing server responses in Zustand/Redux, >5 Context providers

**Verify**:
- `grep -q 'TanStack Query\|@tanstack/react-query' docs/reactjs_frontend.md`
- `grep -qi 'zustand' docs/reactjs_frontend.md` and `grep -q 'zodResolver\|react-hook-form' docs/reactjs_frontend.md`
- `grep -qi 'server state' docs/reactjs_frontend.md` (core principle stated)

---

## Phase 6: Code Quality & Tooling + CI & Delivery (Q6) — sections 5 & 6

Fill the final two sections. Section 5: ESLint v10 flat config + Prettier 3.8 +
`tsc --noEmit`, npm scripts, explicit mapping to the repo's `just check` gates.
Section 6: CI jobs (lint/typecheck/test parallel, build gated), `npm ci`,
pre-commit (husky + lint-staged).

**Files**: `docs/reactjs_frontend.md`
**Key changes** (fenced snippets):
- `package.json` scripts: `dev`, `build` (`tsc --noEmit && vite build`),
  `preview`, `typecheck`, `lint` (`eslint .`), `format`, `test`
- `eslint.config.js` flat-config snippet (js.recommended, tseslint, react-hooks,
  react-refresh); ESLint v10, typescript-eslint v8, Prettier 3.8
- Gate-mapping table: `prettier --check`↔`check-format`, `eslint .`↔`check-lint`,
  `tsc --noEmit`↔`check-typecheck`, `vitest run`↔`test`, `npm audit`↔`audit`
- CI snippet (parallel jobs + `build` via `needs:`); Biome/Oxlint one-liners
- Anti-patterns: relying on Vite build to catch type errors, ESLint+Prettier
  rule conflicts (use `eslint-config-prettier`), non-deterministic `npm install`

**Verify**:
- `grep -q 'eslint.config.js\|flat config' docs/reactjs_frontend.md`
- `grep -q 'tsc --noEmit' docs/reactjs_frontend.md` and `grep -q 'npm audit' docs/reactjs_frontend.md`
- Gate-mapping present: `grep -q 'just check\|check-format\|check-typecheck' docs/reactjs_frontend.md`
- `grep -qi 'npm ci\|lint-staged\|husky' docs/reactjs_frontend.md`

---

## Phase 7: Final Editorial Pass

Verify whole-document conformance to house style and length, fix any drifted
versions, ensure each section opens with a bolded concept name (per
`fastapi_backend.md` H3 style).

**Files**: `docs/reactjs_frontend.md`
**Verify**:
- `wc -l docs/reactjs_frontend.md` in range 400–600 (target ~450–550)
- Re-run all Phase 1 structural checks (6 H2, 6 anti-pattern H3, 5 `---`)
- `npx markdownlint-cli2 docs/reactjs_frontend.md` (if available) reports no
  blocking errors; otherwise confirm no unclosed fenced blocks via
  `grep -c '^```' docs/reactjs_frontend.md` returns an **even** number
- No `file:line` citation style leaked: `grep -nE '\.(ts|tsx|py):[0-9]+' docs/reactjs_frontend.md`
  returns nothing (or only intended config-path references, manually confirmed)

---

## Testing Checkpoints

After each phase the following should hold (useful for resuming after a context
reset):

- **P1**: File exists with H1, overview link, 6 H2 headings, 5 `---`, 6
  anti-pattern stubs. Structural skeleton frozen.
- **P2**: Section 1 documents Vite 8/React 19 scaffold, tsconfig split, env, dev
  server, build — with fenced snippets.
- **P3**: Section 2 documents Hey API generation wired to `/openapi.json`, drift
  CI, and the Pydantic-models callout linking to the backend.
- **P4**: Section 3 documents Vitest 4.1 + RTL + MSW with setup snippet.
- **P5**: Section 4 documents server-vs-client state, TanStack Query, Zustand,
  RHF+Zod.
- **P6**: Sections 5 & 6 document ESLint/Prettier/tsc gates mapped to
  `just check`, npm scripts, and CI.
- **P7**: Whole-file length, structure, and style conform to
  `fastapi_backend.md`; doc is ready for a follow-up `overview.md` index row
  (not done here, per design "What We're NOT Doing").
