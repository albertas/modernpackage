# Implementation Plan

## Overview

Add a single new e2e test, `tests_e2e/test_fullstack_feature_e2e.py`, that scaffolds a
fullstack package, injects a `Product` feature (model + `/api/products` endpoints +
products-list page), brings up the real compose stack, creates a row via host-side
`POST`, reads it back via host-side `GET`, and asserts the seeded name renders in the
browser via Playwright. All injection/HTTP/scaffold helpers extend the existing
`tests_e2e/_scaffold.py`; existing helpers are reused unchanged.

**Conventions (apply to all phases):**
- All work is additive to two files: `tests_e2e/_scaffold.py` (helpers) and
  `tests_e2e/test_fullstack_feature_e2e.py` (new test). No template/`main.py` changes.
- Run scaffold + file-level assertions **before** `_detect_compose_command()` so the
  cheap file-shape checks execute everywhere (then `pytest.skip` at the compose gate),
  mirroring `test_backend_e2e.py:27`→`:41`.
- `_run(check=False)` everywhere; skip-not-fail discipline; teardown `compose down -v`
  in a `try/finally`.
- Verification command for the test: `just test-e2e tests_e2e/test_fullstack_feature_e2e.py`
  (expands to `uv run pytest -m e2e --no-cov tests_e2e/test_fullstack_feature_e2e.py`,
  `Justfile:17-18`). On a host without compose/node it must SKIP, never FAIL.

---

## Phase 1: Fullstack scaffold helper

Add `scaffold_fullstack_package` to `_scaffold.py` plus the frontend page-registration
helper, and a minimal test skeleton proving the scaffold lands all three layers (db +
backend + frontend) with the `modernpackage` token fully renamed.

### Changes

#### 1. Frontend source constants
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (append constants; place near the other source constants)

These are written into the clone **before** `just init`, so the `App.tsx` heading keeps
the literal `modernpackage` token (init's sed renames it; `status.spec.ts` then still
passes). `_APP_TSX_SOURCE` is assigned verbatim (NOT `.format`), so its literal `{...}`
JSX braces are safe.

```python
_APP_TSX_SOURCE: str = """import { useEffect, useState } from 'react';

type AppHealth = 'checking' | 'healthy' | 'unhealthy' | 'unavailable';
type DbHealth = 'checking' | 'ready' | 'not ready' | 'unavailable';

async function fetchStatus(path: string): Promise<'pass' | 'fail' | 'unavailable'> {
  try {
    const response = await fetch(path);
    const body = (await response.json()) as { status?: string };
    if (response.ok && body.status === 'pass') {
      return 'pass';
    }
    return 'fail';
  } catch {
    return 'unavailable';
  }
}

interface Product {
  id: number;
  name: string;
}

export function App() {
  const [appHealth, setAppHealth] = useState<AppHealth>('checking');
  const [dbHealth, setDbHealth] = useState<DbHealth>('checking');
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    void fetchStatus('/livez').then((result) => {
      setAppHealth(
        result === 'pass' ? 'healthy' : result === 'fail' ? 'unhealthy' : 'unavailable',
      );
    });
    void fetchStatus('/readyz').then((result) => {
      setDbHealth(
        result === 'pass' ? 'ready' : result === 'fail' ? 'not ready' : 'unavailable',
      );
    });
    void fetch('/api/products')
      .then((response) => response.json() as Promise<Product[]>)
      .then((rows) => setProducts(rows))
      .catch(() => setProducts([]));
  }, []);

  return (
    <main>
      <h1>modernpackage</h1>
      <dl>
        <dt>Application</dt>
        <dd>{appHealth}</dd>
        <dt>Database</dt>
        <dd>{dbHealth}</dd>
      </dl>
      <ul>
        {products.map((product) => (
          <li key={product.id}>{product.name}</li>
        ))}
      </ul>
    </main>
  );
}
"""


_PRODUCTS_SPEC_SOURCE: str = """import { expect, test } from '@playwright/test';

test('products page shows the seeded product', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('E2E Widget')).toBeVisible();
});
"""
```

#### 2. `_register_products_page` helper
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (append function)

Overwrites the shipped `App.tsx` and adds the products spec. Called inside the scaffold
flow **before** `git add -A` + `just init`, so both files are staged and the `App.tsx`
heading token is renamed consistently (research Q6).

```python
def _register_products_page(destination: Path) -> None:
    """Overwrite `frontend/src/App.tsx` and add the products Playwright spec.

    Runs before `just init` so the staged files are token-renamed (the `App.tsx`
    heading keeps the literal `modernpackage` token for init's sed). The new
    `App.tsx` preserves the heading + health `<dl>` (so `status.spec.ts` still
    passes) and adds a `<ul>` fetched from `/api/products` (design decision 7).
    """
    frontend_dir = destination / 'frontend'
    (frontend_dir / 'src' / 'App.tsx').write_text(_APP_TSX_SOURCE)
    (frontend_dir / 'e2e' / 'products.spec.ts').write_text(_PRODUCTS_SPEC_SOURCE)
```

#### 3. `scaffold_fullstack_package` helper
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (append function)

Mirrors the proven fullstack flow (`tests/test_e2e.py:447-470`): clone → metadata →
strip → `_inject_templates(fullstack=True)` → register page → stage → `just init`.
The extra `git add -A` re-stages the `App.tsx` overwrite and new spec (note
`_inject_templates` already staged the template files, `main.py:992`).

```python
def scaffold_fullstack_package(tmp_path: Path) -> tuple[Path, str]:
    """Scaffold a fullstack package into `tmp_path`; return (destination, module).

    Reproduces the fullstack flow (`tests/test_e2e.py:447-470`): clone the local
    checkout, write metadata, strip scaffolding, inject backend + frontend
    templates, register the products page, stage with `git add -A`, then
    `just init` to rename the `modernpackage` token and make the initial commit.
    """
    package_name = 'fullstack-feature.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e fullstack package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    main._inject_templates(destination, fullstack=True)  # noqa: SLF001
    _register_products_page(destination)

    stage = _run(['git', 'add', '-A'], cwd=destination)
    assert stage.returncode == 0, f'git add failed:\n{stage.stderr}'

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    return destination, module_name
```

#### 4. New test file with Phase-1 skeleton
**File**: `tests_e2e/test_fullstack_feature_e2e.py`
**Action**: create

```python
"""Fullstack feature end-to-end test: scaffold, inject products, round-trip."""

import os
import shutil
from pathlib import Path

import pytest

from _scaffold import (
    REQUIRED_TOOLS,
    _HOST_DATABASE_URL,
    _detect_compose_command,
    _expose_db_port,
    _http_get,
    _http_post_json,
    _register_products_feature,
    _run,
    scaffold_fullstack_package,
)

_REQUIRED_RUNTIME_TOOLS: tuple[str, ...] = (*REQUIRED_TOOLS, 'npm')
_SEED_PRODUCT_NAME: str = 'E2E Widget'


@pytest.mark.e2e
def test_fullstack_feature_runs_end_to_end(tmp_path: Path) -> None:
    for tool in _REQUIRED_RUNTIME_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    destination, module_name = scaffold_fullstack_package(tmp_path)
    source_dir = destination / module_name

    # Phase 1 file-shape checks run before the compose gate (agent-runnable
    # everywhere; mirrors test_backend_e2e.py:30-39).
    assert (source_dir / 'app.py').exists()
    assert (destination / 'frontend' / 'src' / 'App.tsx').exists()
    assert (destination / 'frontend' / 'playwright.config.ts').exists()
    assert 'frontend-test-e2e:' in (destination / 'Justfile').read_text()
    for source in source_dir.glob('*.py'):
        assert 'modernpackage' not in source.read_text()

    # (Phase 2 inserts _register_products_feature + compose gate + backend round
    #  trip here; Phase 3 inserts the frontend build + Playwright run.)
```

> Note: imports `_http_post_json` and `_register_products_feature` are added in Phase 2
> but are listed in the import block here for clarity; if implementing strictly phase by
> phase, add those two names to the import in Phase 2.

### Verification
#### Automated
- [ ] `just check` passes (format + lint + complexity + typecheck + non-e2e test; e2e is
  excluded by `-m 'not e2e'`, `pyproject.toml:40`).
- [ ] `just lint` reports no errors for the two changed files.

#### Manual
- [ ] `just test-e2e tests_e2e/test_fullstack_feature_e2e.py` →
  exit 0 with the test PASSED (compose present) or SKIPPED at the compose gate
  (compose absent); never FAILED. Confirm with:
  `just test-e2e tests_e2e/test_fullstack_feature_e2e.py 2>&1 | grep -Eq '1 (passed|skipped)'`
- [ ] After a scaffold run (or by inspecting a manual scaffold), the renamed package has
  `frontend/src/App.tsx`, `frontend/playwright.config.ts`, `app.py`, `db.py`, and a
  `Justfile` containing `frontend-test-e2e:`; no `*.py` under the source dir contains
  `modernpackage`.

---

## Phase 2: Backend products feature (model → migration → API → host HTTP)

> DEVIATION (Phase 2 implementer): Phase 1 was marked done in `progress.yml` but its
> deliverables were absent from the tree (no `scaffold_fullstack_package`,
> `_register_products_page`, or `tests_e2e/test_fullstack_feature_e2e.py`; Phase 1's
> recorded metrics were all-zero, indicating the work never landed). Because Phase 2 is
> purely additive to Phase 1's files, I reconstructed the Phase 1 foundation verbatim
> from this plan (Phase 1 §§1-4) before applying Phase 2 on top.

Inject the `Product` model, a `products.py` router mounted at `/api`, wire it into
`app.py`, run the migration host-side, then `POST` a product and `GET` it back over HTTP.

### Changes

#### 1. Products router source constant
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (append constant)

Written **after** `just init`, so it references the renamed module via
`.format(module=module_name)` and contains no literal `modernpackage` token (design
decision 4). The source has no other `{...}` braces, so `.format` is safe. Uses
`DbSessionDep` (`db.py:60`) and the `Product` model appended to `db.py`.

```python
_PRODUCTS_ROUTER_SOURCE: str = '''"""Products feature router — injected by the e2e test (not shipped)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from {module}.db import DbSessionDep, Product

router = APIRouter()


class ProductIn(BaseModel):
    name: str


class ProductOut(BaseModel):
    id: int
    name: str


@router.get('/products')
async def list_products(session: DbSessionDep) -> list[ProductOut]:
    result = await session.execute(select(Product))
    return [ProductOut(id=row.id, name=row.name) for row in result.scalars()]


@router.post('/products')
async def create_product(payload: ProductIn, session: DbSessionDep) -> ProductOut:
    product = Product(name=payload.name)
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return ProductOut(id=product.id, name=product.name)
'''
```

#### 2. `_register_products_feature` helper
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (append function)

Reuses `_register_product_model` (already in `_scaffold.py:121`) for the model, writes
`products.py`, then wires the router into `app.py` with assert-before-replace anchors
(design Open Risks). The import line carries the renamed module token after `just init`,
so the anchor is built with `module_name`.

```python
def _register_products_feature(destination: Path, module_name: str) -> None:
    """Inject the products feature into an already-initialized package.

    Appends the `Product` model to `db.py`, writes `products.py` (router with
    GET/POST `/products`), and wires the router into `app.py` under prefix `/api`.
    Runs AFTER `just init`, so all source references the renamed module
    (design decision 4); asserts each anchor before replacing (Open Risks).
    """
    source_dir = destination / module_name
    _register_product_model(source_dir)

    products_path = source_dir / 'products.py'
    products_path.write_text(_PRODUCTS_ROUTER_SOURCE.format(module=module_name))

    app_path = source_dir / 'app.py'
    app_text = app_path.read_text()

    import_anchor = f'from {module_name}.health import router as health_router'
    assert import_anchor in app_text, 'app.py health import anchor not found'
    app_text = app_text.replace(
        import_anchor,
        f'{import_anchor}\nfrom {module_name}.products import router as products_router',
        1,
    )

    include_anchor = '    app.include_router(health_router)'
    assert include_anchor in app_text, 'app.py health include anchor not found'
    app_text = app_text.replace(
        include_anchor,
        f"{include_anchor}\n    app.include_router(products_router, prefix='/api')",
        1,
    )

    app_path.write_text(app_text)
```

#### 3. `_http_post_json` helper
**File**: `tests_e2e/_scaffold.py`
**Action**: modify (add `import json` to the import block; append function near `_http_get`)

Mirrors `_http_get` (`_scaffold.py:67-77`): returns `(status, body)` and surfaces HTTP
error statuses instead of raising.

```python
import json  # add to the existing stdlib import block at the top


def _http_post_json(
    url: str,
    payload: dict[str, object],
    timeout: float = 30.0,
) -> tuple[int, str]:
    """POST `payload` as JSON to `url`; return `(status_code, body)`.

    Mirrors `_http_get`: returns HTTP error statuses (4xx/5xx) rather than
    raising, so callers can assert on them (design decision 6).
    """
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')
```

#### 4. Extend the test body
**File**: `tests_e2e/test_fullstack_feature_e2e.py`
**Action**: modify (replace the Phase-2/3 placeholder comment)

Insert after the Phase-1 file assertions. `_register_products_feature` runs before the
compose gate so the image bakes in the model + endpoints (design decision 9).

```python
    # Inject the products feature; source references the renamed module, so this
    # runs after `just init` (inside scaffold_fullstack_package).
    _register_products_feature(destination, module_name)

    compose = _detect_compose_command()
    if compose is None:
        pytest.skip('no compose command available (docker/podman compose)')

    _expose_db_port(destination)

    try:
        up = _run([*compose, 'up', '-d', '--wait', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'

        livez_status, livez_body = _http_get('http://127.0.0.1:8000/livez')
        assert livez_status == 200, f'/livez returned {livez_status}: {livez_body}'
        assert 'pass' in livez_body, f'/livez body unexpected: {livez_body}'

        readyz_status, readyz_body = _http_get('http://127.0.0.1:8000/readyz')
        assert readyz_status == 200, f'/readyz returned {readyz_status}: {readyz_body}'

        # Run the products migration host-side (env.py:29 hard-requires DATABASE_URL;
        # recipes do not set it). POST must run only after migrate (Open Risks).
        migration_env = os.environ | {'DATABASE_URL': _HOST_DATABASE_URL}
        make = _run(
            ['just', 'makemigration', 'add products'],
            cwd=destination,
            env=migration_env,
        )
        assert make.returncode == 0, (
            f'just makemigration failed:\n{make.stdout}\n{make.stderr}'
        )
        migrate = _run(['just', 'migrate'], cwd=destination, env=migration_env)
        assert migrate.returncode == 0, (
            f'just migrate failed:\n{migrate.stdout}\n{migrate.stderr}'
        )

        versions = destination / 'migrations' / 'versions'
        version_texts = [path.read_text() for path in versions.glob('*.py')]
        assert any("create_table('products')" in text for text in version_texts), (
            f'no version file contains create_table(products):\n{version_texts}'
        )

        # Create a row via host-side POST, then read it back via host-side GET.
        post_status, post_body = _http_post_json(
            'http://127.0.0.1:8000/api/products',
            {'name': _SEED_PRODUCT_NAME},
        )
        assert post_status in (200, 201), (
            f'POST /api/products returned {post_status}: {post_body}'
        )
        assert _SEED_PRODUCT_NAME in post_body, f'POST body missing name: {post_body}'

        get_status, get_body = _http_get('http://127.0.0.1:8000/api/products')
        assert get_status == 200, f'GET /api/products returned {get_status}: {get_body}'
        assert _SEED_PRODUCT_NAME in get_body, f'GET body missing name: {get_body}'

        # (Phase 3 inserts the frontend build + Playwright run here.)
    finally:
        _run([*compose, 'down', '-v'], cwd=destination)
```

### Verification
#### Automated
- [x] `just check` passes (lint/format/typecheck of the changed helpers + non-e2e test).
  format/lint/complexity/typecheck + all 146 non-e2e tests pass. NOTE: the final
  `audit` step fails on a pre-existing `pydantic-settings 2.14.1` CVE
  (GHSA-4xgf-cpjx-pc3j) in the locked deps — unrelated to this change (no dependency
  files touched); ruff was also run directly on both changed files (`tests_e2e/*` is
  outside `just check`'s lint scope of `modernpackage tests`) and passes.

#### Manual
- [ ] With compose available:
  `just test-e2e tests_e2e/test_fullstack_feature_e2e.py 2>&1 | grep -Eq '1 (passed|skipped)'`
  → exit 0. The test asserts: `POST http://127.0.0.1:8000/api/products` with
  `{"name": "E2E Widget"}` returns 200/201 and the body contains `E2E Widget`;
  `GET http://127.0.0.1:8000/api/products` returns 200 and the body contains
  `E2E Widget`; some `migrations/versions/*.py` contains `create_table('products')`;
  `/livez` and `/readyz` return 200.
  NOT VERIFIABLE ON THIS HOST: the only compose provider here is `podman-compose`,
  which does not support the `--wait` flag (`podman compose up -d --wait --build`
  exits 2). The test reaches the compose gate and faithfully mirrors the existing
  pattern (`test_backend_e2e.py:51`, `tests/test_e2e.py:476` use the identical
  `--wait` invocation) — so every pre-existing live e2e test hits the same wall on
  this host. The live round-trip needs a `--wait`-capable compose (docker compose
  or podman backed by docker-compose).
- [x] Anchor sanity (no live stack needed): after a manual fullstack scaffold +
  `_register_products_feature`, confirm wiring landed:
  `grep -q "app.include_router(products_router, prefix='/api')" <pkg>/<module>/app.py`
  and `grep -q "import router as products_router" <pkg>/<module>/app.py`.
  Verified via a local scaffold probe: IMPORT_OK, INCLUDE_OK, products.py written,
  `Product` model appended to db.py, App.tsx + products.spec.ts present, and no
  `modernpackage` token remains in any `*.py` source.

---

## Phase 3: Frontend products page + Playwright read-through

The frontend `App.tsx` and `products.spec.ts` were already written in Phase 1 (so they
are token-renamed by `just init`). This phase only extends the test to run the frontend
build + Playwright spec, completing the browser-level read-through.

### Changes

#### 1. Extend the test body (frontend round-trip)
**File**: `tests_e2e/test_fullstack_feature_e2e.py`
**Action**: modify (replace the Phase-3 placeholder comment, before the `finally`)

Mirrors `tests/test_e2e.py:490-548`: install → generate-client → build → assert dist →
Playwright with the install-failure skip guard. The seeded row from Phase 2 persists
(DB stays up), so the browser reads it through the `vite preview` proxy → live backend.

```python
        install = _run(['just', 'frontend-install'], cwd=destination)
        assert install.returncode == 0, (
            f'just frontend-install failed:\n{install.stdout}\n{install.stderr}'
        )

        # generate-client reads the LIVE openapi (now including products) — backend
        # must be up (Open Risks: keep Pydantic models well-formed).
        generate = _run(['just', 'generate-client'], cwd=destination)
        assert generate.returncode == 0, (
            f'just generate-client failed:\n{generate.stdout}\n{generate.stderr}'
        )
        client_dir = destination / 'frontend' / 'src' / 'client'
        client_text = '\n'.join(
            path.read_text() for path in client_dir.rglob('*') if path.is_file()
        )
        assert 'products' in client_text, (
            f'regenerated client missing products operations:\n{client_text}'
        )

        build = _run(['just', 'frontend-build'], cwd=destination)
        assert build.returncode == 0, (
            f'just frontend-build failed:\n{build.stdout}\n{build.stderr}'
        )
        assert (destination / 'frontend' / 'dist' / 'index.html').is_file(), (
            'frontend/dist/index.html missing'
        )

        # Browser read-through: vite preview (:4173) proxies /api → live backend
        # (:8000). products.spec.ts asserts the seeded name is visible; status.spec.ts
        # still passes (heading + health preserved). Treat a Playwright browser-install
        # failure as "browsers unavailable" and skip (design Open Risks).
        e2e_run = _run(['just', 'frontend-test-e2e'], cwd=destination)
        if e2e_run.returncode != 0 and 'playwright install' in (
            e2e_run.stdout + e2e_run.stderr
        ):
            pytest.skip(
                'playwright browser install unavailable:\n'
                f'{e2e_run.stdout}\n{e2e_run.stderr}'
            )
        assert e2e_run.returncode == 0, (
            f'just frontend-test-e2e failed:\n{e2e_run.stdout}\n{e2e_run.stderr}'
        )
```

> If `just generate-client` fails or is unavailable in the target environment, the
> `assert generate.returncode == 0` will fail loudly (this is intentional — a broken
> openapi from malformed Pydantic models is a real regression). There is no codegen
> fallback to hand-edit, because the generated client is ephemeral (research Q4) and the
> test only depends on it via the `'products'` substring check and a successful build.

### Verification
#### Automated
- [x] `just check` passes. format/lint/complexity/typecheck + all 146 non-e2e tests
  pass. NOTE (same as Phase 2): the final `audit` step fails on a pre-existing
  `pydantic-settings 2.14.1` CVE (GHSA-4xgf-cpjx-pc3j) in the locked deps — unrelated
  to this change (no dependency files touched). `tests_e2e/*` is outside `just check`'s
  lint scope (`modernpackage tests`); ruff was run directly on the changed file and
  passes after adding `# noqa: PLR0915` (the Phase-3 additions pushed the function to
  53 statements > 50; DEVIATION from plan — the codebase's targeted-noqa convention was
  followed rather than touching pyproject config, keeping changes within the test file).

#### Manual
- [ ] With compose + Node + browsers available:
  `just test-e2e tests_e2e/test_fullstack_feature_e2e.py 2>&1 | grep -Eq '1 (passed|skipped)'`
  → exit 0, full round trip PASSED. The `products.spec.ts` assertion confirms
  `E2E Widget` is visible in the rendered DOM; `status.spec.ts` confirms the health
  `<dl>` still renders (heading renamed + healthy + ready).
  NOT VERIFIABLE ON THIS HOST: same wall as Phase 2 — the only compose provider here is
  `podman-compose`, which does not support `--wait` (`podman compose up -d --wait
  --build` exits 2). The run fails at the Phase-2 `compose up` step (line 54), before
  any Phase-3 code executes, so the frontend build + Playwright path cannot be live-run
  here. Phase-3 wiring verified statically (see below).
- [ ] Without browsers (but with compose + Node): the run reaches
  `just frontend-test-e2e`, hits the `playwright install` guard, and SKIPS — confirm
  the run does not FAIL.
  NOT VERIFIABLE ON THIS HOST: blocked at the same `compose up --wait` step before
  reaching `frontend-test-e2e`. The skip-guard string match is sound: the
  `frontend-test-e2e` recipe (`main.py:611-612`) runs `npx playwright install`, so a
  browser-install failure surfaces `playwright install` in stdout/stderr, which the
  guard checks.
- [ ] `frontend/dist/index.html` exists after the build step (asserted in-test).
  NOT VERIFIABLE ON THIS HOST: requires the live stack (blocked at `compose up --wait`).
  Statically confirmed Phase-3 dependencies exist: `frontend-install`,
  `generate-client`, `frontend-build`, `frontend-test-e2e` recipes
  (`main.py:596,608,599,611`), `frontend_template/playwright.config.ts`, and
  `_register_products_page` writes `frontend/e2e/products.spec.ts` (`_scaffold.py:308`).

---

## Testing Checkpoints (from structure.md)

- [ ] **After Phase 1**: `scaffold_fullstack_package` produces a renamed package with
  backend (`app.py`, `db.py`), frontend (`App.tsx`, `playwright.config.ts`), and frontend
  recipes in the `Justfile`; no `modernpackage` token remains in `*.py`. Cheap file
  assertions pass even without compose.
- [ ] **After Phase 2**: with compose up, `POST /api/products` creates `E2E Widget` and
  `GET /api/products` reads it back (both 200, body contains the name); a migration
  version file contains `create_table('products')`; `/livez` + `/readyz` stay 200.
  (Live-stack assertions not verifiable on this host — only `podman-compose` is
  available and it lacks `--wait`; see the Phase 2 manual note. Code/anchor wiring
  verified statically.)
- [ ] **After Phase 3**: the full round trip passes — `E2E Widget` is visible in the
  browser DOM via Playwright; `status.spec.ts` still passes; `generate-client`/
  `frontend-build` succeed. Missing compose/node/browsers → `pytest.skip`, never fail.
  (Live round trip not verifiable on this host — only `podman-compose` is available and
  it lacks `--wait`, blocking the run at the Phase-2 `compose up` step before Phase-3
  code runs. Phase-3 test code lints/typechecks clean and its recipe/file dependencies
  are statically confirmed present.)

## Assumptions / Resolutions

- **`_register_products_feature` runs before the compose gate** (not after) so the
  image build bakes in the model + endpoints (design decision 9). It only edits files,
  so it is harmless when compose is absent.
- **`app.py` import wiring**: the structure outline names only the include-line anchor.
  Wiring the router also requires an `import` line, so the helper adds two
  assert-before-replace edits (import after the health import; include after the health
  include). Both anchors are unique in the shipped `app.py:12,33`.
- **POST success codes**: FastAPI returns 200 by default for the `POST` handler (no
  explicit `status_code`), but the assertion accepts `200` or `201` to stay robust.
- **Client assertion**: a single stable-substring check (`'products' in client_text`)
  is used, consistent with the existing fullstack test's substring approach
  (`test_e2e.py:511-516`); no exact-structure assertions.
- **Imports added across phases**: `_http_post_json` and `_register_products_feature`
  are imported in the test file in Phase 2; `json` is added to `_scaffold.py` imports in
  Phase 2.
```
