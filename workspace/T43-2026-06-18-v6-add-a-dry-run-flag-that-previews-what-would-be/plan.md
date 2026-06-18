# Implementation Plan

## Overview

Add a `--dry-run` boolean flag (modeled on `--version`) that runs the existing
read-only preflight, then short-circuits `init_new_package` **before the first
mutation** (`git clone`, `main.py:617`): it prints a high-level plan to stdout
and returns 0 without cloning, rewriting metadata, or invoking any scaffolding
subprocess.

Two phases: (1) wire the flag end-to-end so the safe abort path works with a
minimal plan; (2) replace the minimal plan with a complete, stable preview.

## Phase 1: Wire `--dry-run` end-to-end (flag → abort path)

### Changes

#### 1. Add the `--dry-run` flag to `parse_args`
**File**: `modernpackage/main.py`
**Action**: modify

Add a `store_true` argument modeled exactly on `--version` (`main.py:350-356`).
Place it immediately after the `--version` block, before the `package_name`
positional (`main.py:357`):

```python
    parser.add_argument(
        '--dry-run',
        help='Preview what scaffolding would do without making any changes.',
        action='store_true',
        default=False,
    )
```

The hyphenated name maps to the `arguments.dry_run` attribute automatically.
No change to `_resolve_metadata_defaults` (dry_run is not a metadata field).

#### 2. Add the `dry_run` keyword-only parameter to `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify

Append a defaulted keyword-only parameter to the existing signature
(`main.py:602-610`):

```python
def init_new_package(  # noqa: PLR0913
    package_name: str,
    *,
    author_name: str | None = None,
    author_email: str | None = None,
    description: str | None = None,
    package_license: str | None = None,
    repository_url: str | None = None,
    dry_run: bool = False,
) -> int:
```

> Note: the signature already carries `# noqa: PLR0913` (too-many-arguments);
> adding one more argument keeps that suppression valid — do not remove it.

#### 3. Branch on `dry_run` after preflight, before the clone
**File**: `modernpackage/main.py`
**Action**: modify

Insert the short-circuit between `_run_preflight_checks(...)` (`main.py:615`)
and the `Popen(['git', 'clone', ...])` (`main.py:617`). Phase 1 uses a minimal
inline plan (replaced in Phase 2):

```python
    _run_preflight_checks(new_package_path)

    if dry_run:
        print(  # noqa: T201
            f'Dry run — would scaffold {module_name} at {new_package_path}.'
        )
        return 0

    pipe = Popen(  # noqa: S603
        ['git', 'clone', _TEMPLATE_REPOSITORY_URL, new_package_path],  # noqa: S607
        ...
```

#### 4. Thread `dry_run` from `main` into `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify

Pass the flag in the existing keyword call (`main.py:691-698`):

```python
            return init_new_package(
                package_name=parsed_args.package_name,
                author_name=parsed_args.author_name,
                author_email=parsed_args.author_email,
                description=parsed_args.description,
                package_license=parsed_args.license,
                repository_url=parsed_args.repository_url,
                dry_run=parsed_args.dry_run,
            )
```

#### 5. Update the existing `main` threading test (breaking change)
**File**: `tests/test_main.py`
**Action**: modify

`test_main_with_package_name` (`test_main.py:502-525`) asserts the exact kwargs
via `init_mock.assert_called_once_with(...)`. Adding `dry_run` to the call in
`main` breaks this test, so it must be updated. Set the mock attribute and add
the kwarg to the assertion:

```python
        argparse_mock().parse_args().repository_url = None
        argparse_mock().parse_args().dry_run = False
        init_mock.return_value = 0
        result = main()
    init_mock.assert_called_once_with(
        package_name='mypackage',
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
        dry_run=False,
    )
```

> Deviation note: structure.md does not call this out explicitly, but the
> existing `assert_called_once_with` is exact and will fail once `dry_run` is
> added to the call. Updating it is mandatory, not optional.

#### 6. Add Phase 1 unit tests
**File**: `tests/test_main.py`
**Action**: modify (add new test functions)

Add near the other `init_new_package` tests (after `test_main.py:294`). Mirror
the `Popen`/`run` patch seam (`test_main.py:286-294`) and the abort assertion
(`test_main.py:385`):

```python
def test_init_new_package_dry_run_performs_no_subprocess() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        result = init_new_package('mypackage', dry_run=True)
    assert result == 0
    assert popen_mock.call_count == 0
```

> Note: `run` is still patched because preflight's `git ls-remote` probe
> (`main.py:546-552`) runs during a dry-run (design Decision 2). `popen_mock`
> must be 0 — no clone/init/check.

Add a `parse_args` test mirroring `test_parse_args_version_flag`
(`test_main.py:108-118`), with a default-off counterpart:

```python
def test_parse_args_dry_run_flag() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--dry-run']):
        result = parse_args()
    assert result.dry_run is True


def test_parse_args_dry_run_defaults_false() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.dry_run is False
```

Add a `main`-threading test mirroring `test_main_with_package_name`
(`test_main.py:502-525`) that asserts `dry_run=True` reaches the call:

```python
def test_main_threads_dry_run() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        argparse_mock().parse_args().author_name = None
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().description = None
        argparse_mock().parse_args().license = None
        argparse_mock().parse_args().repository_url = None
        argparse_mock().parse_args().dry_run = True
        init_mock.return_value = 0
        result = main()
    assert init_mock.call_args.kwargs['dry_run'] is True
    assert result == 0
```

### Verification

#### Automated
- [x] `just check` passes (format, lint, complexity, typecheck, test, audit).
- [x] `just test` passes.
- [x] `just test tests/test_main.py::test_init_new_package_dry_run_performs_no_subprocess` passes.
- [x] `just test tests/test_main.py::test_parse_args_dry_run_flag tests/test_main.py::test_parse_args_dry_run_defaults_false` passes.
- [x] `just test tests/test_main.py::test_main_threads_dry_run tests/test_main.py::test_main_with_package_name` passes (confirms the updated existing test still green).

#### Manual
- [x] `grep -q "action='store_true'" modernpackage/main.py && grep -q "'--dry-run'" modernpackage/main.py` → both present (flag defined).
- [x] `grep -q 'dry_run: bool = False' modernpackage/main.py` → signature param present.
- [x] `grep -q 'dry_run=parsed_args.dry_run' modernpackage/main.py` → flag threaded from `main`.
- [ ] Run a real dry-run and confirm no directory is created:
  `python -c "import sys; sys.argv=['modernpackage','dryruntmp','--dry-run']; from modernpackage.main import main; raise SystemExit(main())"; echo "exit=$?"; test ! -e dryruntmp && echo "NO DIR CREATED"`
  → expect `exit=0` and `NO DIR CREATED` (requires git/just/uv on PATH and network for the `ls-remote` probe; if offline this returns 1 by design — see inherited risk below).

---

## Phase 2: Full preview plan content

### Changes

#### 1. Add the dry-run header constant
**File**: `modernpackage/main.py`
**Action**: modify

Add alongside `_PREFLIGHT_HEADER` (`main.py:504`):

```python
_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'
```

#### 2. Add `_format_dry_run_plan`
**File**: `modernpackage/main.py`
**Action**: create (new private helper)

Place near `_format_check_line` (`main.py:507-510`), reusing its two-space
indent aesthetic. Reports only what the code knows (design Decision 3): the
target directory, the template URL it would clone, the per-field metadata
substitutions (each non-`None` field; `None` → "keeps template default"), and
the well-known `just init` outcomes (rename + version reset to `0.0.1`):

```python
def _format_dry_run_plan(  # noqa: PLR0913
    module_name: str,
    target_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
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
    lines.append('  run just init: reset version to 0.0.1')
    return '\n'.join(lines)
```

#### 3. Add `_print_dry_run_plan`
**File**: `modernpackage/main.py`
**Action**: create (new private helper)

```python
def _print_dry_run_plan(  # noqa: PLR0913
    module_name: str,
    target_path: Path,
    *,
    author_name: str | None,
    author_email: str | None,
    description: str | None,
    package_license: str | None,
    repository_url: str | None,
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
        )
    )
```

#### 4. Replace the Phase 1 inline plan with the helper call
**File**: `modernpackage/main.py`
**Action**: modify

Replace the minimal `if dry_run:` body from Phase 1 (change #3) with:

```python
    if dry_run:
        _print_dry_run_plan(
            module_name,
            new_package_path,
            author_name=author_name,
            author_email=author_email,
            description=description,
            package_license=package_license,
            repository_url=repository_url,
        )
        return 0
```

#### 5. Add Phase 2 unit tests
**File**: `tests/test_main.py`
**Action**: modify (add new test functions)

A direct test of the formatter (import `_format_dry_run_plan` from
`modernpackage.main`):

```python
def test_format_dry_run_plan_reports_known_actions() -> None:
    plan = _format_dry_run_plan(
        'foo',
        Path('/tmp/foo'),
        author_name='Ada Lovelace',
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert '/tmp/foo' in plan
    assert 'https://github.com/albertas/modernpackage' in plan
    assert 'Ada Lovelace' in plan
    assert 'keeps template default' in plan
    assert 'modernpackage/ -> foo/' in plan
    assert '0.0.1' in plan
```

A `capsys`-based test on the full dry-run path (own test, not coupled to the
exact-stdout assertions at `test_main.py:641-665`):

```python
def test_init_new_package_dry_run_prints_plan(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.run') as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stderr='')
        result = init_new_package('foo', dry_run=True, author_name='Ada')
    assert result == 0
    assert popen_mock.call_count == 0
    captured = capsys.readouterr()
    assert 'Dry run — no changes will be made:' in captured.out
    assert 'Ada' in captured.out
```

> Add `_format_dry_run_plan` to the existing `from modernpackage.main import ...`
> import block in `tests/test_main.py` (private symbols are imported directly,
> per Code Best Practices).

### Verification

#### Automated
- [x] `just check` passes.
- [x] `just test tests/test_main.py::test_format_dry_run_plan_reports_known_actions` passes.
- [x] `just test tests/test_main.py::test_init_new_package_dry_run_prints_plan` passes.

#### Manual
- [x] `grep -q "_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'" modernpackage/main.py` → header constant present.
- [x] `grep -q 'def _format_dry_run_plan' modernpackage/main.py && grep -q 'def _print_dry_run_plan' modernpackage/main.py` → both helpers present.
- [ ] Run a dry-run with a metadata flag and confirm the plan content + no directory:
  `python -c "import sys; sys.argv=['modernpackage','dryruntmp2','--dry-run','--author-name','Ada']; from modernpackage.main import main; raise SystemExit(main())" | tee /tmp/dryrun.out; echo "exit=$?"; grep -q 'Dry run — no changes will be made:' /tmp/dryrun.out && grep -q 'Ada' /tmp/dryrun.out && grep -q 'modernpackage/ -> dryruntmp2/' /tmp/dryrun.out && test ! -e dryruntmp2 && echo "PLAN OK, NO DIR"`
  → expect `exit=0` and `PLAN OK, NO DIR` (requires git/just/uv on PATH and network for the `ls-remote` probe).

---

## Testing Checkpoints

- **After Phase 1**: `modernpackage foo --dry-run` returns 0 and performs no
  clone/init/check (`popen_mock.call_count == 0`); `parse_args` exposes
  `dry_run` (default `False`); `main` threads it. The existing
  `test_main_with_package_name` is updated for the new kwarg. Preflight still
  runs — preflight failures still return 1 via the existing `RuntimeError` path
  in `main` (`main.py:699-701`). `just check` green. The safety guarantee (no
  mutation) holds independently of plan content.
- **After Phase 2**: stdout shows a complete, stable plan — target dir, template
  URL, per-field metadata substitutions (with `None` → template default), and
  the rename + version-reset outcomes — covered by its own dedicated tests.
  `just check` green.

## Inherited Risk (design Open Risks)

Dry-run still issues the `git ls-remote` network probe via preflight
(`main.py:546-552`). This is **by design** (Decision 2) — it surfaces a
genuinely unreachable remote — but means a fully unattended/offline live
invocation returns 1, not 0. The primary verification gates are therefore the
unit tests with `run`/`Popen` patched, not the live network probe; the manual
live-run checks above assume network availability.
