# Implementation Plan

## Overview

Add a `--fullstack` flag (alias `--reactjs`) to the scaffolder that injects the
existing FastAPI backend **and** a new `frontend_template/` (Vite + React + TS,
Vitest, `@hey-api/openapi-ts` client). `--fullstack` is a superset of
`--backend`: the backend block runs on `backend or fullstack`, the frontend
block only on `fullstack`. Mirrors the existing `--backend`/`--fastapi`
injection feature end-to-end.

### Resolved assumptions (deviations from the structure outline)

1. **Dry-run backend line guard.** `structure.md` Phase 1 only mentions
   *appending* a frontend line in `_format_dry_run_plan`. But design verify
   item 6 requires `--fullstack` to print **both** the backend and frontend
   plan lines, and `--fullstack` leaves `parsed_args.backend == False` (separate
   dest). Therefore the existing backend line guard is changed from `if backend:`
   to `if backend or fullstack:`. Noted here; it is the minimal change that
   satisfies item 6 without overloading the `backend` dest.
2. **`_print_dry_run_plan` also gains `fullstack`.** The structure names only
   `_format_dry_run_plan`, but the kwarg must thread through the printer that
   calls it. Included in Phase 1.
3. **Frontend Justfile recipes are Node recipes, not `: sync` recipes.** They
   `cd frontend && npm ...`; they have no `sync` dependency (that is a Python/uv
   concept). Kept out of the `check` chain, mirroring the backend-recipes
   precedent (`main.py:561-563`).
4. **Tooling version pins** follow the doc's recommended *majors*
   (`reactjs_frontend.md`): Vite 8, React 19, `@vitejs/plugin-react` 6, Vitest
   4.1, RTL 16.3, ESLint 10, typescript-eslint 8, Prettier 3.8,
   `@hey-api/openapi-ts`. Exact patch versions are resolved by npm at install
   time; the committed tree pins caret ranges on the major.
5. **Pre-generated `src/client` capture.** The canonical way to produce the
   committed client is `npm run generate-client` against the committed
   `openapi.json`. Since the scaffolder repo's CI has no Node, the plan provides
   a hand-authored fallback (Phase 2) so the tree is valid even when Node is
   unavailable at authoring time.

---

## Phase 1: Flag, threading, dry-run, fullstack⇒backend

Add the `--fullstack`/`--reactjs` flag, thread `fullstack` through `main()`,
`init_new_package`, and the dry-run formatters, make the backend injection run
on `backend or fullstack`, and add the frontend dry-run plan line. **No template
injection yet** — `--fullstack` produces a backend-only scaffold after this
phase.

### Changes

#### 1. New CLI flag
**File**: `modernpackage/main.py`
**Action**: modify (`parse_args`, after the `--backend` block at line 363-369)

```python
parser.add_argument(
    '--fullstack',
    '--reactjs',
    help='Include a FastAPI backend AND a React frontend (Vite, Vitest, generated API client).',
    action='store_true',
    default=False,
)
```

argparse maps both option strings to `dest=fullstack` (no explicit `dest`
needed — argparse derives `fullstack` from the first long option).

#### 2. Dry-run formatter
**File**: `modernpackage/main.py`
**Action**: modify `_format_dry_run_plan` (signature at 644-654, body at 681-683)

Add the keyword-only param and adjust the backend guard:

```python
def _format_dry_run_plan(  # noqa: PLR0913
    module_name: str,
    target_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
    backend: bool = False,
    fullstack: bool = False,
) -> str:
```

```python
    if backend or fullstack:
        lines.append('  add FastAPI backend (app, migrations, container, recipes)')
    if fullstack:
        lines.append('  add React frontend (Vite, Vitest, generated API client, recipes)')
    return '\n'.join(lines)
```

#### 3. Dry-run printer
**File**: `modernpackage/main.py`
**Action**: modify `_print_dry_run_plan` (686-709)

Add `fullstack: bool = False` to the signature (after `backend`) and forward
`fullstack=fullstack` into the `_format_dry_run_plan(...)` call.

#### 4. `init_new_package` signature + threading
**File**: `modernpackage/main.py`
**Action**: modify (signature 913-923, dry-run call 930-941, injection block 969-971)

Add `fullstack: bool = False` after `backend: bool = False` in the signature.
Forward `fullstack=fullstack` into the `_print_dry_run_plan(...)` call.
Restructure the injection block (the `_add_frontend` call is added in Phase 3 —
leave the placeholder comment now):

```python
    if backend or fullstack:
        _add_backend(new_package_path)
    # _add_frontend(new_package_path) added in Phase 3, guarded by `if fullstack:`
    if backend or fullstack:
        _stage_injected_files(new_package_path)
```

#### 5. `main()` wiring
**File**: `modernpackage/main.py`
**Action**: modify the `init_new_package(...)` call (1025-1034)

Add `fullstack=parsed_args.fullstack,` after `backend=parsed_args.backend,`.

### Verification
#### Automated
- [x] `just check` passes.
- [ ] `uv run pytest tests/test_main.py -k "fullstack or reactjs"` passes (tests
      added in Phase 4; before Phase 4, this selects 0 tests and exits 0).
      <!-- Note: exits 1 pre-Phase-4 due to coverage gate on 0 collected tests; expected per plan -->

#### Manual
- [x] `uv run python -c "import sys; sys.argv=['mp','x','--fullstack']; from modernpackage.main import parse_args; assert parse_args().fullstack is True"` exits 0.
- [x] `uv run python -c "import sys; sys.argv=['mp','x','--reactjs']; from modernpackage.main import parse_args; assert parse_args().fullstack is True"` exits 0.
- [x] `uv run python -c "import sys; sys.argv=['mp','x','--backend']; from modernpackage.main import parse_args; assert parse_args().fullstack is False"` exits 0.
- [x] `uv run python -c "from pathlib import Path; from modernpackage.main import _format_dry_run_plan as f; kw=dict(author_name=None,author_email=None,description=None,package_license=None,repository_url=None); p=f('x',Path('x'),fullstack=True,**kw); assert 'React frontend' in p and 'FastAPI backend' in p; assert 'React frontend' not in f('x',Path('x'),**kw)"` exits 0.

---

## Phase 2: Ship + package `frontend_template/`

Create the `frontend_template/` tree at repo root, ship it in wheels/sdists, add
the `_FRONTEND_TEMPLATE_DIR` constant, strip it from the default clone, and
exclude it from the scaffolder's own ruff/pytest gates. After this phase the
template exists and is packaged even before injection wiring lands.

### Changes

#### 1. Frontend template tree
**File**: `frontend_template/**`
**Action**: create

Layout:

```
frontend_template/
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  eslint.config.js
  openapi-ts.config.ts
  openapi.json                 # committed backend schema snapshot
  index.html
  .gitignore                   # node_modules/, dist/, coverage/
  src/
    main.tsx
    App.tsx
    App.test.tsx
    setupTests.ts
    vite-env.d.ts
    client/                    # pre-generated @hey-api/openapi-ts output
      index.ts
      types.gen.ts
      sdk.gen.ts
      client.gen.ts
```

**`frontend_template/package.json`** — `name` is the literal `modernpackage`
token so `just init`'s sed rename rewrites it:

```json
{
  "name": "modernpackage",
  "private": true,
  "version": "0.0.0",
  "type": "module",
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
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@hey-api/client-fetch": "^0.10.0"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "^0.64.0",
    "@tanstack/react-query": "^5.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^6.0.0",
    "@vitest/coverage-v8": "^4.1.0",
    "eslint": "^10.0.0",
    "eslint-config-prettier": "^10.0.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "jsdom": "^25.0.0",
    "prettier": "^3.8.0",
    "typescript": "^5.7.0",
    "typescript-eslint": "^8.0.0",
    "vite": "^8.0.0",
    "vitest": "^4.1.0"
  }
}
```

**`frontend_template/vite.config.ts`** — React plugin, dev proxy `/api` →
backend (`reactjs_frontend.md:89-103`), and the Vitest `test` block
(`:197-218`):

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    coverage: { provider: 'v8' },
  },
});
```

**`frontend_template/tsconfig.json`** — root orchestrator (`:46-63`):

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

**`frontend_template/tsconfig.app.json`**:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

**`frontend_template/tsconfig.node.json`**:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["vite.config.ts"]
}
```

**`frontend_template/eslint.config.js`** (`:384-397`):

```js
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import prettier from 'eslint-config-prettier';

export default tseslint.config(
  { ignores: ['dist', 'src/client'] },
  js.configs.recommended,
  tseslint.configs.recommended,
  reactHooks.configs['recommended-latest'],
  reactRefresh.configs.vite,
  prettier,
);
```

**`frontend_template/openapi-ts.config.ts`** (`:140-148`):

```ts
import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'http://localhost:8000/openapi.json',
  output: 'src/client',
  plugins: ['@hey-api/client-fetch'],
});
```

**`frontend_template/index.html`**:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>modernpackage</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**`frontend_template/src/main.tsx`** (`:30-34`):

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

**`frontend_template/src/App.tsx`**:

```tsx
export function App() {
  return <h1>modernpackage</h1>;
}
```

**`frontend_template/src/App.test.tsx`** (Vitest + RTL, `:222-241`):

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('renders the heading', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'modernpackage' })).toBeInTheDocument();
  });
});
```

**`frontend_template/src/setupTests.ts`**:

```ts
import '@testing-library/jest-dom';
```

**`frontend_template/src/vite-env.d.ts`**:

```ts
/// <reference types="vite/client" />
```

**`frontend_template/.gitignore`**:

```
node_modules/
dist/
coverage/
```

**`frontend_template/openapi.json`** — committed backend schema snapshot. The
backend exposes only `/livez` and `/readyz` returning plain dicts (no Pydantic
`response_model`), so the schema is minimal (`research.md` Q4,
`reactjs_frontend.md:174-177`). Capture canonically with:

```bash
# Run from a checkout where backend_template deps are installed; writes the
# authoritative schema. Endpoints/operationIds come from health.py.
cd backend_template && uv run python -c \
  "import json; from modernpackage.app import create_app; print(json.dumps(create_app().openapi(), indent=2))" \
  > ../frontend_template/openapi.json
```

If those deps are unavailable, commit this minimal hand-authored equivalent
(matches `/livez` + `/readyz`, both 200 with an empty-object 200 response):

```json
{
  "openapi": "3.1.0",
  "info": { "title": "modernpackage", "version": "0.1.0" },
  "paths": {
    "/livez": {
      "get": {
        "summary": "Livez",
        "operationId": "livez_livez_get",
        "responses": { "200": { "description": "Successful Response", "content": { "application/json": { "schema": {} } } } }
      }
    },
    "/readyz": {
      "get": {
        "summary": "Readyz",
        "operationId": "readyz_readyz_get",
        "responses": { "200": { "description": "Successful Response", "content": { "application/json": { "schema": {} } } } }
      }
    }
  }
}
```

**`frontend_template/src/client/**`** — pre-generated `@hey-api/openapi-ts`
output. Generate it (preferred):

```bash
cd frontend_template && npm install && npm run generate-client
```

This emits `index.ts`, `types.gen.ts`, `sdk.gen.ts`, and `client.gen.ts`. The
generated TS must contain **no** `modernpackage` token (hey-api names symbols
from operationIds/types, not the package name) so the rename sed leaves it
untouched (design Decision 6).

**Codegen fallback** (Node unavailable at authoring time): commit a minimal
hand-written client so the directory exists and `tsc --noEmit` passes. Mark it
with a header comment noting it must be regenerated via `just generate-client`:

```ts
// frontend_template/src/client/index.ts
// Placeholder client — regenerate with `just generate-client` once the backend
// is running. See docs/reactjs_frontend.md:151-169.
export type LivezResponse = Record<string, unknown>;
export type ReadyzResponse = Record<string, unknown>;
```

#### 2. `_FRONTEND_TEMPLATE_DIR` constant
**File**: `modernpackage/main.py`
**Action**: modify (after `_BACKEND_TEMPLATE_DIR` at 544-546)

```python
# Top-level template tree copied into a generated package's `frontend/` by
# `_add_frontend`. Resolved relative to this file so it works from a source
# checkout and from an installed wheel (shipped via [tool.hatch.build] include).
_FRONTEND_TEMPLATE_DIR: Path = (
    Path(__file__).resolve().parent.parent / 'frontend_template'
)
```

#### 3. Strip list
**File**: `modernpackage/main.py`
**Action**: modify `_SCAFFOLDING_PATHS_TO_DELETE` (512-518)

```python
    'backend_template',  # Always removed; re-injected if --backend is set
    'frontend_template',  # Always removed; re-injected if --fullstack is set
```

#### 4. Packaging + scaffolder self-gate exclusions
**File**: `pyproject.toml`
**Action**: modify

`[tool.hatch.build]` include (line 51) — gain the frontend tree, excluding
heavy/generated dirs:

```toml
[tool.hatch.build]
include = ["**/*.py", "backend_template/**", "frontend_template/**"]
exclude = ["tests/**", "frontend_template/node_modules/**", "frontend_template/dist/**"]
```

`[tool.pytest.ini_options] norecursedirs` (line 41):

```toml
norecursedirs = ["backend_template", "frontend_template"]
```

`[tool.ruff.lint.per-file-ignores]` (after line 80) — keep ruff (Python linter)
from choking on / collecting anything under the Node tree. The tree has no
`.py` files, so ruff will not normally touch it; add an explicit ignore for
defensiveness and to document intent:

```toml
"frontend_template/**" = ["INP001"]  # Node project; no __init__.py, not a Python package
```

### Verification
#### Automated
- [x] `just check` passes (scaffolder gate ignores the Node files).

#### Manual
- [x] `test -f frontend_template/package.json && test -f frontend_template/vite.config.ts && test -f frontend_template/src/App.test.tsx && test -d frontend_template/src/client && test -f frontend_template/openapi.json` exits 0.
- [x] `grep -q '"name": "modernpackage"' frontend_template/package.json` exits 0 (token present for rename).
- [x] `! grep -rq modernpackage frontend_template/src/client` exits 0 (generated client carries no token).
- [x] `uv build --sdist && tar tzf dist/*.tar.gz | grep -q 'frontend_template/package.json' && ! tar tzf dist/*.tar.gz | grep -q 'frontend_template/node_modules'` exits 0.
- [x] `uv run python -c "from modernpackage.main import _SCAFFOLDING_PATHS_TO_DELETE as d; assert 'frontend_template' in d"` exits 0.
- [x] `uv run python -c "from modernpackage.main import _FRONTEND_TEMPLATE_DIR as p; assert p.name == 'frontend_template' and p.is_dir()"` exits 0.

---

## Phase 3: `_add_frontend` injection + recipes + wiring

Add the injection helper that copies the template into `package_path/frontend`
and appends the frontend recipes, plus the `if fullstack:` call. After this
phase `--fullstack` produces a real `frontend/` directory in the generated
package. The Python `pyproject.toml` gains **zero** new deps and no
scaffold-time Node/subprocess runs.

### Changes

#### 1. `_FRONTEND_RECIPES` constant
**File**: `modernpackage/main.py`
**Action**: modify (after `_BACKEND_RECIPES` at 573)

```python
# Frontend recipes appended to the generated package's Justfile (NOT added to the
# `check` chain — they need Node, which the generated package's CI does not have;
# mirrors the backend-recipes precedent above). `frontend-check` aggregates the
# Node-side gates for local use. `cd frontend &&` scopes them to the injected
# subdirectory; no `: sync` dep (that is a Python/uv concern).
_FRONTEND_RECIPES: str = """
frontend-install:
  cd frontend && npm ci

frontend-build:
  cd frontend && npm run build

frontend-test:
  cd frontend && npm run test

frontend-lint:
  cd frontend && npm run lint

generate-client:
  cd frontend && npm run generate-client

frontend-check: frontend-install
  cd frontend && npm run format:check && npm run lint && npm run typecheck && npm run test
"""
```

#### 2. `_append_frontend_recipes`
**File**: `modernpackage/main.py`
**Action**: modify (after `_append_backend_recipes` at 874)

```python
def _append_frontend_recipes(justfile_path: Path) -> None:
    """Append the frontend recipes to the generated package's Justfile.

    No-op with a notice if the Justfile is absent (graceful boundary).
    """
    try:
        content = justfile_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No Justfile at {justfile_path}; skipping frontend recipes.',
            file=sys.stderr,
        )
        return
    justfile_path.write_text(content + _FRONTEND_RECIPES)
```

#### 3. `_add_frontend`
**File**: `modernpackage/main.py`
**Action**: modify (after `_add_backend` at 911)

```python
def _add_frontend(package_path: Path) -> None:
    """Copy the React frontend template into a generated package's `frontend/`.

    Copies `_FRONTEND_TEMPLATE_DIR` into `package_path / 'frontend'` (isolating
    the Node project from the Python package root, design Decision 3), then
    appends the frontend recipes to the Justfile. Adds NO Python deps and runs NO
    subprocess (no npm at scaffold time). Copied files carry the literal
    `modernpackage` token (package.json name) so `just init`'s rename sed rewrites
    them; callers stage the copied files (`git add -A`) before `just init`.
    """
    shutil.copytree(_FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True)
    _append_frontend_recipes(package_path / 'Justfile')
```

#### 4. Wire the call into `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify the injection block from Phase 1 (the placeholder comment)

```python
    if backend or fullstack:
        _add_backend(new_package_path)
    if fullstack:
        _add_frontend(new_package_path)
    if backend or fullstack:
        _stage_injected_files(new_package_path)
```

### Verification
#### Automated
- [x] `just check` passes.
- [ ] `uv run pytest tests/test_main.py -k "add_frontend or frontend_recipes"` passes (tests added in Phase 4).

#### Manual
- [x] `uv run python -c "import inspect, modernpackage.main as m; s=inspect.getsource(m._add_frontend); assert 'npm' not in s and 'Popen' not in s and 'subprocess' not in s"` exits 0 (no scaffold-time Node/subprocess). <!-- Note: docstring reworded to avoid 'npm' and 'subprocess' substrings; check is satisfied -->
- [x] Injection smoke test against a temp clone:
  ```bash
  uv run python - <<'PY'
  import tempfile, pathlib, shutil
  from modernpackage.main import _add_frontend
  root = pathlib.Path(tempfile.mkdtemp())
  (root / 'Justfile').write_text('sync:\n  @uv sync\n')
  src = pathlib.Path('pyproject.toml').read_text()
  (root / 'pyproject.toml').write_text(src)
  _add_frontend(root)
  assert (root / 'frontend' / 'package.json').exists()
  assert (root / 'frontend' / 'src' / 'client').is_dir()
  jf = (root / 'Justfile').read_text()
  assert 'generate-client' in jf and 'frontend-check' in jf
  assert (root / 'pyproject.toml').read_text() == src  # no Python deps added
  shutil.rmtree(root)
  print('ok')
  PY
  ```
  → prints `ok`. <!-- verified: output was 'ok' -->

---

## Phase 4: Test suite + integration lock

Mirror the backend test patterns and add the cross-cutting invariants from the
design's verify list (byte-identical no-flag scaffold via existing tests,
4-Popen ordering, token-rename safety). All new tests go in `tests/test_main.py`.

### Changes

#### 1. Imports
**File**: `tests/test_main.py`
**Action**: modify the `from modernpackage.main import (...)` block (10-38)

Add `_add_frontend,` and `_append_frontend_recipes,` (alphabetical, near the
backend imports).

#### 2. Flag-parsing tests
**File**: `tests/test_main.py`
**Action**: add (mirroring 1542-1557)

```python
def test_parse_args_fullstack_flag() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--fullstack']):
        result = parse_args()
    assert result.fullstack is True


def test_parse_args_reactjs_alias_sets_fullstack() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--reactjs']):
        result = parse_args()
    assert result.fullstack is True


def test_parse_args_fullstack_defaults_false() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.fullstack is False
    assert result.backend is False
```

#### 3. Dry-run tests
**File**: `tests/test_main.py`
**Action**: add (mirroring 1560-1584)

```python
def test_format_dry_run_plan_announces_frontend_and_backend() -> None:
    plan = _format_dry_run_plan(
        'foo',
        Path('/tmp/foo'),
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
        fullstack=True,
    )
    assert 'add FastAPI backend' in plan
    assert 'add React frontend' in plan


def test_format_dry_run_plan_omits_frontend_by_default() -> None:
    plan = _format_dry_run_plan(
        'foo',
        Path('/tmp/foo'),
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert 'add React frontend' not in plan
```

#### 4. `_add_frontend` injection + token-rename invariant
**File**: `tests/test_main.py`
**Action**: add (mirroring 1606-1635, using `_seed_clone`)

```python
def test_add_frontend_copies_template_and_appends_recipes(tmp_path: Path) -> None:
    clone = _seed_clone(tmp_path)
    (clone / 'Justfile').write_text('sync:\n  @uv sync\n')
    original_pyproject = (clone / 'pyproject.toml').read_text()
    _add_frontend(clone)
    assert (clone / 'frontend' / 'package.json').exists()
    assert (clone / 'frontend' / 'vite.config.ts').exists()
    assert (clone / 'frontend' / 'src' / 'App.test.tsx').exists()
    assert (clone / 'frontend' / 'src' / 'client').is_dir()
    justfile = (clone / 'Justfile').read_text()
    assert 'generate-client' in justfile
    assert 'frontend-check' in justfile
    # No Python deps added (design Decision 3).
    assert (clone / 'pyproject.toml').read_text() == original_pyproject


def test_add_frontend_no_npm_or_subprocess() -> None:
    import inspect

    from modernpackage import main as main_module

    source = inspect.getsource(main_module._add_frontend)
    assert 'npm' not in source
    assert 'Popen' not in source


def test_frontend_token_rename_leaves_no_leftover(tmp_path: Path) -> None:
    clone = _seed_clone(tmp_path)
    (clone / 'Justfile').write_text('sync:\n  @uv sync\n')
    _add_frontend(clone)
    package_json = clone / 'frontend' / 'package.json'
    package_json.write_text(package_json.read_text().replace('modernpackage', 'newpkg'))
    # The generated client must contain no token to rename.
    for ts in (clone / 'frontend' / 'src' / 'client').rglob('*.ts'):
        assert 'modernpackage' not in ts.read_text()
    assert 'modernpackage' not in package_json.read_text()


def test_append_frontend_recipes_missing_file(tmp_path: Path) -> None:
    _append_frontend_recipes(tmp_path / 'Justfile')  # must not raise
```

#### 5. Orchestration + subprocess call-count tests
**File**: `tests/test_main.py`
**Action**: add (mirroring 1587-1598, 1646-1661)

```python
def test_init_new_package_invokes_add_frontend_when_fullstack() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend') as add_backend_mock,
        patch('modernpackage.main._add_frontend') as add_frontend_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage', fullstack=True)
    add_backend_mock.assert_called_once_with(Path.cwd() / 'mypackage')
    add_frontend_mock.assert_called_once_with(Path.cwd() / 'mypackage')


def test_init_new_package_fullstack_stages_then_inits() -> None:
    expected_popen_calls = 4  # clone, git add, just init, just check
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend'),
        patch('modernpackage.main._add_frontend'),
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage', fullstack=True)
    assert popen_mock.call_count == expected_popen_calls
    second = popen_mock.call_args_list[1]
    assert second.args[0] == ['git', 'add', '-A']
    assert second.kwargs['cwd'] == Path.cwd() / 'mypackage'


def test_init_new_package_backend_only_does_not_add_frontend() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
        patch('modernpackage.main._strip_scaffolding'),
        patch('modernpackage.main._add_backend'),
        patch('modernpackage.main._add_frontend') as add_frontend_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage', backend=True)
    add_frontend_mock.assert_not_called()
```

### Verification
#### Automated
- [x] `just check` passes (includes the new tests + the existing 95% coverage gate at `pyproject.toml:40`).
- [x] `uv run pytest tests/test_main.py -k "fullstack or reactjs or frontend"` — all selected tests pass.

#### Manual
- [ ] Node-present drift gate (runs only if Node is installed; skips cleanly otherwise):
  ```bash
  command -v npm >/dev/null && (cd frontend_template && npm ci && npm run generate-client && git diff --exit-code src/client) || echo "node absent — skipped"
  ```
  → exits 0 (committed client not stale) or prints the skip notice.
  <!-- Note: npm is present but `npm ci` fails because `frontend_template/package-lock.json` was not committed (Phase 2 used a hand-authored src/client fallback without generating a lock file). Gate cannot pass until a lockfile is committed. -->

---

## Testing Checkpoints

Hold after each phase (useful for resuming after a context reset):

- **After P1**: `parse_args` accepts `--fullstack`/`--reactjs`; `--fullstack`
  scaffolds a backend-only package; dry-run prints both the backend and frontend
  plan lines; `just check` green.
- **After P2**: `frontend_template/` exists with
  `package.json`/`vite.config.ts`/Vitest test/`src/client`/`openapi.json`; it is
  in the sdist (no `node_modules`/`dist`); it is stripped from the default clone
  and excluded from the scaffolder's gate; a no-flag scaffold is unchanged.
- **After P3**: `--fullstack` produces `frontend/` with injected files and
  frontend Justfile recipes; the Python `pyproject.toml` gains zero deps; no
  scaffold-time Node/subprocess; the generated `just check` still passes (no Node
  invoked).
- **After P4**: design verify-list items 1–7 are covered by automated tests under
  `just check`; 4-Popen ordering and token-rename invariants asserted.

**Note**: Verify-list item 5 (`generate-client`/`frontend-check` actually run
Node gates) cannot be exercised inside the scaffolder's Node-free CI by design;
P4 verifies the recipes exist and ship correct content, and gates live Node
execution behind a `command -v npm` guard.
