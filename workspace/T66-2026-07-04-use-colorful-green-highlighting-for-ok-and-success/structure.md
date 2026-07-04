# Structure Outline

## Approach

Add ~15 lines of stdlib ANSI helpers to `modernpackage/main.py` (no runtime
dependency), gate coloring on `sys.stdout.isatty() and NO_COLOR is unset`, and
apply `_green()` only to affirmative tokens (`[ok]` marker, the words
`passed`/`valid`). Add blank-line separators between init sections via bare
`print()` calls in the orchestration code, never inside `_format_*` builders.
Non-TTY output (pipes, `capsys`) stays byte-for-byte identical so every existing
exact-string test passes unchanged.

The two deliverables (green tokens, blank lines) are independent surfaces. Each
phase below crosses the primitive → builder/orchestration → test layers for one
user-visible slice and is independently valuable if a later phase is dropped.

---

## Phase 1: Color primitives + green `[ok]` marker

Establishes the ANSI helpers and applies them to the first affirmative token:
the preflight `[ok]` marker turns green on a TTY while alignment and plain-text
output are preserved.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_ANSI_GREEN: str = '\033[32m'`, `_ANSI_RESET: str = '\033[0m'` — new
  module-level constants beside `_PREFLIGHT_HEADER` (`main.py:674`).
- `_color_enabled() -> bool` — returns
  `sys.stdout.isatty() and os.environ.get('NO_COLOR') is None`; must never raise.
- `_green(text: str) -> str` — returns `f'{_ANSI_GREEN}{text}{_ANSI_RESET}'`
  when `_color_enabled()` else `text` unchanged.
- `_format_check_line(label, *, ok)` (`main.py:683`) — compute plain padded
  field first (`field = f'{marker:<6}'`), then `field = _green(field)` when `ok`;
  return `f'  {field} {label}'`. Padding measured before escape codes so columns
  stay aligned; `[FAIL]` untouched.

**Verify**: `just check` passes (proves existing exact-line preflight tests
`test_main.py:742-746,830` still match under non-TTY `capsys`). New unit tests:
`monkeypatch.setattr(main.sys.stdout, 'isatty', lambda: True)` →
`_green('x') == '\033[32mx\033[0m'` and `'[ok]' `-wrapped line contains
`'\033[32m'`; with `isatty` False → `_green('x') == 'x'` and check line has no
`'\033'`; with `isatty` True + `NO_COLOR=''` set → no `'\033'`. Run
`just test` and confirm both branches covered (≥95% gate, `pyproject.toml:40`).

---

## Phase 2: Green `passed` / `valid` in the success line

Reuses the Phase 1 helpers to color the two affirmative words in the
`just check passed …` success line, keeping sentence structure identical.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- Success line (`main.py:1109`) — wrap the two tokens:
  `f'just check {_green("passed")} — {module_name} scaffold is {_green("valid")}.'`
  Keep `# noqa: T201`. Substring `'just check passed'` must still appear when
  color is off (it does, since `_green` is a no-op under non-TTY).

**Verify**: `just check` passes (integration asserts `'just check passed' in
call`, `test_main.py:687,718`, still hold under `capsys`). New unit test with
`isatty` forced True asserts the emitted line contains `'\033[32mpassed\033[0m'`
and `'\033[32mvalid\033[0m'`.

---

## Phase 3: Blank-line separators between init sections

Adds blank lines at init happy-path section boundaries so the terminal is easy
to scan, without touching the order-checked check-line block or any builder.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- Bare `print()  # noqa: T201` separators in `init_new_package` /
  `_run_preflight_checks` at boundaries: after the preflight block, before the
  `Running just check …` progress line (use `flush=True` to stay ordered against
  the child's direct-to-fd stream, mirroring `main.py:1099`), and between the
  passed-line / summary / next-steps blocks (`main.py:1108-1111`).
- No change to `_format_*` builders — they keep returning blank-free strings.
- No blank line inserted *inside* the four consecutive `[ok]` lines
  (order-checked, `test_main.py:749-751`).

**Verify**: `just check` passes (four-`[ok]`-lines-consecutive and substring
integration tests unchanged). New test on captured init output
(`capsys.readouterr().out.split('\n')`) asserts an empty string appears between
the last preflight line and the progress line, and between the passed-line and
`_INIT_SUMMARY_HEADER`.

---

## Testing Checkpoints

- **After Phase 1**: `_green` / `_color_enabled` exist and are unit-tested for
  both branches; `[ok]` renders green on a TTY, plain when piped; all pre-existing
  exact-line preflight tests still pass; coverage ≥95%.
- **After Phase 2**: success-line `passed`/`valid` render green on a TTY; the
  `'just check passed'` substring test still matches under `capsys`.
- **After Phase 3**: captured init output shows blank separators at section
  boundaries; the four `[ok]` lines remain consecutive; child `just check` stream
  stays correctly ordered (manual: run `python -m modernpackage init …` in a real
  terminal and confirm spacing).
- **Whole feature**: in a real terminal, `[ok]` + `passed` + `valid` are green
  and sections are spaced; `python -m modernpackage init … | cat` (non-TTY) and
  `NO_COLOR=1 python -m modernpackage init …` emit zero `\033` bytes.

**No un-sliceable work**: every phase crosses primitive → apply-site → test and
is independently testable. Phases 1→2 share the color helpers (2 depends on 1);
Phase 3 is orthogonal and can ship even if coloring is deferred.
