"""Shared infrastructure for the backend-only end-to-end test.

Mirrors the proven scaffold/compose/http helpers in `tests/test_e2e.py`
(design decision 2). Kept as a sibling module so the test imports it cleanly
under pytest's default "prepend" import mode (the test dir is on `sys.path`).
"""

import os
import subprocess
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
