"""Example package configuration using bleeding edge toolset."""

import os
import re
import shutil
import sys
import tomllib
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, Popen, run
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


# Template repository cloned to scaffold a new package; used by the clone and as
# the metadata-replacement target.
_TEMPLATE_REPOSITORY_URL: str = 'https://github.com/albertas/modernpackage'


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
        '--dry-run',
        help='Preview what scaffolding would do without making any changes.',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--backend',
        '--fastapi',
        help='Include a FastAPI backend (app, async DB, migrations, container).',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--fullstack',
        '--reactjs',
        help='Include a FastAPI backend AND a React frontend (Vite, Vitest, generated API client).',  # noqa: E501
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


# Clone-relative paths removed wholesale from a generated package. Looped over
# like _METADATA_FIELDS; absent entries are tolerated (clone-shape-agnostic).
# `backend_template` is always removed: the clone contains it (from the repo),
# but the no-flag path must not include it. `_add_backend` re-injects from the
# installed/source package path when --backend is set.
_SCAFFOLDING_PATHS_TO_DELETE: tuple[str, ...] = (
    'modernpackage/main.py',
    'tests/test_e2e.py',
    'tests_e2e',  # Newer runtime e2e dir (T61/T62); imports `main`, must not ship
    'docs',
    'BACKLOG.md',
    'backend_template',  # Always removed; re-injected if --backend is set
    'frontend_template',  # Always removed; re-injected if --fullstack is set
    # Scaffolder operational/process artifacts removed from every generated
    # package (never part of a scaffolded project's tree).
    'errors',
    'issues',
    'workspace',
    # Deleted here to drop the scaffolder's phases/semaphores, then re-seeded by
    # _strip_scaffolding with a fresh `code_quality_is_good: true` stub.
    'lifecycle_state.yml',
    'metrics.yml',
)

# Stub tests/test_main.py: pytest needs >=1 collected test (empty collection
# exits non-zero), and importing the package keeps --cov-fail-under=95.0 happy
# (after main.py is deleted the only package code is __version__, run on import).
# Written with the literal `modernpackage` token so `just init`'s rename sed
# (Justfile:61-66) rewrites the import to the new module name.
_TEST_MAIN_STUB: str = """\
from modernpackage import __version__


def test_version() -> None:
    assert __version__ == '0.0.1'
"""

# Minimal generic README (pyproject.toml:7 requires `readme = "README.md"`).
# The distribution name is written directly into the H1 during
# _strip_scaffolding, so `just init`'s rename sed no longer touches README.md.
_README_STUB_TEMPLATE: str = """\
# {package_name}

A Python package.
"""

# Fresh lifecycle_state.yml seeded into a generated package. The scaffolder's own
# copy (with its dev phases and runtime semaphores) is stripped via
# _SCAFFOLDING_PATHS_TO_DELETE; this clean stub replaces it so the new package's
# own lifecycle loop starts from a good-quality baseline (`code_quality_is_good:
# true`) rather than inheriting the scaffolder's process state.
_LIFECYCLE_STATE_STUB: str = """\
code_quality_is_good: true
"""

# Top-level template tree copied into a generated package by `_add_backend`.
# Resolved relative to this file so it works from a source checkout and from an
# installed wheel (shipped as package data via [tool.hatch.build] include).
_BACKEND_TEMPLATE_DIR: Path = (
    Path(__file__).resolve().parent.parent / 'backend_template'
)

# Top-level template tree copied into a generated package's `frontend/` by
# `_add_frontend`. Resolved relative to this file so it works from a source
# checkout and from an installed wheel (shipped via [tool.hatch.build] include).
_FRONTEND_TEMPLATE_DIR: Path = (
    Path(__file__).resolve().parent.parent / 'frontend_template'
)

# Runtime dependencies appended to the generated package's [project.dependencies]
# (PEP 621 — these are service runtime deps, not dev tooling). Lower bounds only.
_BACKEND_DEPENDENCIES: tuple[str, ...] = (
    'fastapi>=0.115',
    'sqlalchemy[asyncio]>=2.0',
    'asyncpg>=0.30',
    'alembic>=1.14',
    'uvicorn>=0.34',
)

# Test-only dependency appended to the dev dependency-group: TestClient needs httpx.
_BACKEND_DEV_DEPENDENCIES: tuple[str, ...] = ('httpx',)

# Migration recipes appended to the generated package's Justfile (NOT added to the
# `check` chain — they need a live database). Two-space body indent matches the
# template Justfile; `: sync` follows the recipe convention (Justfile:8-42).
_BACKEND_RECIPES: str = """
migrate: sync
  uv run alembic upgrade head

makemigration message: sync
  uv run alembic revision --autogenerate -m "{{message}}"

migration-check: sync
  uv run alembic check
"""

# Frontend recipes appended to the generated package's Justfile (NOT added to the
# `check` chain — they need Node, which the generated package's CI does not have;
# mirrors the backend-recipes precedent above). `frontend-check` aggregates the
# Node-side gates for local use. `cd frontend &&` scopes them to the injected
# subdirectory; no `: sync` dep (that is a Python/uv concern).
_FRONTEND_RECIPES: str = """
frontend-install:
  cd frontend && npm ci

frontend-build:
  cd frontend && npm run build

frontend-test:
  cd frontend && npm run test

frontend-lint:
  cd frontend && npm run lint

generate-client:
  cd frontend && npm run generate-client

frontend-test-e2e:
  cd frontend && npx playwright install --with-deps chromium && npm run test:e2e

frontend-check: frontend-install
  cd frontend && npm run format:check && npm run lint \
    && npm run typecheck && npm run test
"""


def _remove_project_scripts(pyproject_path: Path) -> None:
    """Remove the [project.scripts] table from the cloned pyproject.toml.

    Deletes the header line, its entries, and the trailing blank line, leaving
    surrounding tables ([project.urls], [dependency-groups], the
    e2e marker, the vupi dep, [tool.deadcode]) intact. No-op if the table or the
    file is absent (graceful boundary degradation, like _write_package_metadata).
    """
    try:
        lines = pyproject_path.read_text().splitlines(keepends=True)
    except FileNotFoundError:
        return
    try:
        start = lines.index('[project.scripts]\n')
    except ValueError:
        return
    end = start + 1
    while end < len(lines) and not lines[end].startswith('['):
        end += 1
    del lines[start:end]
    pyproject_path.write_text(''.join(lines))


def _strip_scaffolding(package_path: Path, package_name: str) -> None:
    """Remove the scaffolder's own CLI, tests, docs, and entry points from a clone.

    Mutates the cloned tree in place. Run before `just init` so the rename sed
    (Justfile:61-66) and the single git commit (Justfile:72) capture an already-
    clean tree. Deletes tolerate absent paths; the stub writes assume the clone
    root and tests/ exist (always true for a real clone). Stubs retain the
    literal `modernpackage` token so the rename sed rewrites their imports,
    EXCEPT README.md, whose H1 is written directly as the distribution
    `package_name` (the rename sed no longer matches it). The scaffolder's own
    `lifecycle_state.yml` is deleted and then re-seeded with a fresh
    `code_quality_is_good: true` stub so the generated package's lifecycle
    starts from a good-quality baseline instead of inheriting scaffolder state.
    """
    for relative_path in _SCAFFOLDING_PATHS_TO_DELETE:
        target = package_path / relative_path
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
    (package_path / 'tests' / 'test_main.py').write_text(_TEST_MAIN_STUB)
    (package_path / 'README.md').write_text(
        _README_STUB_TEMPLATE.format(package_name=package_name)
    )
    (package_path / 'lifecycle_state.yml').write_text(_LIFECYCLE_STATE_STUB)
    _remove_project_scripts(package_path / 'pyproject.toml')


_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'
# Version the template is reset to by `just init` (mirrors the Justfile sed
# value at Justfile:67; coupled by convention, not programmatically).
_RESET_VERSION: str = '0.0.1'
_INIT_SUMMARY_HEADER: str = 'Created package:'
_NEXT_COMMANDS_HEADER: str = 'Next steps:'
_ANSI_GREEN: str = '\033[32m'
_ANSI_RESET: str = '\033[0m'


def _color_enabled() -> bool:
    """Return True when stdout is an interactive TTY and NO_COLOR is unset.

    Probes the environment/TTY at a process boundary; never raises — degrades to
    plain text (graceful boundary style).
    """
    return sys.stdout.isatty() and os.environ.get('NO_COLOR') is None


def _green(text: str) -> str:
    """Wrap `text` in ANSI green/reset when color is enabled, else return as-is."""
    if _color_enabled():
        return f'{_ANSI_GREEN}{text}{_ANSI_RESET}'
    return text


def _format_dry_run_plan(  # noqa: PLR0913
    module_name: str,
    target_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
    backend: bool = False,
    fullstack: bool = False,
) -> str:
    """Return the multi-line dry-run preview (design Decision 3).

    Reports the actions a real run would take at the level the code knows:
    target directory, template clone URL, pyproject.toml metadata
    substitutions (None fields keep the template default), and the documented
    `just init` outcomes (directory rename, version reset).
    """
    metadata_fields = (
        ('author name', author_name),
        ('author email', author_email),
        ('description', description),
        ('license', package_license),
        ('repository URL', repository_url),
    )
    lines = [
        _DRY_RUN_HEADER,
        f'  clone {_TEMPLATE_REPOSITORY_URL} into {target_path}',
        '  update pyproject.toml metadata:',
    ]
    for label, value in metadata_fields:
        if value is None:
            lines.append(f'    {label}: keeps template default')
        else:
            lines.append(f'    {label}: {value}')
    lines.append(f'  run just init: rename modernpackage/ -> {module_name}/')
    lines.append(f'  run just init: reset version to {_RESET_VERSION}')
    if backend or fullstack:
        lines.append('  add FastAPI backend (app, migrations, container, recipes)')
    if fullstack:
        lines.append(
            '  add React frontend (Vite, Vitest, generated API client, recipes)'
        )
    return '\n'.join(lines)


def _print_dry_run_plan(  # noqa: PLR0913
    module_name: str,
    target_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
    backend: bool = False,
    fullstack: bool = False,
) -> None:
    """Print the formatted dry-run plan to stdout (output convention, main.py:592)."""
    print(  # noqa: T201
        _format_dry_run_plan(
            module_name,
            target_path,
            author_name=author_name,
            author_email=author_email,
            description=description,
            package_license=package_license,
            repository_url=repository_url,
            backend=backend,
            fullstack=fullstack,
        )
    )


def _format_init_summary(package_name: str, created_path: Path) -> str:
    """Return the multi-line post-scaffold summary (design Decision 1).

    Reports the package/distribution name, the created directory path, and the
    version the template was reset to (`_RESET_VERSION`).
    """
    lines = [
        _INIT_SUMMARY_HEADER,
        f'  package name: {package_name}',
        f'  path: {created_path}',
        f'  version: {_RESET_VERSION}',
    ]
    return '\n'.join(lines)


def _print_init_summary(package_name: str, created_path: Path) -> None:
    """Print the formatted init summary to stdout."""
    print(_format_init_summary(package_name, created_path))  # noqa: T201


def _format_next_commands(module_name: str) -> str:
    """Return the next-steps hint block shown after a successful scaffold."""
    return '\n'.join(
        [
            _NEXT_COMMANDS_HEADER,
            f'  cd {module_name} && just check',
        ]
    )


def _print_next_commands(module_name: str) -> None:
    """Print the formatted next-steps hint to stdout."""
    print(_format_next_commands(module_name))  # noqa: T201


def _append_backend_dependencies(pyproject_path: Path) -> None:
    """Populate [project.dependencies] and extend the dev group for the backend.

    Replaces the empty `dependencies = []` array with the backend runtime deps and
    prepends the dev-only deps (httpx) to the `dev` dependency-group. No-op with a
    notice if the file is absent (graceful boundary, like `_write_package_metadata`).
    """
    try:
        content = pyproject_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No pyproject.toml at {pyproject_path}; skipping backend deps.',
            file=sys.stderr,
        )
        return
    runtime = ''.join(f'    "{dep}",\n' for dep in _BACKEND_DEPENDENCIES)
    content = content.replace(
        'dependencies = []\n',
        f'dependencies = [\n{runtime}]\n',
    )
    dev = ''.join(f'    "{dep}",\n' for dep in _BACKEND_DEV_DEPENDENCIES)
    content = content.replace('dev = [\n', f'dev = [\n{dev}')
    pyproject_path.write_text(content)


def _append_backend_recipes(justfile_path: Path) -> None:
    """Append the migration recipes to the generated package's Justfile.

    No-op with a notice if the Justfile is absent (graceful boundary).
    """
    try:
        content = justfile_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No Justfile at {justfile_path}; skipping backend recipes.',
            file=sys.stderr,
        )
        return
    justfile_path.write_text(content + _BACKEND_RECIPES)


def _stage_injected_files(package_path: Path) -> None:
    """Stage the injected backend files so `just init`'s `git grep` sees them.

    Runs `git add -A` in the clone. Copied files are untracked until staged; the
    rename sed (Justfile:62-67) only rewrites tracked files. Raises RuntimeError on
    a non-zero exit, matching the other subprocess steps.
    """
    pipe = Popen(
        ['git', 'add', '-A'],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        cwd=package_path,
    )
    _stdout, stderr = pipe.communicate()
    if pipe.returncode != 0:
        stderr_text = stderr.decode().strip()
        message = f'git add failed with exit code {pipe.returncode}: {stderr_text}'
        raise RuntimeError(message)


def _append_frontend_recipes(justfile_path: Path) -> None:
    """Append the frontend recipes to the generated package's Justfile.

    No-op with a notice if the Justfile is absent (graceful boundary).
    """
    try:
        content = justfile_path.read_text()
    except FileNotFoundError:
        print(  # noqa: T201
            f'No Justfile at {justfile_path}; skipping frontend recipes.',
            file=sys.stderr,
        )
        return
    justfile_path.write_text(content + _FRONTEND_RECIPES)


def _add_frontend(package_path: Path) -> None:
    """Copy the React frontend template into a generated package's `frontend/`.

    Copies `_FRONTEND_TEMPLATE_DIR` into `package_path / 'frontend'` (isolating
    the Node project from the Python package root, design Decision 3), then
    appends the frontend recipes to the Justfile. Adds NO Python deps and spawns NO
    child processes at scaffold time (Node tooling is invoked later by the user via
    `just frontend-install`). Copied files carry the literal `modernpackage` token
    (package.json name) so `just init`'s rename sed rewrites them; callers stage
    the copied files (`git add -A`) before `just init`.
    """
    shutil.copytree(
        _FRONTEND_TEMPLATE_DIR, package_path / 'frontend', dirs_exist_ok=True
    )
    _append_frontend_recipes(package_path / 'Justfile')


def _inject_templates(package_path: Path, *, fullstack: bool) -> None:
    """Copy backend and optionally frontend templates into the clone, then stage.

    Always injects the backend (callers guard with `if backend or fullstack`).
    Additionally injects the frontend when `fullstack=True`. Stages all injected
    files with `git add -A` so `just init`'s rename sed sees them.
    """
    _add_backend(package_path)
    if fullstack:
        _add_frontend(package_path)
    _stage_injected_files(package_path)


def _add_backend(package_path: Path) -> None:
    """Copy the FastAPI backend template into a generated package and wire its deps.

    Copies `_BACKEND_TEMPLATE_DIR` over the clone (merging into existing
    `modernpackage/` and `tests/`), then appends backend runtime/dev dependencies
    to the cloned pyproject.toml and migration recipes to the Justfile. Copied
    files carry the literal `modernpackage` token so `just init`'s rename sed
    rewrites their imports. Callers stage the copied files (`git add -A`) before
    `just init` so `git grep` sees them.
    """
    shutil.copytree(_BACKEND_TEMPLATE_DIR, package_path, dirs_exist_ok=True)
    _append_backend_dependencies(package_path / 'pyproject.toml')
    _append_backend_recipes(package_path / 'Justfile')


def _compile_and_sync_package(package_path: Path, module_name: str) -> bool:
    """Run `just compile` then `just sync` on the scaffolded package.

    Inherits the parent's stdout/stderr (no PIPE) so both steps stream their
    progress live, matching the `just check` rationale. Returns True on success;
    on a non-zero exit prints a failure notice to stderr and returns False.
    """
    for target in ('compile', 'sync'):
        print(flush=True)  # noqa: T201
        print(  # noqa: T201
            f'Running just {target} in {module_name}…',
            flush=True,
        )
        pipe = Popen(  # noqa: S603
            ['just', target],  # noqa: S607
            stdin=PIPE,
            cwd=package_path,
        )
        pipe.communicate()
        if pipe.returncode != 0:
            print(  # noqa: T201
                f'just {target} failed with exit code {pipe.returncode}'
                f' — see the {target} output above.',
                file=sys.stderr,
            )
            return False
    return True


def init_new_package(  # noqa: PLR0913
    package_name: str,
    *,
    author_name: str | None = None,
    author_email: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
    repository_url: str | None = None,
    dry_run: bool = False,
    backend: bool = False,
    fullstack: bool = False,
) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name

    if dry_run:
        _print_dry_run_plan(
            module_name,
            new_package_path,
            author_name=author_name,
            author_email=author_email,
            description=description,
            package_license=package_license,
            repository_url=repository_url,
            backend=backend,
            fullstack=fullstack,
        )
        return 0

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

    _strip_scaffolding(new_package_path, package_name)

    if backend or fullstack:
        _inject_templates(new_package_path, fullstack=fullstack)

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

    # Regenerate the lockfile and sync dependencies before checking, so `just
    # check` runs against a fresh lockfile and an up-to-date virtual environment.
    if not _compile_and_sync_package(new_package_path, module_name):
        return 1

    # Inherit the parent's stdout/stderr (no PIPE) so `just check` streams its
    # progress live — the chained ruff/mypy/pytest/pip-audit steps are slow and a
    # silent capture makes the CLI look hung. The header gives that output context;
    # flush=True keeps it ordered ahead of the child's direct-to-fd writes.
    print(flush=True)  # noqa: T201
    print(  # noqa: T201
        f'Running just check in {module_name} (this can take a while)…',
        flush=True,
    )
    pipe = Popen(
        ['just', 'check'],  # noqa: S607
        stdin=PIPE,
        cwd=new_package_path,
    )
    pipe.communicate()

    if pipe.returncode == 0:
        print(  # noqa: T201
            f'just check {_green("passed")} — '
            f'{module_name} scaffold is {_green("valid")}.'
        )
        print()  # noqa: T201
        _print_init_summary(package_name, new_package_path)
        print()  # noqa: T201
        _print_next_commands(module_name)
        return 0
    print(  # noqa: T201
        f'just check failed with exit code {pipe.returncode}'
        ' — see the check output above.',
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
                dry_run=parsed_args.dry_run,
                backend=parsed_args.backend,
                fullstack=parsed_args.fullstack,
            )
        except RuntimeError as error:
            print(error, file=sys.stderr)  # noqa: T201
            return 1

    return 0
