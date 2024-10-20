"""Example package configuration using bleeding edge toolset."""

from argparse import ArgumentParser, Namespace
from modernpackage import __version__
from subprocess import Popen, PIPE
import os


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument('-v', '--version', help='Show package version.',
                        action='store_true', default=False)
    parser.add_argument('package_name', help='Name of a new pacakge to initialise in a local directory.', nargs='?')
    parsed_args = parser.parse_args()
    return parsed_args


def init_new_package(package_name: str) -> None:
    """Clone modernpackage files to `package_name` and run `make init` in it."""
    new_package_path = os.path.join(os.getcwd(), package_name)

    print("Cloning modernpackage files to", new_package_path)
    pipe = Popen(["git", "clone", "https://github.com/albertas/modernpackage", new_package_path], stdin=PIPE, stdout=PIPE)
    pipe.communicate()[0]

    pipe = Popen(["make", "init", package_name], stdin=PIPE, stdout=PIPE, cwd=new_package_path)
    output = pipe.communicate()[0].decode().split("make:")[0]
    print(output)


def main() -> None:
    """Return 'Hello world!' or package version if -v option is provided."""

    parsed_args = parse_args()

    if parsed_args.version:
        print(f"modernpackage {__version__}")

    elif parsed_args.package_name:
        init_new_package(package_name=parsed_args.package_name)
