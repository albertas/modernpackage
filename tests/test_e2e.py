"""End-to-end scaffolding test.

Scaffolds a package from the *local committed checkout* (not the hardcoded
GitHub URL in ``modernpackage.main``) and asserts the generated package passes
``just check``.

Intentional deviations / caveats:
- Replicates the two-step ``git clone`` + ``just init`` flow against the local
  repo root rather than calling ``init_new_package`` (which clones GitHub), so a
  regression in the local template actually fails this test.
- ``git clone`` copies **committed** state only; uncommitted template edits are
  not exercised. CI tests committed refs, so it is unaffected.
- The inner ``just check`` runs a full ``uv sync`` and a networked ``pip-audit``,
  so this test takes minutes and requires network; offline runners fail at sync.
"""

import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from modernpackage import main
from modernpackage.main import normalize_module_name

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')

# Phase 2's skip guard needs the base tools plus a Node toolchain (`npm`); the
# compose command itself is detected separately via `_detect_compose_command`.
_REQUIRED_RUNTIME_TOOLS: tuple[str, ...] = (*REQUIRED_TOOLS, 'npm')

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
    """Return the first working compose command, or None if none is available.

    Probes the portability set named in `backend_template/compose.yml:1`
    (`docker compose` → `podman compose` → `podman-compose`) by running
    `<cmd> version` with `check=False`; returns the first whose returncode is 0.
    Degrades gracefully: a missing executable raises `FileNotFoundError`, which
    is treated as "not available" rather than propagated.
    """
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

    Mirrors the `Containerfile` healthcheck's use of `urllib.request`
    (`Containerfile:25`) instead of pulling in `httpx` (a backend-template dev
    dep, not guaranteed in the outer test env — design decision 5). HTTP error
    statuses (4xx/5xx) are returned, not raised, so callers can assert on them;
    only a connection-level failure propagates.
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


_RECIPE_NAME_RE = re.compile(r'^([a-z][\w-]*)(?: \w+)*:', re.MULTILINE)


def _dependency_tokens() -> set[str]:
    """Bare package names from the backend dependency constants (no version/extras)."""
    deps = main._BACKEND_DEPENDENCIES + main._BACKEND_DEV_DEPENDENCIES  # noqa: SLF001
    return {re.split(r'[<>=\[ ]', dep, maxsplit=1)[0] for dep in deps}


def _recipe_tokens() -> set[str]:
    """Recipe names declared in the backend/frontend recipe constants."""
    recipes = main._BACKEND_RECIPES + main._FRONTEND_RECIPES  # noqa: SLF001
    return set(_RECIPE_NAME_RE.findall(recipes))


@pytest.mark.e2e
def test_scaffolded_package_passes_check(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'scaffold-check.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e generated package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )

    main._strip_scaffolding(destination)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    source_dir = destination / module_name
    assert source_dir.is_dir()
    assert '-' not in module_name
    assert '.' not in module_name
    assert '_' in module_name

    init_file = source_dir / '__init__.py'
    assert init_file.exists()
    assert '0.0.1' in init_file.read_text()

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'

    pyproject = (destination / 'pyproject.toml').read_text()
    assert 'Test Author' in pyproject
    assert 'test@example.org' in pyproject
    assert 'An e2e generated package.' in pyproject
    assert 'license = "Apache-2.0"' in pyproject
    assert 'License :: OSI Approved :: MIT License' not in pyproject
    assert 'Name Surname' not in pyproject
    assert 'email@example.com' not in pyproject
    assert 'Package configuration example using bleeding edge toolset.' not in pyproject

    # Scaffolding removed from the generated package.
    assert not (source_dir / 'main.py').exists()  # self-replicating CLI gone
    assert not (destination / 'tests' / 'test_e2e.py').exists()
    assert not (destination / 'docs').exists()
    assert not (destination / 'BACKLOG.md').exists()
    assert '[project.scripts]' not in pyproject  # no dangling entry point
    assert 'modernpackage.main:main' not in pyproject
    assert not (destination / 'backend_template').exists()  # template never leaks
    # Operational/process artifacts stripped from every generated package.
    assert not (destination / 'errors').exists()  # operational artifact
    assert not (destination / 'issues').exists()
    assert not (destination / 'workspace').exists()
    assert not (destination / 'metrics.yml').exists()
    # lifecycle_state.yml is re-seeded fresh with the good-quality baseline
    # (scaffolder's own phases/semaphores dropped).
    assert (destination / 'lifecycle_state.yml').read_text() == (
        'code_quality_is_good: true\n'
    )
    # __init__.py version 0.0.1 already asserted at lines 88-90; check stub test.
    stub = (destination / 'tests' / 'test_main.py').read_text()
    assert '0.0.1' in stub


@pytest.mark.e2e
def test_just_bump_increments_patch(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    destination = tmp_path / 'bump_check'
    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    init_file = destination / 'modernpackage' / '__init__.py'
    version_re = re.compile(r"^__version__ = '(\d+)\.(\d+)\.(\d+)'$", re.MULTILINE)

    before = version_re.search(init_file.read_text())
    assert before is not None, 'starting __version__ not found'
    start_major, start_minor, start_patch = (int(part) for part in before.groups())

    bump = _run(['just', 'bump'], cwd=destination)
    assert bump.returncode == 0, f'just bump failed:\n{bump.stdout}\n{bump.stderr}'

    after = version_re.search(init_file.read_text())
    assert after is not None, 'post-bump __version__ not found'
    end_major, end_minor, end_patch = (int(part) for part in after.groups())

    assert end_patch == start_patch + 1
    assert end_major == start_major
    assert end_minor == start_minor


@pytest.mark.e2e
def test_scaffolded_backend_package_passes_check(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'backend-check.pkg'
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

    source_dir = destination / module_name
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()
    # token fully renamed in injected sources
    for source in source_dir.glob('*.py'):
        assert 'modernpackage' not in source.read_text()
    assert '/readyz' in (source_dir / 'health.py').read_text()

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'

    generated_justfile = (destination / 'Justfile').read_text()
    assert 'migrate: sync' in generated_justfile
    assert 'makemigration' in generated_justfile
    assert (destination / 'migrations' / 'env.py').exists()
    assert (destination / 'alembic.ini').exists()

    assert (destination / 'Containerfile').exists()
    assert (destination / '.dockerignore').exists()
    compose = (destination / 'compose.yml').read_text()
    assert 'service_completed_successfully' in compose
    assert 'migrate:' in compose
    containerfile = (destination / 'Containerfile').read_text()
    assert '/readyz' in containerfile


@pytest.mark.e2e
def test_scaffolded_package_has_no_backend_or_frontend(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'no-extras.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='A no-extras package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    source_dir = destination / module_name
    assert source_dir.is_dir()

    # 1. Backend/frontend directories never reach the package.
    for directory in (
        'backend_template',
        'frontend_template',
        'frontend',
        'migrations',
        'tests_e2e',
    ):
        assert not (destination / directory).exists(), f'unexpected dir: {directory}'

    # 2. Backend/container config files absent.
    for filename in ('alembic.ini', 'compose.yml', 'Containerfile', '.dockerignore'):
        assert not (destination / filename).exists(), f'unexpected file: {filename}'

    # 3. pyproject.toml carries no backend deps and keeps the empty list.
    pyproject = (destination / 'pyproject.toml').read_text()
    assert 'dependencies = []' in pyproject
    for token in _dependency_tokens():
        assert token not in pyproject, f'unexpected dependency token: {token}'

    # 4. Justfile carries no backend/frontend recipes.
    justfile = (destination / 'Justfile').read_text()
    for token in _recipe_tokens():
        assert token not in justfile, f'unexpected recipe: {token}'

    # 5. Package source dir contains no backend/frontend import tokens
    #    (scoped scan avoids incidental-substring false positives).
    import_tokens = (
        'import fastapi',
        'from fastapi',
        'import sqlalchemy',
        'from sqlalchemy',
        'import asyncpg',
        'import alembic',
        'import uvicorn',
        'from react',
        'vite',
    )
    source_text = '\n'.join(
        path.read_text() for path in source_dir.rglob('*') if path.is_file()
    )
    for token in import_tokens:
        assert token not in source_text, f'unexpected import token: {token}'


@pytest.mark.e2e
def test_scaffolded_fullstack_package_passes_check(tmp_path: Path) -> None:
    """Scaffold a fullstack package and run both backend and frontend test suites.

    Injects backend + frontend via the production path
    (`main._inject_templates(..., fullstack=True)`, which stages internally), runs
    the generated `just check` (backend pytest), then installs and runs the
    frontend Vitest suite directly.

    Caveats (inherited from sibling tests, see module docstring): the inner
    `just check` runs `uv sync` + networked `pip-audit`, and `just frontend-install`
    runs `npm ci`, which hits the network and needs a compatible Node toolchain.
    The `npm` skip guard makes Node-less environments (CI) skip rather than fail.
    """
    required_tools = (*REQUIRED_TOOLS, 'npm')
    for tool in required_tools:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'fullstack-check.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e fullstack package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    # Production fullstack injection path: backend + frontend, then `git add -A`
    # internally (no manual staging needed, unlike the backend test).
    main._inject_templates(destination, fullstack=True)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'

    # Frontend: install deps then run Vitest. `frontend-test` (vitest run) does
    # NOT depend on `frontend-install`, so install must run first (design
    # decision 3). `npm ci` hits the network and needs a compatible Node.
    install = _run(['just', 'frontend-install'], cwd=destination)
    assert install.returncode == 0, (
        f'just frontend-install failed:\n{install.stdout}\n{install.stderr}'
    )

    # Run `frontend-test` directly (vitest run) — NOT `frontend-check`, which
    # also runs format/lint/typecheck (out of scope; design "Do NOT follow").
    frontend_test = _run(['just', 'frontend-test'], cwd=destination)
    assert frontend_test.returncode == 0, (
        f'just frontend-test failed:\n{frontend_test.stdout}\n{frontend_test.stderr}'
    )
    # Confirm Vitest actually executed (not a silent no-op). Vitest prints a
    # "Test Files" summary line to stdout/stderr on every run.
    combined_output = frontend_test.stdout + frontend_test.stderr
    assert 'Test Files' in combined_output, (
        f'Vitest did not appear to run:\n{frontend_test.stdout}\n{frontend_test.stderr}'
    )

    # Backend sources present.
    source_dir = destination / module_name
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()

    # Frontend injected.
    frontend_dir = destination / 'frontend'
    assert frontend_dir.is_dir()

    # `just init`'s rename sed reached the staged frontend files (decision 5).
    package_json = (frontend_dir / 'package.json').read_text()
    app_test = (frontend_dir / 'src' / 'App.test.tsx').read_text()
    assert 'modernpackage' not in package_json
    assert 'modernpackage' not in app_test

    # Frontend recipes injected into the generated Justfile.
    generated_justfile = (destination / 'Justfile').read_text()
    assert 'frontend-install' in generated_justfile
    assert 'frontend-test' in generated_justfile
    assert 'frontend-check' in generated_justfile

    # Frontend recipes are excluded from the `check` chain (design "What We're
    # NOT Doing"). The chain line begins with `check:` (Justfile:53).
    check_line = next(
        line for line in generated_justfile.splitlines() if line.startswith('check:')
    )
    assert 'frontend-' not in check_line


@pytest.mark.e2e
def test_fullstack_package_runs_end_to_end(tmp_path: Path) -> None:
    """Scaffold a fullstack package and prove it runs against a real stack.

    Brings the shipped `compose.yml` up (db + migrate + app) via
    `compose up -d --build`, then polls `/readyz` until it returns 200 (proving
    DB + migrations + app readiness), then asserts host-side HTTP on `/livez`
    and `/readyz`, regenerates the API client against the live backend, and
    builds the frontend against it.

    Caveats (inherited from sibling tests, see module docstring): pulls
    `postgres:17`, builds the app image, and runs `npm ci` + `vite build` —
    minutes-long and network-dependent. Skip guards make environments lacking
    compose or Node skip rather than fail. Teardown (`compose down -v`) always
    runs in `try/finally`.
    """
    for tool in _REQUIRED_RUNTIME_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')
    compose = _detect_compose_command()
    if compose is None:
        pytest.skip('no compose command available (docker/podman compose)')

    package_name = 'fullstack-run.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

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

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    # `compose.yml` lands at the package root (`destination`), not under
    # `destination / module_name` — `_add_backend` copytrees the backend
    # template into `package_path`. The `build: .` context is `destination`.
    try:
        up = _run([*compose, 'up', '-d', '--build'], cwd=destination)
        assert up.returncode == 0, f'compose up failed:\n{up.stdout}\n{up.stderr}'
        _wait_for_ready('http://127.0.0.1:8000/readyz')

        # Backend HTTP assertions (design pillar 1). The `_wait_for_ready` poll
        # already proved readiness; these confirm real behavior from the host.
        livez_status, livez_body = _http_get('http://127.0.0.1:8000/livez')
        assert livez_status == 200, f'/livez returned {livez_status}: {livez_body}'
        assert 'pass' in livez_body, f'/livez body unexpected: {livez_body}'

        readyz_status, readyz_body = _http_get('http://127.0.0.1:8000/readyz')
        assert readyz_status == 200, f'/readyz returned {readyz_status}: {readyz_body}'

        # Frontend deps first: `generate-client` does not depend on
        # `frontend-install` (research Q4; test_e2e.py:321-323).
        install = _run(['just', 'frontend-install'], cwd=destination)
        assert install.returncode == 0, (
            f'just frontend-install failed:\n{install.stdout}\n{install.stderr}'
        )

        # `generate-client` reads the LIVE http://localhost:8000/openapi.json
        # (openapi-ts.config.ts:4), so the backend must be up — this is why the
        # call lives inside the `try` after `compose up`.
        generate = _run(['just', 'generate-client'], cwd=destination)
        assert generate.returncode == 0, (
            f'just generate-client failed:\n{generate.stdout}\n{generate.stderr}'
        )

        # The regenerated client references the real operations. Assert on stable
        # substrings (operationIds livez_livez_get / readyz_readyz_get) rather
        # than exact generated structure, which @hey-api versions may change
        # (design Open Risks).
        client_dir = destination / 'frontend' / 'src' / 'client'
        client_text = '\n'.join(
            path.read_text() for path in client_dir.rglob('*') if path.is_file()
        )
        assert 'livez' in client_text, (
            f'regenerated client missing livez:\n{client_text}'
        )
        assert 'readyz' in client_text, (
            f'regenerated client missing readyz:\n{client_text}'
        )
        # Placeholder marker is gone (src/client/index.ts:3-4 used this type).
        assert 'Record<string, unknown>' not in client_text, (
            'client still looks like the hand-written placeholder'
        )

        build = _run(['just', 'frontend-build'], cwd=destination)
        assert build.returncode == 0, (
            f'just frontend-build failed:\n{build.stdout}\n{build.stderr}'
        )

        # Build emitted a non-empty dist/ (Vite default output dir).
        dist_dir = destination / 'frontend' / 'dist'
        assert dist_dir.is_dir(), 'frontend/dist not created by build'
        assert (dist_dir / 'index.html').is_file(), 'frontend/dist/index.html missing'

        # Browser e2e (design pillar 2): drive the built frontend via
        # `vite preview` against the LIVE compose stack. `frontend-test-e2e`
        # runs `npx playwright install --with-deps chromium` first; that
        # downloads a browser (network + minutes). Treat an install failure as
        # "browsers unavailable" and skip, mirroring the compose/npm guards
        # (design Open Risks), rather than failing the suite.
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
