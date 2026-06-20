"""Backend-only end-to-end test: scaffold, run the stack, apply a migration."""

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
    _register_product_model,
    _run,
    scaffold_backend_package,
)


@pytest.mark.e2e
def test_backend_package_runs_end_to_end(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    destination, module_name = scaffold_backend_package(tmp_path)
    source_dir = destination / module_name

    # Backend layout landed and the token was fully renamed (research Q2, Q5).
    assert (source_dir / 'db.py').exists()
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()
    assert (destination / 'compose.yml').exists()
    assert (destination / 'alembic.ini').exists()
    assert (destination / 'migrations' / 'env.py').exists()
    assert 'migrate: sync' in (destination / 'Justfile').read_text()
    for source in source_dir.glob('*.py'):
        assert 'modernpackage' not in source.read_text()

    compose = _detect_compose_command()
    if compose is None:
        pytest.skip('no compose command available (docker/podman compose)')

    _expose_db_port(destination)

    # `compose.yml` lands at the package root (`destination`); `build: .` context
    # is `destination`. `--wait` blocks until the app's `/readyz` healthcheck
    # passes — proving db up + migrations applied + app ready (research Q2).
    try:
        up = _run([*compose, 'up', '-d', '--wait', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'

        livez_status, livez_body = _http_get('http://127.0.0.1:8000/livez')
        assert livez_status == 200, f'/livez returned {livez_status}: {livez_body}'
        assert 'pass' in livez_body, f'/livez body unexpected: {livez_body}'

        readyz_status, readyz_body = _http_get('http://127.0.0.1:8000/readyz')
        assert readyz_status == 200, f'/readyz returned {readyz_status}: {readyz_body}'

        # Register a real table, then drive the scaffold's own migration targets
        # host-side. The Justfile recipes don't set DATABASE_URL and `env.py:29`
        # hard-requires it, so inject the host-reachable URL (design decision 4).
        _register_product_model(source_dir)
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

        # Autogenerate emitted a version file creating the products table. Assert
        # on the substring, not exact structure (design Open Risks).
        versions = destination / 'migrations' / 'versions'
        version_texts = [
            path.read_text() for path in versions.glob('*.py')
        ]
        assert any("create_table('products')" in text for text in version_texts), (
            f'no version file contains create_table(products):\n{version_texts}'
        )

        # DB still answers `SELECT 1` after the schema changed (task core requirement).
        post_status, post_body = _http_get('http://127.0.0.1:8000/readyz')
        assert post_status == 200, f'/readyz post-migration: {post_status} {post_body}'
    finally:
        _run([*compose, 'down', '-v'], cwd=destination)
