"""Example package configuration using bleeding edge toolset."""

import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from subprocess import PIPE, Popen

from modernpackage import __version__


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


def init_new_package(package_name: str) -> None:
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
        message = f'git clone failed with exit code {pipe.returncode}: {stderr_text}'
        raise RuntimeError(message)

    pipe = Popen(  # noqa: S603
        ['just', 'init', package_name],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        cwd=new_package_path,
    )
    _stdout, stderr = pipe.communicate()
    stderr_text = stderr.decode().strip()

    if pipe.returncode != 0:
        message = f'just init failed with exit code {pipe.returncode}: {stderr_text}'
        raise RuntimeError(message)


def main() -> int:
    """Orchestrate CLI commands; return 0 on success or 1 on scaffolding failure."""
    parsed_args = parse_args()

    if parsed_args.version:
        print(f'modernpackage {__version__}')  # noqa: T201

    elif parsed_args.package_name:
        try:
            init_new_package(package_name=parsed_args.package_name)
        except RuntimeError as error:
            print(error, file=sys.stderr)  # noqa: T201
            return 1

    return 0
