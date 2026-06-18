"""Example package configuration using bleeding edge toolset."""

import os
import re
import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

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


# PEP 503 / PEP 508 valid distribution name: alphanumeric ends, with
# -, _, . permitted internally. Case-insensitive.
_PACKAGE_NAME_RE: re.Pattern[str] = re.compile(
    r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$',
    re.IGNORECASE,
)

# Matches the first character that is NOT a permitted package-name character.
# Permits A-Z via re.IGNORECASE to stay consistent with _PACKAGE_NAME_RE.
_DISALLOWED_CHAR_RE: re.Pattern[str] = re.compile(r'[^a-z0-9._-]', re.IGNORECASE)

# All Python standard-library top-level module names for the running
# interpreter (a frozenset; available since 3.10). A normalized module name
# equal to any of these would shadow a stdlib module on import, so reject it.
_STDLIB_MODULE_NAMES: frozenset[str] = sys.stdlib_module_names

# Permissive email shape: non-whitespace, '@', non-whitespace, '.',
# non-whitespace. Full RFC 5322 validation is out of scope (design Decision 4).
_EMAIL_RE: re.Pattern[str] = re.compile(r'^\S+@\S+\.\S+$')

# Require an http(s):// scheme; no network/reachability check (design Decision 5).
_REPOSITORY_URL_RE: re.Pattern[str] = re.compile(r'^https?://\S+$')

# Environment variables consulted as metadata defaults when the matching flag
# is omitted (precedence: flag > env > None).
_AUTHOR_NAME_ENV: str = 'MODERNPACKAGE_AUTHOR_NAME'
_AUTHOR_EMAIL_ENV: str = 'MODERNPACKAGE_AUTHOR_EMAIL'
_DESCRIPTION_ENV: str = 'MODERNPACKAGE_DESCRIPTION'
_LICENSE_ENV: str = 'MODERNPACKAGE_LICENSE'
_REPOSITORY_URL_ENV: str = 'MODERNPACKAGE_REPOSITORY_URL'


def _explain_invalid_package_name(value: str) -> str:
    """Return a precise reason a name failed `_PACKAGE_NAME_RE`.

    Caller guarantees `_PACKAGE_NAME_RE.match(value)` is falsy. Reasons are
    checked most-specific-first (empty → disallowed char → separator); the
    first match wins. The function is total: the final branch is the residual
    leading/trailing-separator case.
    """
    if value == '':
        return 'name must not be empty'
    match = _DISALLOWED_CHAR_RE.search(value)
    if match:
        bad_char = match.group()
        return (
            f'name contains a disallowed character: {bad_char!r} '
            f"(only letters, digits, '.', '_', '-' are allowed)"
        )
    # Residual case: regex failed, value is non-empty and contains only
    # allowed characters, so a leading/trailing '.', '_', or '-' is to blame.
    return 'name must start and end with a letter or digit'


def validate_package_name(value: str) -> str:
    """Validate value is a PEP 508 / PyPI distribution name not shadowing stdlib."""
    if not _PACKAGE_NAME_RE.match(value):
        reason = _explain_invalid_package_name(value)
        message = f'Invalid package name: {value!r} — {reason}'
        raise ArgumentTypeError(message)
    module_name = normalize_module_name(value)
    if module_name in _STDLIB_MODULE_NAMES:
        message = (
            f'Package name {value!r} collides with the Python '
            f'standard-library module {module_name!r}'
        )
        raise ArgumentTypeError(message)
    return value


def normalize_module_name(value: str) -> str:
    """Return an import-safe module name: `.` and `-` replaced by `_`.

    Input is already validated by `validate_package_name`, so this never
    returns None. `_` is preserved; case is unchanged. Leading-digit names
    (e.g. `9lives`) and Python keywords (e.g. `class`) remain invalid module
    names — out of scope (see plan Open Risks / design Open Risks).
    """
    return value.replace('.', '_').replace('-', '_')


def validate_author_email(value: str) -> str:
    """Validate value has a basic email shape; raise ArgumentTypeError otherwise."""
    if not _EMAIL_RE.match(value):
        message = f'Invalid author email: {value!r} — expected name@domain.tld'
        raise ArgumentTypeError(message)
    return value


def validate_repository_url(value: str) -> str:
    """Validate value is an http(s) URL; raise ArgumentTypeError otherwise."""
    if not _REPOSITORY_URL_RE.match(value):
        message = f'Invalid repository URL: {value!r} — expected http(s)://…'
        raise ArgumentTypeError(message)
    return value


def _environment_default(variable_name: str) -> str | None:
    """Return the env var value, treating a set-but-empty value as unset."""
    return os.environ.get(variable_name) or None


def _validated_or_error(
    parser: ArgumentParser,
    value: str | None,
    validator: Callable[[str], str],
) -> str | None:
    """Validate a non-None value, converting ArgumentTypeError to parser.error."""
    if value is None:
        return None
    try:
        return validator(value)
    except ArgumentTypeError as error:
        parser.error(str(error))


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
        type=validate_package_name,
    )
    parser.add_argument(
        '--author-name',
        help=(
            'Author name to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_NAME.'
        ),
        default=None,
    )
    parser.add_argument(
        '--description',
        help=(
            'Short description of the new package.'
            ' Defaults to $MODERNPACKAGE_DESCRIPTION.'
        ),
        default=None,
    )
    parser.add_argument(
        '--author-email',
        help=(
            'Author email to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_EMAIL.'
        ),
        type=validate_author_email,
        default=None,
    )
    parser.add_argument(
        '--license',
        help=(
            'License identifier for the new package.'
            ' Defaults to $MODERNPACKAGE_LICENSE.'
        ),
        default=None,
    )
    parser.add_argument(
        '--repository-url',
        help=(
            'Repository URL to record in the new package.'
            ' Defaults to $MODERNPACKAGE_REPOSITORY_URL.'
        ),
        type=validate_repository_url,
        default=None,
    )
    arguments = parser.parse_args()
    if arguments.author_name is None:
        arguments.author_name = _environment_default(_AUTHOR_NAME_ENV)
    if arguments.description is None:
        arguments.description = _environment_default(_DESCRIPTION_ENV)
    if arguments.license is None:
        arguments.license = _environment_default(_LICENSE_ENV)
    if arguments.author_email is None:
        arguments.author_email = _environment_default(_AUTHOR_EMAIL_ENV)
    if arguments.repository_url is None:
        arguments.repository_url = _environment_default(_REPOSITORY_URL_ENV)
    arguments.author_email = _validated_or_error(
        parser, arguments.author_email, validate_author_email
    )
    arguments.repository_url = _validated_or_error(
        parser, arguments.repository_url, validate_repository_url
    )
    return arguments


def init_new_package(  # noqa: PLR0913
    package_name: str,
    *,
    author_name: str | None = None,
    author_email: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
    repository_url: str | None = None,
) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    # Threaded for later V4 work (writing metadata into pyproject.toml); not yet
    # consumed. The `del` documents intent and satisfies ruff ARG001.
    del author_name, author_email, description, package_license, repository_url

    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

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
            ['just', 'init', module_name],  # noqa: S607
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
        print(f'just check passed — {module_name} scaffold is valid.')  # noqa: T201
        return 0
    print(  # noqa: T201
        f'just check failed with exit code {pipe.returncode}'
        f' — review the output in {module_name}.',
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
            return init_new_package(
                package_name=parsed_args.package_name,
                author_name=parsed_args.author_name,
                author_email=parsed_args.author_email,
                description=parsed_args.description,
                package_license=parsed_args.license,
                repository_url=parsed_args.repository_url,
            )
        except RuntimeError as error:
            print(error, file=sys.stderr)  # noqa: T201
            return 1

    return 0
