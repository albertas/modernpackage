"""Example package configuration using bleeding edge toolset."""

import re
import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from subprocess import PIPE, Popen

from modernpackage import __version__

# Ordered most-specific first so that a more precise pattern wins over a broad one.
_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern[str], str]] = [
    # Network connectivity failures
    (
        re.compile(
            r'could not resolve host|could not read from remote'
            r'|failed to connect|connection timed out|network is unreachable'
        ),
        'repository unreachable — check your network connection',
    ),
    # Repository not found on the remote (git may insert the URL between words)
    (
        re.compile(r'repository.*not found|remote: not found|does not exist'),
        'template repository not found — it may have moved or been removed',
    ),
    # SSH / credential authentication errors (must precede broad "permission denied")
    (
        re.compile(
            r'permission denied \(publickey\)|authentication failed'
            r'|could not read username'
        ),
        'authentication failed — check your git credentials or access rights',
    ),
    # Destination directory already occupied
    (
        re.compile(r'already exists and is not an empty directory'),
        'destination directory already exists — choose a different package name',
    ),
    # Filesystem permission / write errors (broad, intentionally last)
    (
        re.compile(r'permission denied|could not create|unable to create'),
        'cannot write to the destination directory — check filesystem permissions',
    ),
]


def humanize_git_clone_error(stderr_text: str) -> str | None:
    """Return the first friendly message for a known git clone failure, or None."""
    lowercased = stderr_text.lower()
    for pattern, message in _GIT_CLONE_ERROR_MESSAGES:
        if pattern.search(lowercased):
            return message
    return None


def check_alpha_numeric(value: str) -> str:
    """Validate value to contain only Letters and Numbers."""
    if not value.isalnum():
        message = 'Non-AlphaNumeric package name'
        raise ArgumentTypeError(message)
    return value


def parse_args() -> Namespace:
    """Parse CLI options and return them as Namespace (object instance)."""
    parser = ArgumentParser()
    parser.add_argument(
        '-v',
        '--version',
        help='Show package version.',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        'package_name',
        help='Name of a new package to initialise in a local directory.',
        nargs='?',
        type=check_alpha_numeric,
    )
    return parser.parse_args()


def init_new_package(package_name: str) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    new_package_path = Path.cwd() / package_name

    pipe = Popen(  # noqa: S603
        ['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    _stdout, stderr = pipe.communicate()
    stderr_text = stderr.decode().strip()

    if pipe.returncode != 0:
        raw = f'git clone failed with exit code {pipe.returncode}: {stderr_text}'
        friendly = humanize_git_clone_error(stderr_text)
        message = f'{friendly}\n\n{raw}' if friendly else raw
        raise RuntimeError(message)

    try:
        pipe = Popen(  # noqa: S603
            ['just', 'init', package_name],  # noqa: S607
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            cwd=new_package_path,
        )
    except FileNotFoundError as error:
        message = (
            "'just' command not found — install it to initialize the package."
            ' See https://github.com/casey/just#installation'
        )
        raise RuntimeError(message) from error
    _stdout, stderr = pipe.communicate()
    stderr_text = stderr.decode().strip()

    if pipe.returncode != 0:
        message = f'just init failed with exit code {pipe.returncode}: {stderr_text}'
        raise RuntimeError(message)

    pipe = Popen(
        ['just', 'check'],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        cwd=new_package_path,
    )
    pipe.communicate()

    if pipe.returncode == 0:
        print(f'just check passed — {package_name} scaffold is valid.')  # noqa: T201
        return 0
    print(  # noqa: T201
        f'just check failed with exit code {pipe.returncode}'
        f' — review the output in {package_name}.',
        file=sys.stderr,
    )
    return 1


def main() -> int:
    """Orchestrate CLI commands; return 0 on success or 1 on scaffolding failure."""
    parsed_args = parse_args()

    if parsed_args.version:
        print(f'modernpackage {__version__}')  # noqa: T201

    elif parsed_args.package_name:
        try:
            return init_new_package(package_name=parsed_args.package_name)
        except RuntimeError as error:
            print(error, file=sys.stderr)  # noqa: T201
            return 1

    return 0
