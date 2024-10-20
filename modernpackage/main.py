"""Example package configuration using bleeding edge toolset."""

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
        help='Name of a new pacakge to initialise in a local directory.',
        nargs='?',
        type=check_alpha_numeric
    )
    return parser.parse_args()


def init_new_package(package_name: str) -> None:
    """Clone modernpackage files into `package_name` and run `make init` in it."""
    new_package_path = Path.cwd() / package_name

    pipe = Popen(  # noqa: S603
        ['git', 'clone', 'https://github.com/albertas/modernpackage', new_package_path],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
    )
    pipe.communicate()[0]

    pipe = Popen(  # noqa: S603
        ['make', 'init', package_name], stdin=PIPE, stdout=PIPE, cwd=new_package_path  # noqa: S607
    )
    pipe.communicate()[0].decode().split('make:')[0].strip()


def main() -> None:
    """Return 'Hello world!' or package version if -v option is provided."""
    parsed_args = parse_args()

    if parsed_args.version:
        print(f'modernpackage {__version__}')  # noqa: T201

    elif parsed_args.package_name:
        init_new_package(package_name=parsed_args.package_name)
