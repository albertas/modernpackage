"""Example package configuration using bleeding edge toolset."""

import os
from argparse import ArgumentParser, Namespace
from subprocess import PIPE, Popen

from modernpackage import __version__


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
        help='Name of a new pacakge to initialise in a local directory.',
        nargs='?',
    )
    return parser.parse_args()


def init_new_package(package_name: str) -> None:
    """Clone modernpackage files into `package_name` and run `make init` in it."""
    new_package_path = os.path.join(os.getcwd(), package_name)

    pipe = Popen(
        ['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path],
        stdin=PIPE,
        stdout=PIPE,
    )
    pipe.communicate()[0]

    pipe = Popen(
        ['make', 'init', package_name], stdin=PIPE, stdout=PIPE, cwd=new_package_path
    )
    pipe.communicate()[0].decode().split('make:')[0].strip()


def main() -> None:
    """Return 'Hello world!' or package version if -v option is provided."""
    parsed_args = parse_args()

    if parsed_args.version:
        print(f"modernpackage {__version__}")  # noqa: T201

    elif parsed_args.package_name:
        init_new_package(package_name=parsed_args.package_name)
