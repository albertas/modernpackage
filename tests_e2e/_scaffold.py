"""Shared infrastructure for the backend-only end-to-end test.

Mirrors the proven scaffold/compose/http helpers in `tests/test_e2e.py`
(design decision 2). Kept as a sibling module so the test imports it cleanly
under pytest's default "prepend" import mode (the test dir is on `sys.path`).
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from modernpackage import main
from modernpackage.main import normalize_module_name

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')

_GIT_IDENTITY_ENV: dict[str, str] = {
    'GIT_AUTHOR_NAME': 'e2e',
    'GIT_AUTHOR_EMAIL': 'e2e@example.com',
    'GIT_COMMITTER_NAME': 'e2e',
    'GIT_COMMITTER_EMAIL': 'e2e@example.com',
}


def _run(
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


_COMPOSE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ('docker', 'compose'),
    ('podman', 'compose'),
    ('podman-compose',),
)


def _detect_compose_command() -> list[str] | None:
    """Return the first working compose command, or None if none is available."""
    for candidate in _COMPOSE_CANDIDATES:
        try:
            probe = subprocess.run(  # noqa: S603
                [*candidate, 'version'],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if probe.returncode == 0:
            return list(candidate)
    return None


def _http_get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    """GET `url` via stdlib urllib; return `(status_code, body)`.

    Returns HTTP error statuses (4xx/5xx) rather than raising, so callers can
    assert on them; only a connection-level failure propagates.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')


def _wait_for_ready(url: str, timeout: float = 120.0) -> None:
    """Poll `url` until it returns HTTP 200 or `timeout` seconds elapse.

    Backend-agnostic replacement for docker-compose's `up --wait` (design
    decision 1): podman compose rejects `--wait` (research Q3). The stack builds
    images and runs migrations on first `up`, so use a generous monotonic
    deadline with a short sleep between polls. `_http_get` re-raises
    connection-level failures (the port refuses connections before the app
    binds), so wrap each poll in `try/except (URLError, OSError)` and retry.
    Raises `RuntimeError` on timeout with the last status/body.
    """
    deadline = time.monotonic() + timeout
    last_detail = 'no response received'
    while time.monotonic() < deadline:
        try:
            status, body = _http_get(url, timeout=5.0)
        except (urllib.error.URLError, OSError) as error:
            last_detail = f'connection error: {error}'
        else:
            if status == 200:
                return
            last_detail = f'status {status}: {body}'
        time.sleep(2.0)
    raise RuntimeError(f'{url} not ready after {timeout}s ({last_detail})')


_HOST_DATABASE_URL: str = 'postgresql+asyncpg://appuser:secret@localhost:5432/appdb'


def _expose_db_port(destination: Path) -> None:
    """Publish the generated `db` service's port 5432 to the host.

    Edits the ephemeral `tmp_path` compose copy only (design decision 3) so the
    shipped host-side `just makemigration`/`just migrate` can reach the same
    Postgres the app uses. The shipped `db` service has no `ports:` mapping
    (compose.yml:23-36); this inserts one under the `db:` key.

    DEVIATION (Phase 2): the plan's anchor `  db:` + newline is NOT unique — it
    also matches the tail of the 6-space-indented `depends_on: db:` entries, so a
    `replace(..., 1)` would corrupt the first `depends_on` block. Use the
    service-level `  db:` + `    image:` anchor instead (unique in the shipped
    file).
    """
    compose_path = destination / 'compose.yml'
    text = compose_path.read_text()
    anchor = '  db:\n    image:'
    assert anchor in text, 'compose.yml `db:` service block not found'
    ports_block = '  db:\n    ports:\n      - "127.0.0.1:5432:5432"\n    image:'
    compose_path.write_text(text.replace(anchor, ports_block, 1))


_PRODUCT_MODEL_SOURCE: str = '''

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Product(Base):
    """E2E fixture model — exercises autogenerate + migrate against real Postgres."""

    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
'''


def _register_product_model(source_dir: Path) -> None:
    """Append the `Product` model to the generated `module/db.py`.

    `env.py` imports `Base` from this module for `target_metadata`, so appending
    the model here lands `products` in `Base.metadata` for autogenerate
    (design decision 5).
    """
    db_path = source_dir / 'db.py'
    db_path.write_text(db_path.read_text() + _PRODUCT_MODEL_SOURCE)


def scaffold_backend_package(tmp_path: Path) -> tuple[Path, str]:
    """Scaffold a backend-only package into `tmp_path`; return (destination, module).

    Reproduces the proven backend-only flow (research Q2; `tests/test_e2e.py`
    `test_scaffolded_backend_package_passes_check`): clone the committed local
    checkout, write metadata, strip scaffolding, inject the backend via
    `_add_backend`, stage with `git add -A`, then `just init` to rename the
    `modernpackage` token and make the initial commit.
    """
    package_name = 'backend-run.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e backend package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    main._add_backend(destination)  # noqa: SLF001
    stage = _run(['git', 'add', '-A'], cwd=destination)
    assert stage.returncode == 0, f'git add failed:\n{stage.stderr}'

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    return destination, module_name


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


_PRODUCTS_ROUTER_SOURCE: str = '''"""Products router — injected by the e2e test."""

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
    products_import = f'from {module_name}.products import router as products_router'
    app_text = app_text.replace(
        import_anchor,
        f'{import_anchor}\n{products_import}',
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


def scaffold_fullstack_package(tmp_path: Path) -> tuple[Path, str]:
    """Scaffold a fullstack package into `tmp_path`; return (destination, module).

    Reproduces the fullstack flow (`tests/test_e2e.py`): clone the local
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
