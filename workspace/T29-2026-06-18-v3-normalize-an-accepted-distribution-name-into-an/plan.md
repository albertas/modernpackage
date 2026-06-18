# Implementation Plan

## Overview
Add a pure helper `normalize_module_name(value: str) -> str` that converts a
validated distribution name (e.g. `my-cool.package`) into an import-safe Python
module identifier (`my_cool_package`) by replacing `.` and `-` with `_`, then
derive `module_name` once in `init_new_package` and use it for the clone
destination directory, the `just init` argument, and the print messages.
`validate_package_name` and the `Justfile` are left unchanged.

---

## Phase 1: `normalize_module_name` helper + unit tests

Adds the pure transform that converts a validated distribution name into an
import-safe Python module identifier. No call sites yet; fully unit-testable in
isolation.

### Changes

#### 1. New helper in `main.py`
**File**: `modernpackage/main.py`
**Action**: modify (add one function)

Add the helper directly after `validate_package_name` (after `main.py:69`),
keeping the validate-and-passthrough validator above the transform. Use a
chained `str.replace()` per Decision 4 (fixed two-character substitution; a
regex constant adds ceremony without value). Mirror the
`humanize_git_clone_error` shape (`main.py:47-53`): typed signature, one-line
docstring stating the return contract, no side effects.

```python
def normalize_module_name(value: str) -> str:
    """Return an import-safe module name: `.` and `-` replaced by `_`.

    Input is already validated by `validate_package_name`, so this never
    returns None. `_` is preserved; case is unchanged. Leading-digit names
    (e.g. `9lives`) and Python keywords (e.g. `class`) remain invalid module
    names — out of scope (see plan Open Risks / design Open Risks).
    """
    return value.replace('.', '_').replace('-', '_')
```

Notes:
- Do **not** lowercase (Decision 1) — uppercase is already a valid Python
  identifier; lowercasing is style, not import-safety.
- Do **not** collapse runs (`a--b` → `a__b`, not `a_b`) — design "What We're
  NOT Doing"; runs of `_` are valid identifiers.
- No regex constant is introduced. (If a future change prefers a regex, it must
  be named `_MODULE_NAME_SEPARATOR_RE` and annotated `re.Pattern[str]` per the
  `main.py:58` convention.)

#### 2. New unit test
**File**: `tests/test_main.py`
**Action**: modify (add import + one test)

Add `normalize_module_name` to the existing import block (`test_main.py:8-14`):

```python
from modernpackage.main import (
    humanize_git_clone_error,
    init_new_package,
    main,
    normalize_module_name,
    parse_args,
    validate_package_name,
)
```

Add a test using the input/expected loop style of
`test_validate_package_name_valid` (`test_main.py:28-33`). Place it next to
that test:

```python
def test_normalize_module_name() -> None:
    cases = {
        'my-cool.package': 'my_cool_package',
        'my_package': 'my_package',
        'a': 'a',
        'my-cool_pkg.v2': 'my_cool_pkg_v2',
        'a--b': 'a__b',  # runs are preserved, not collapsed (design intent)
    }
    for value, expected in cases.items():
        assert normalize_module_name(value) == expected
```

### Verification
#### Automated
- [x] `just test tests/test_main.py::test_normalize_module_name` passes
- [x] `just lint` passes (no new lint violations)
- [x] `just typecheck` passes

#### Manual
- [x] Import-clean check:
  `uv run python -c "from modernpackage.main import normalize_module_name as n; assert n('my-cool.package')=='my_cool_package'; assert n('my_package')=='my_package'; assert n('a--b')=='a__b'; print('ok')"`
  → prints `ok`
- [x] Confirm no call sites changed yet (validator/`init_new_package` still use
  raw name): `grep -n "normalize_module_name" modernpackage/main.py` → shows
  only the function definition, not a call inside `init_new_package`

---

## Phase 2: Wire the module name into `init_new_package` (+ tests)

Derives the normalized name once inside `init_new_package` and uses it for the
clone destination directory, the `just init` argument, and both print messages,
so the scaffolded source directory and all generated `import` paths are valid
Python. Validator and Justfile untouched.

### Changes

#### 1. Use the module name in `init_new_package`
**File**: `modernpackage/main.py`
**Action**: modify

Add the derivation as the first line of the function body and replace the four
downstream uses of `package_name`. Signature is unchanged (`package_name`
remains the raw user input the caller passes).

`main.py:91-93` — add derivation, change destination dir:

```python
def init_new_package(package_name: str) -> int:
    """Clone modernpackage files into `package_name` and run `just init` in it."""
    module_name = normalize_module_name(package_name)
    new_package_path = Path.cwd() / module_name
```

`main.py:112` — pass the module name to `just init`:

```python
            ['just', 'init', module_name],  # noqa: S607
```

`main.py:141` — success message:

```python
        print(f'just check passed — {module_name} scaffold is valid.')  # noqa: T201
```

`main.py:143-146` — failure message:

```python
    print(  # noqa: T201
        f'just check failed with exit code {pipe.returncode}'
        f' — review the output in {module_name}.',
        file=sys.stderr,
    )
```

The `['git', 'clone', ..., new_package_path]` target (`main.py:96`) and
`cwd=new_package_path` (`main.py:116`, `:136`) now resolve through
`module_name` automatically because `new_package_path` is derived from it. No
other edits.

#### 2. New unit test for normalization wiring
**File**: `tests/test_main.py`
**Action**: modify (add one test)

Patch `Popen` on the module object (`patch('modernpackage.main.Popen')`),
following the `side_effect` / `return_value` style of
`test_init_new_package_runs_just_check` (`test_main.py:62-69`). Call with a
`-`/`.` input and assert the clone target ends with `my_cool_package` and the
`just init` arg list is `['just', 'init', 'my_cool_package']`.

```python
def test_init_new_package_normalizes_name() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('my-cool.package')

    clone_call = popen_mock.call_args_list[0]
    clone_target = clone_call.args[0][-1]
    assert Path(clone_target).name == 'my_cool_package'

    init_call = popen_mock.call_args_list[1]
    assert init_call.args[0] == ['just', 'init', 'my_cool_package']
    assert init_call.kwargs['cwd'] == Path.cwd() / 'my_cool_package'
```

#### 3. e2e normalization regression guard
**File**: `tests/test_e2e.py`
**Action**: modify

Close the e2e coverage gap (design Open Risks) by proving a `-`/`.` input yields
an underscore source directory. The existing e2e
(`test_scaffolded_package_passes_check`, `test_e2e.py:50-74`) replicates the
clone + `just init` flow against the local checkout directly (it does not call
`init_new_package`), so it must apply `normalize_module_name` itself to mirror
production behavior.

Change the existing test to scaffold from a name containing `-` and `.`, derive
the module name, and assert the created source directory uses underscores.
Import the helper and update `package_name` / `destination` / the `just init`
arg / the `__init__.py` path:

```python
from modernpackage.main import normalize_module_name
```

```python
    package_name = 'scaffold-check.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    source_dir = destination / module_name
    assert source_dir.is_dir()
    assert '-' not in module_name and '.' not in module_name
    assert '_' in module_name

    init_file = source_dir / '__init__.py'
    assert init_file.exists()
    assert '0.0.1' in init_file.read_text()

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'
```

Assumption (noted per Process step 4): the e2e is *modified in place* rather
than duplicated, because the design says "extend it (or add a unit assertion)"
and the existing test only exercised an all-lowercase-alpha name; a `-`/`.`
input is a strict superset of the prior coverage (still all-lowercase, still
passes `just check`) and avoids a second multi-minute networked e2e run.

### Verification
#### Automated
- [x] `just test` passes (new `test_init_new_package_normalizes_name`, all
  existing `init_new_package` tests, and
  `test_validate_package_name_valid` identity assertions stay green)
- [ ] `just test-e2e` passes (requires `git`/`just`/`uv` on PATH + network;
  skips otherwise)
- [x] `just check` passes end-to-end (check-format, check-lint,
  check-complexity ≤10, check-typecheck, test, audit)

#### Manual
- [x] Mocked normalization assertion:
  `just test tests/test_main.py::test_init_new_package_normalizes_name` → passes
- [x] Source-dir name matches the module pattern after wiring — confirm the
  derived directory is `^[a-z0-9_]+$`:
  `uv run python -c "import re; from modernpackage.main import normalize_module_name as n; assert re.fullmatch(r'[a-z0-9_]+', n('scaffold-check.pkg')); print('ok')"`
  → prints `ok`
- [x] Validator unchanged — identity return preserved:
  `uv run python -c "from modernpackage.main import validate_package_name as v; assert v('my-cool.package')=='my-cool.package'; print('ok')"`
  → prints `ok`
- [x] Justfile untouched:
  `git diff --stat Justfile` → no output (no changes)

---

## Testing Checkpoints

- **After Phase 1**: `normalize_module_name` exists and is correct in isolation;
  the four design-specified mappings plus the `a--b → a__b` run case pass. No
  call sites changed yet — `init_new_package` still uses the raw name, so the
  rest of the suite is unaffected. Independently shippable.
- **After Phase 2**: `init_new_package` uses the normalized name for the clone
  dir, `just init` arg, and both messages. Mocked-`Popen` unit test confirms a
  `-`/`.` input produces an underscore directory and `just init` arg; e2e
  confirms the same end-to-end. `validate_package_name` identity-return tests
  (`test_main.py:28-33`) remain green (validator untouched). `just check` green.
- **Out of scope (flagged, not fixed)**: leading-digit names (`9lives`) and
  Python-keyword names (`class`) still yield invalid module names; the Justfile
  and `_PACKAGE_NAME_RE` are unchanged.

## Open Risks (carried from design — not addressed here)

- **Leading-digit names** (`9lives`): `import 9lives` is a `SyntaxError`;
  separator replacement does not fix it. Out of scope; flagged in the helper
  docstring.
- **Python keyword names** (`class`, `import`): PyPI-valid but unusable as
  module names. Same status; flagged in the helper docstring.
- **Display divergence**: a user who typed `my-cool.package` sees a directory
  named `my_cool_package`. Accepted per Decision 2 (PEP 503-equivalent,
  predictable).
