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
    """Copy this package file to current dir as `package_name` and run `make init` in it."""

    from_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    new_package_path = os.path.join(os.getcwd(), package_name)

    print("Copying files from", from_path, "to", new_package_path, "..")
    pipe = Popen(["cp", "-r", from_path, new_package_path], stdin=PIPE, stdout=PIPE)
    pipe.communicate()[0]

    pipe = Popen(["make", "init", package_name], stdin=PIPE, stdout=PIPE, cwd=new_package_path)
    output = pipe.communicate()[0].decode()
    print(output)


def main() -> None:
    """Return 'Hello world!' or package version if -v option is provided."""

    parsed_args = parse_args()

    if parsed_args.version:
        print(f"modernpackage {__version__}")

    elif parsed_args.package_name:
        init_new_package(package_name=parsed_args.package_name)
