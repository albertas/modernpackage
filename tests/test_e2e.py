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
import shutil
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.e2e
def test_scaffolded_package_passes_check(tmp_path: Path) -> None:
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'scaffoldcheck'
    destination = tmp_path / package_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    init = _run(
        ['just', 'init', package_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    init_file = destination / package_name / '__init__.py'
    assert init_file.exists()
    assert '0.0.1' in init_file.read_text()

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'
