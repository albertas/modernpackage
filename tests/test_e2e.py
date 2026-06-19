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
from pathlib import Path

import pytest

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
    # __init__.py version 0.0.1 already asserted at lines 88-90; check stub test.
    stub = (destination / 'tests' / 'test_main.py').read_text()
    assert '0.0.1' in stub


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
