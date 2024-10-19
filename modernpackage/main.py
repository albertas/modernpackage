"""Example package configuration using bleeding edge toolset."""

import argparse


def main() -> str:
    """Return 'Hello world!' or package version if -v option is provided."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', help='Show package version.',
                        action='store_true', default=False)
    parsed_args = parser.parse_args()
    if parsed_args.version:
        from modernpackage import __version__
        return f"modernpackage {__version__}"

    return "Hello world!"
