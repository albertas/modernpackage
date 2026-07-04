# Implementation Plan

## Overview

Add ~15 lines of stdlib ANSI helpers to `modernpackage/main.py` so that, on an
interactive terminal, the affirmative `[ok]` marker and the words
`passed`/`valid` render green and init sections are separated by blank lines —
while non-TTY output (pipes, redirects, pytest `capsys`) stays byte-for-byte
identical so every existing exact-string test passes unchanged.

**Project conventions that constrain this work** (from `research.md` / `design.md`):
- No runtime dependency may be added (`pyproject.toml:18` `dependencies = []`).
  Use only stdlib; `os` and `sys` are already imported (`main.py:3,6`).
- Every `print` needs `# noqa: T201` (`ruff select = ["ALL"]`, `pyproject.toml:68`).
- Single quotes, line-length **88** (`pyproject.toml`), mypy `strict`.
- Verification commands: `just check` (format+lint+complexity+typecheck+test+audit)
  and `just test`. Coverage gate `--cov-fail-under=95.0` (`pyproject.toml:40`).

---

## Phase 1: Color primitives + green `[ok]` marker

Establish the ANSI helpers and apply them to the first affirmative token: the
preflight `[ok]` marker turns green on a TTY while alignment and plain-text
output are preserved.

### Changes

#### 1. Color constants and helpers
**File**: `modernpackage/main.py`
**Action**: modify — add three module-level constants and two helpers directly
after the header constants block (after `_NEXT_COMMANDS_HEADER`, `main.py:680`,
before `_format_check_line` at `main.py:683`).

```python
_ANSI_GREEN: str = '\033[32m'
_ANSI_RESET: str = '\033[0m'


def _color_enabled() -> bool:
    """Return True when stdout is an interactive TTY and NO_COLOR is unset.

    Probes the environment/TTY at a process boundary; never raises — degrades to
    plain text (graceful boundary style, main.py:895-902).
    """
    return sys.stdout.isatty() and os.environ.get('NO_COLOR') is None


def _green(text: str) -> str:
    """Wrap `text` in ANSI green/reset when color is enabled, else return as-is."""
    if _color_enabled():
        return f'{_ANSI_GREEN}{text}{_ANSI_RESET}'
    return text
```

Notes / assumptions:
- `NO_COLOR` follows the community standard: any value (including empty string)
  disables color, hence `is None` rather than a truthiness check. The structure's
  test case (`NO_COLOR=''` set → no `\033`) confirms empty-string must disable.
- `sys.stdout.isatty()` on a normal file object does not raise; if a replaced
  stdout lacked `isatty`, that is out of scope (design Decision 2 relies on the
  real stdout). No try/except is added — keep it minimal per CLAUDE.md §2.

#### 2. Color the `[ok]` marker while preserving alignment
**File**: `modernpackage/main.py`
**Action**: modify `_format_check_line` (`main.py:683-686`).

```python
def _format_check_line(label: str, *, ok: bool) -> str:
    """Return one indented checklist line; marker padded to 6 chars so labels align."""
    marker = '[ok]' if ok else '[FAIL]'
    field = f'{marker:<6}'
    if ok:
        field = _green(field)
    return f'  {field} {label}'
```

- Padding (`:<6`) is computed on the plain marker **before** wrapping, so column
  alignment is measured on visible width, not escape codes (design Decision 3).
- `[FAIL]` stays uncolored (affirmative-only scope, design Decision 7).
- Under non-TTY, `_green(field)` returns `field` unchanged → output is
  byte-identical to `f'  {marker:<6} {label}'`, so `test_main.py:742-746,830,850`
  still match.

#### 3. New unit tests
**File**: `tests/test_main.py`
**Action**: modify — import the new symbols and add tests. Import `main` as a
module object for monkeypatching the SDK/stdout seam, and add `_format_check_line`
to the symbol imports (it is currently untested directly).

Add to the existing `from modernpackage.main import (...)` block:
```python
    _color_enabled,
    _format_check_line,
    _green,
```
Also ensure `from modernpackage import main` (module handle) is available for
`monkeypatch.setattr(main.sys.stdout, 'isatty', ...)`. If not already imported,
add `from modernpackage import main`.

New tests:
```python
def test_green_wraps_when_tty(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert _green('x') == '\033[32mx\033[0m'


def test_green_noop_when_not_tty(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert _green('x') == 'x'


def test_green_noop_when_no_color_set(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)
    monkeypatch.setenv('NO_COLOR', '')
    assert _green('x') == 'x'
    assert _color_enabled() is False


def test_check_line_ok_is_green_on_tty(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    line = _format_check_line('package name valid', ok=True)
    assert '\033[32m' in line
    assert '\033[0m' in line


def test_check_line_ok_is_plain_off_tty(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: False)
    line = _format_check_line('package name valid', ok=True)
    assert line == '  [ok]   package name valid'
    assert '\033' not in line


def test_check_line_fail_is_never_green(monkeypatch):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    line = _format_check_line('template remote reachable', ok=False)
    assert '\033' not in line
```

These cover both branches of `_green` and `_color_enabled` (≥95% gate).

### Verification
#### Automated
- [x] `just check` passes (proves existing exact-line preflight tests
  `test_main.py:742-746,830,850` still match under non-TTY `capsys`).
- [x] `just test` passes; coverage stays ≥95% (`pyproject.toml:40`) with both
  color branches covered. (98.39% coverage.)

#### Manual
- [x] `python -c "from modernpackage.main import _green; import sys; print(repr(_green('x')))" | cat`
  → prints `'x'` (non-TTY, no escapes).
- [x] `grep -q "_ANSI_GREEN: str = '\\\\033\[32m'" modernpackage/main.py` → exit 0.
- [x] `grep -q "def _color_enabled() -> bool:" modernpackage/main.py` → exit 0.

---

## Phase 2: Green `passed` / `valid` in the success line

Reuse the Phase 1 helpers to color the two affirmative words in the
`just check passed …` success line, keeping sentence structure identical.

### Changes

#### 1. Wrap `passed` and `valid`
**File**: `modernpackage/main.py`
**Action**: modify the success line (`main.py:1109`).

```python
        print(  # noqa: T201
            f'just check {_green("passed")} — '
            f'{module_name} scaffold is {_green("valid")}.'
        )
```

- Split across two f-strings to stay under line-length 88; keep `# noqa: T201`.
- Under non-TTY, `_green` is a no-op → the line collapses to
  `just check passed — {module_name} scaffold is valid.`, so the
  `'just check passed' in call` substring assertions (`test_main.py:687,718`)
  still hold.
- Assumption: double quotes inside the f-string args (`_green("passed")`) are
  required because the f-string uses single quotes; ruff's `inline-quotes` rule
  permits the alternate quote inside an f-string expression. If ruff flags it,
  fall back to assigning `passed = _green('passed')` / `valid = _green('valid')`
  on prior lines and interpolating those names.

#### 2. New unit test
**File**: `tests/test_main.py`
**Action**: modify — add a test that forces a TTY and inspects the emitted line.
This exercises the success branch of `init_new_package` (`main.py:1108-1112`)
with mocked `Popen`, mirroring the existing `test_init_new_package_*` setup
(git clone / just init / just check all returncode 0).

```python
def test_success_line_words_are_green_on_tty(monkeypatch, capsys):
    monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    line = (
        f'just check {main._green("passed")} — '
        f'demo scaffold is {main._green("valid")}.'
    )
    assert '\033[32mpassed\033[0m' in line
    assert '\033[32mvalid\033[0m' in line
```

Assumption: rather than re-mock the whole `init_new_package` Popen chain under a
forced TTY (which would also color `[ok]` lines and risk coupling to other
assertions), assert the composed string directly via `main._green`. This keeps
the test focused on the Phase 2 change and avoids duplicating the large mock
fixture. If a full end-to-end assertion is preferred, reuse the mock setup from
`test_init_new_package_reports_check_failed` (`test_main.py:755+`) with
`just_check_mock.returncode = 0` and assert `'\033[32mpassed\033[0m' in
capsys.readouterr().out`.

### Verification
#### Automated
- [x] `just check` passes (integration asserts `'just check passed' in call`,
  `test_main.py:687,718`, still hold under `capsys`).
- [x] `just test` passes.

#### Manual
- [x] `grep -q '_green("passed")' modernpackage/main.py` → exit 0.
- [x] `grep -q '_green("valid")' modernpackage/main.py` → exit 0.
- [x] `python -c "from modernpackage import main; import sys; sys.stdout.isatty=lambda: True; print('\033[32mpassed\033[0m' in (f'just check {main._green(chr(34)) }'.replace(chr(34),'passed')))"`
  — (optional) or simply confirm the two greps above.

---

## Phase 3: Blank-line separators between init sections

Add blank lines at init happy-path section boundaries so the terminal is easy to
scan, without touching the order-checked check-line block or any builder.

### Changes

#### 1. Blank line before the `just check` progress line
**File**: `modernpackage/main.py`
**Action**: modify — insert a bare separator `print(flush=True)` immediately
before the progress-line print (`main.py:1097`). In the happy path the last
visible output before this point is the final preflight line (git clone and
metadata steps are PIPE-captured / silent), so this produces the blank line
between the last preflight line and the progress line.

```python
    print(flush=True)  # noqa: T201
    print(  # noqa: T201
        f'Running just check in {module_name} (this can take a while)…',
        flush=True,
    )
```

- `flush=True` keeps the blank ordered ahead of `just check`'s direct-to-fd
  writes (design Open Risk / Decision 5; mirrors `main.py:1099`).
- Placed in the non-dry-run path (after git clone, before progress line) so
  dry-run output is untouched.

#### 2. Blank lines between passed-line / summary / next-steps
**File**: `modernpackage/main.py`
**Action**: modify the success block (`main.py:1108-1112`).

```python
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
```

- No `flush=True` needed here — `just check` has already completed
  (`pipe.communicate()` returned).
- `_format_*` builders are **not** changed — they keep returning blank-free
  strings (design Decision 5). No blank line is inserted inside the four
  consecutive `[ok]` lines (order-checked, `test_main.py:749-751`).

#### 3. New test asserting blank separators
**File**: `tests/test_main.py`
**Action**: modify — add a test on captured init output. Reuse the existing
happy-path mock pattern (all of git clone / just init / just check returncode 0,
as in `test_main.py:730-752`).

```python
def test_init_output_has_blank_separators(capsys):
    # ... same Popen/run mock setup as the four-[ok]-lines test (test_main.py:730) ...
    # git clone, just init, just check all returncode 0, communicate -> (b'', b'')
    init_new_package('mypackage')
    lines = capsys.readouterr().out.split('\n')

    # blank line between the last preflight line and the progress line
    last_preflight = max(
        i for i, line in enumerate(lines)
        if 'template remote reachable' in line
    )
    progress = next(
        i for i, line in enumerate(lines) if 'Running just check' in line
    )
    assert '' in lines[last_preflight + 1:progress]

    # blank line between the passed-line and the summary header
    passed = next(i for i, line in enumerate(lines) if 'just check passed' in line)
    summary = next(
        i for i, line in enumerate(lines) if line == _INIT_SUMMARY_HEADER
    )
    assert '' in lines[passed + 1:summary]
```

Add `_INIT_SUMMARY_HEADER` to the imports from `modernpackage.main` if not
already imported. Under `capsys` (non-TTY) the `[ok]`/`passed`/`valid` tokens are
plain, so the substring lookups work without escape-code handling.

Assumption: the single `just check passed` mock path must exercise
`returncode == 0` for both `just init` and `just check`. Model the mock exactly
on the existing success-path test so `Popen` returns the right sequence of mocks
(git clone → just init → just check).

### Verification
#### Automated
- [x] `just check` passes (four-`[ok]`-lines-consecutive test
  `test_main.py:749-751` and substring integration tests unchanged).
- [x] `just test` passes.

#### Manual
- [x] `grep -q '^    print(flush=True)  # noqa: T201$' modernpackage/main.py`
  → exit 0 (separator before progress line present).
- [x] `grep -cq 'print()  # noqa: T201' modernpackage/main.py` — confirm the two
  bare separators in the success block exist:
  `test $(grep -c 'print()  # noqa: T201' modernpackage/main.py) -ge 2`.

---

## Whole-feature verification

#### Automated
- [ ] `just check` passes end-to-end (format, lint, complexity ≤8, mypy strict,
  tests, audit) with no modifications to any pre-existing test.
- [ ] `just test` reports coverage ≥95%.

#### Manual
- [ ] Non-TTY emits zero escape bytes:
  `python -m modernpackage init demo-color-check --dry-run | cat | grep -c $'\033'`
  → `0` (dry-run avoids network/clone; exercises the non-TTY color path). If a
  full run is desired in a scratch dir, pipe `| cat` and grep for `$'\033'` → 0.
- [ ] `NO_COLOR` disables color even on a TTY:
  `NO_COLOR=1 python -c "from modernpackage import main; import sys; sys.stdout.isatty=lambda: True; print(repr(main._green('x')))"`
  → `'x'`.
- [ ] Real-terminal spot check (human/agent in an interactive shell): run
  `python -m modernpackage init demo-real --dry-run` in a TTY and confirm no
  crash; for full color, run a real init in a scratch directory and observe the
  green `[ok]`, `passed`, `valid`, and blank-line spacing between sections.

---

## Deviations from the structure outline

- **Phase 2 test**: the structure says "New unit test with `isatty` forced True
  asserts the emitted line contains `'\033[32mpassed\033[0m'`". This plan asserts
  the composed string via `main._green` directly rather than re-mocking the full
  `init_new_package` Popen chain under a forced TTY, to keep the test surgical
  and avoid coupling to the larger mock fixture. An end-to-end variant is noted as
  a fallback.
- **Phase 3 "after the preflight block" separator**: the structure lists both
  "after the preflight block" and "before the progress line" as boundaries. In
  the happy path these coincide (clone/metadata steps are silent), so a single
  `print(flush=True)` before the progress line satisfies the tested boundary
  ("empty string between the last preflight line and the progress line") without
  emitting a spurious blank in the dry-run path. No separate separator is added
  inside `_run_preflight_checks`.
- **Line length**: research notes CLAUDE.md/code-practices mention 120, but this
  repo's `pyproject.toml` sets **88** (authoritative). All snippets above respect
  88.
