"""Example package configuration using bleeding edge toolset."""

import os
import re
import shutil
import sys
import tomllib
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, Popen, TimeoutExpired, run
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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


# Required executables that must resolve on PATH before scaffolding begins.
_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')


# Template repository cloned to scaffold a new package; used by the reachability
# probe and the clone, and as the metadata-replacement target.
_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'

# Upper bound (seconds) on the pre-flight `git ls-remote` reachability probe so a
# hung DNS/connect cannot defeat fail-fast.
_REMOTE_REACHABILITY_TIMEOUT_SECONDS: int = 10


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

# Git config keys consulted as the weakest metadata default for author name /
# email when the matching flag and env var are both absent
# (precedence: flag > env > git config > None).
_GIT_CONFIG_USER_NAME_KEY: str = 'user.name'
_GIT_CONFIG_USER_EMAIL_KEY: str = 'user.email'

# Per-user TOML config file consulted as the weakest metadata default for all
# five fields when the matching flag, env var, and git config are all absent
# (precedence: flag > env > git config > config file > None).
_CONFIG_DIR_NAME: str = 'modernpackage'
_CONFIG_FILE_NAME: str = 'config.toml'
_XDG_CONFIG_HOME_ENV: str = 'XDG_CONFIG_HOME'


@dataclass(frozen=True)
class _MetadataField:
    """Declares how one metadata field resolves its default, sources in order."""

    attr: str  # Namespace attribute the flag stores to (e.g. 'author_name')
    env_var: str  # Environment variable consulted after the flag
    git_key: str | None  # git config key consulted next; None = no git source
    config_key: str  # Config-file flat key consulted last


# One entry per metadata field. Sources are tried in the canonical order
# env -> git config -> config file; the flag value already in the namespace wins
# implicitly because the resolver only fills attrs still set to None. git_key=None
# encodes the author-only asymmetry: description / license / repository_url have
# no git source (precedence: flag > env > config file > None), while author_name /
# author_email do (flag > env > git config > config file > None).
_METADATA_FIELDS: tuple[_MetadataField, ...] = (
    _MetadataField(
        'author_name', _AUTHOR_NAME_ENV, _GIT_CONFIG_USER_NAME_KEY, 'author_name'
    ),
    _MetadataField('description', _DESCRIPTION_ENV, None, 'description'),
    _MetadataField('license', _LICENSE_ENV, None, 'license'),
    _MetadataField(
        'author_email', _AUTHOR_EMAIL_ENV, _GIT_CONFIG_USER_EMAIL_KEY, 'author_email'
    ),
    _MetadataField('repository_url', _REPOSITORY_URL_ENV, None, 'repository_url'),
)


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


def _git_config_default(key: str) -> str | None:
    """Return the effective `git config <key>` value, or None.

    Reads the merged (local-over-global) git config the way a commit would
    resolve it (design Decision 6). Degrades silently to None — never raises —
    when git is missing, the key is unset (git exits 1), the value is empty, or
    the command otherwise fails. An absent git default is expected, not an
    error, so no notice is printed (design Decision 4).
    """
    try:
        result = run(  # noqa: S603
            ['git', 'config', key],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _user_config_path() -> Path | None:
    """Return the per-user config file path, or None if home is unresolvable.

    Resolves `$XDG_CONFIG_HOME` (a set-but-empty value coalesces to the
    `~/.config` fallback, matching the empty-as-unset convention of the env
    reader), else `~/.config`. Returns None when the home directory cannot be
    determined (design Open Risk: `Path.home()` raises in odd environments).
    """
    xdg_config_home = os.environ.get(_XDG_CONFIG_HOME_ENV) or None
    if xdg_config_home is not None:
        base = Path(xdg_config_home)
    else:
        try:
            base = Path.home() / '.config'
        except RuntimeError:
            return None
    return base / _CONFIG_DIR_NAME / _CONFIG_FILE_NAME


def _load_config_file() -> dict[str, object]:
    """Parse the per-user TOML config file into a mapping, or return {}.

    A missing file (no resolvable path or FileNotFoundError) returns {} silently
    — an absent config is expected, not an error. Malformed or unreadable files
    (TOMLDecodeError / OSError) print a notice to stderr and return {} (design
    Decision 6).
    """
    path = _user_config_path()
    if path is None:
        return {}
    try:
        with path.open('rb') as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as error:
        print(  # noqa: T201
            f'Ignoring unreadable config file {path}: {error}',
            file=sys.stderr,
        )
        return {}


def _config_file_default(config: Mapping[str, object], key: str) -> str | None:
    """Return config[key] only if it is a non-empty str; else None.

    Empty strings and non-string TOML values (int/bool/array/table) coalesce to
    None, matching the empty-as-unset convention of the env/git readers and
    protecting the regex validators from non-str input (design Decision 5).
    """
    value = config.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _resolve_metadata_defaults(
    arguments: Namespace, config: Mapping[str, object]
) -> None:
    """Fill each None metadata field from its first available source, in-place.

    Walks `_METADATA_FIELDS`; for a field still None, tries env, then git config
    (only if the descriptor names a git key), then the config file, stopping at
    the first non-None value. Each source is consulted lazily and only when the
    higher-priority sources came back None, so "loser never consulted" assertions
    hold (a stronger source never triggers a weaker reader). The config file is
    passed in pre-loaded so it is read exactly once per `parse_args()` call.
    """
    for field in _METADATA_FIELDS:
        if getattr(arguments, field.attr) is not None:
            continue
        value = _environment_default(field.env_var)
        if value is None and field.git_key is not None:
            value = _git_config_default(field.git_key)
        if value is None:
            value = _config_file_default(config, field.config_key)
        setattr(arguments, field.attr, value)


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
            ' Defaults to $MODERNPACKAGE_AUTHOR_NAME, then git config'
            ' user.name, then the config.toml config file.'
        ),
        default=None,
    )
    parser.add_argument(
        '--description',
        help=(
            'Short description of the new package.'
            ' Defaults to $MODERNPACKAGE_DESCRIPTION, then the config.toml'
            ' config file.'
        ),
        default=None,
    )
    parser.add_argument(
        '--author-email',
        help=(
            'Author email to record in the new package.'
            ' Defaults to $MODERNPACKAGE_AUTHOR_EMAIL, then git config'
            ' user.email, then the config.toml config file.'
        ),
        type=validate_author_email,
        default=None,
    )
    parser.add_argument(
        '--license',
        help=(
            'License identifier for the new package.'
            ' Defaults to $MODERNPACKAGE_LICENSE, then the config.toml'
            ' config file.'
        ),
        default=None,
    )
    parser.add_argument(
        '--repository-url',
        help=(
            'Repository URL to record in the new package.'
            ' Defaults to $MODERNPACKAGE_REPOSITORY_URL, then the config.toml'
            ' config file.'
        ),
        type=validate_repository_url,
        default=None,
    )
    arguments = parser.parse_args()
    _resolve_metadata_defaults(arguments, _load_config_file())
    arguments.author_email = _validated_or_error(
        parser, arguments.author_email, validate_author_email
    )
    arguments.repository_url = _validated_or_error(
        parser, arguments.repository_url, validate_repository_url
    )
    return arguments


def _toml_escape(value: str) -> str:
    """Escape backslashes then double-quotes for safe TOML basic-string insertion."""
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _write_package_metadata(  # noqa: PLR0913
    package_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
) -> None:
    """Replace template placeholders in the cloned pyproject.toml with supplied values.

    Each non-None field is applied as a targeted, TOML-escaped str.replace of a
    known template literal; None fields are skipped (design Decision 7). A missing
    pyproject.toml prints a notice and returns without raising (graceful boundary
    degradation, design Decision 8 — also lets the Popen-mocked unit tests, which
    never create a real clone, pass unchanged). The file is rewritten only if a
    substitution changed it.
    """
    pyproject_path = package_path / 'pyproject.toml'
    try:
        original = pyproject_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No pyproject.toml at {pyproject_path}; skipping metadata.',
            file=sys.stderr,
        )
        return

    updated = original
    if author_name is not None:
        updated = updated.replace('Name Surname', _toml_escape(author_name))
    if author_email is not None:
        updated = updated.replace('email@example.com', _toml_escape(author_email))
    if description is not None:
        updated = updated.replace(
            'Package configuration example using bleeding edge toolset.',
            _toml_escape(description),
        )
    if repository_url is not None:
        updated = updated.replace(
            _TEMPLATE_REPOSITORY_URL,
            _toml_escape(repository_url),
        )
    if package_license is not None:
        updated = _apply_license(updated, package_license)

    if updated != original:
        pyproject_path.write_text(updated)


def _apply_license(content: str, package_license: str) -> str:
    """Insert a PEP 639 license key and drop the hardcoded MIT trove classifier.

    Adds `license = "<value>"` to [project] after the stable `readme` key, and
    removes the `License :: OSI Approved :: MIT License` classifier line so the
    scaffold does not carry a contradictory hardcoded license.
    """
    license_line = f'license = "{_toml_escape(package_license)}"'
    content = content.replace(
        'readme = "README.md"',
        f'readme = "README.md"\n{license_line}',
    )
    return content.replace(
        '    "License :: OSI Approved :: MIT License",\n',
        '',
    )


@dataclass(frozen=True)
class PreflightCheck:
    """One entry in the preflight check registry."""

    label: str  # text shown after the status marker on the checklist line
    run: Callable[
        [], None
    ]  # verifier; returns None on success, raises RuntimeError on failure


_PREFLIGHT_HEADER: str = 'Preflight checks:'


def _format_check_line(label: str, *, ok: bool) -> str:
    """Return one indented checklist line; marker padded to 6 chars so labels align."""
    marker = '[ok]' if ok else '[FAIL]'
    return f'  {marker:<6} {label}'


def _verify_required_tools() -> None:
    """Raise RuntimeError if any required executable is absent from PATH."""
    missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        message = (
            f'required tool(s) not found on PATH: {", ".join(missing)}'
            ' — install the missing tool(s) before scaffolding.'
            ' See https://github.com/casey/just#installation'
        )
        raise RuntimeError(message)


def _verify_target_directory_absent(target_path: Path) -> None:
    """Raise RuntimeError if the target package directory already exists."""
    if target_path.exists():
        message = (
            f'target directory already exists: {target_path}'
            ' — choose a different package name or remove the existing directory'
        )
        raise RuntimeError(message)


def _verify_template_remote_reachable() -> None:
    """Raise RuntimeError if the template remote cannot be reached.

    Pre-flight probe (design Decision 1): `git ls-remote` contacts the remote
    without cloning, and its stderr is already classified by
    `humanize_git_clone_error`. Returns None silently when reachable. Bounded by
    `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` so a hung connect still fails fast.
    """
    try:
        result = run(  # noqa: S603
            ['git', 'ls-remote', _TEMPLATE_REPOSITORY_URL],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=_REMOTE_REACHABILITY_TIMEOUT_SECONDS,
        )
    except TimeoutExpired as error:
        friendly = 'repository unreachable — check your network connection'
        raw = (
            'template remote unreachable (git ls-remote timed out after'
            f' {_REMOTE_REACHABILITY_TIMEOUT_SECONDS}s)'
        )
        message = f'{friendly}\n\n{raw}'
        raise RuntimeError(message) from error

    if result.returncode != 0:
        stderr_text = result.stderr.strip()
        raw = (
            'template remote unreachable (git ls-remote exit code'
            f' {result.returncode}): {stderr_text}'
        )
        friendly_msg = humanize_git_clone_error(stderr_text)
        message = f'{friendly_msg}\n\n{raw}' if friendly_msg else raw
        raise RuntimeError(message)


def _run_preflight_checks(target_path: Path) -> None:
    """Print the preflight checklist to stdout, running each check in order.

    The registry is built per-call so `_verify_target_directory_absent` binds
    `target_path` via closure. Each check's verifier raises RuntimeError on
    failure; the success path emits all `[ok]` lines.
    """
    checks = (
        PreflightCheck('package name valid', lambda: None),
        PreflightCheck(
            f'required tools on PATH ({", ".join(_REQUIRED_TOOLS)})',
            _verify_required_tools,
        ),
        PreflightCheck(
            'target directory available',
            lambda: _verify_target_directory_absent(target_path),
        ),
        PreflightCheck('template remote reachable', _verify_template_remote_reachable),
    )
    print(_PREFLIGHT_HEADER)  # noqa: T201
    for check in checks:
        try:
            check.run()
        except RuntimeError:
            print(_format_check_line(check.label, ok=False))  # noqa: T201
            raise
        print(_format_check_line(check.label, ok=True))  # noqa: T201


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
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

    _run_preflight_checks(new_package_path)

    pipe = Popen(  # noqa: S603
        ['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path],  # noqa: S607
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

    _write_package_metadata(
        new_package_path,
        author_name=author_name,
        author_email=author_email,
        description=description,
        package_license=package_license,
        repository_url=repository_url,
    )

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
