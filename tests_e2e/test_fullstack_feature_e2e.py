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
def test_fullstack_feature_runs_end_to_end(tmp_path: Path) -> None:  # noqa: PLR0915
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

        # Run the products migration host-side (env.py hard-requires DATABASE_URL;
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
    finally:
        _run([*compose, 'down', '-v'], cwd=destination)
