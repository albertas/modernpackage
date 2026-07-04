# Research Findings

Scope: `modernpackage/main.py` output layer, preflight flow, init command,
`pyproject.toml` deps/lint config, and `tests/test_main.py`.

## Q1: How does the CLI produce terminal output — build vs print, any styling/ANSI/color?

### Findings
- **Two-tier helper convention**: pure `_format_*` functions build strings;
  thin `_print_*` wrappers call `print()` on the formatted string.
  - `_format_check_line` `main.py:683` / printed inline in `_run_preflight_checks`
    `main.py:883,885`.
  - `_format_dry_run_plan` `main.py:689` → `_print_dry_run_plan` `main.py:736`.
  - `_format_init_summary` `main.py:764` → `_print_init_summary` `main.py:779`.
  - `_format_next_commands` `main.py:784` → `_print_next_commands` `main.py:794`.
- **All output is plain text.** No ANSI escapes, no color library, no styling
  anywhere. Grep for `isatty|ansi|\033|colorama|rich|termcolor|NO_COLOR` in
  `modernpackage/` returns **zero** matches (only unrelated `ArgumentTypeError`).
- Formatting is purely structural: two-space indentation and a fixed-width
  marker field (`f'  {marker:<6} {label}'`, `main.py:686`).
- Direct `print()` calls (not via a `_print_*` helper) also exist:
  - Header `print(_PREFLIGHT_HEADER)` `main.py:878`.
  - `just check` progress line `main.py:1097-1100` (`flush=True`).
  - Success line `just check passed …` `main.py:1109`.
  - Failure/notice lines to `sys.stderr` `main.py:1113-1117`, and various
    boundary notices (`main.py:290,468,898,921,958`).
  - Version line `main.py:1126`; error dump `main.py:1142`.
- Every `print` carries a `# noqa: T201` marker (see Q6).

## Q2: Complete message sequence during package initialization

### Findings
Order of emission in `init_new_package` (`main.py:1011-1118`):
1. **Preflight header** `Preflight checks:` — `print(_PREFLIGHT_HEADER)`
   `main.py:878` (`_PREFLIGHT_HEADER` = `'Preflight checks:'`, `main.py:674`).
2. **One check line per check**, printed in the loop `main.py:879-885`. Success
   prints `[ok]` line after `check.run()`; failure prints `[FAIL]` line then
   re-raises. Four checks: `package name valid`, `required tools on PATH (git,
   just, uv)`, `target directory available`, `template remote reachable`
   (`main.py:866-877`).
3. If `--dry-run`: `_print_dry_run_plan` `main.py:1030`, then `return 0` (no
   further messages). Dry-run block starts with `_DRY_RUN_HEADER`
   = `'Dry run — no changes will be made:'` `main.py:675`.
4. (real run) git clone runs silently (output PIPE-captured).
5. **Progress line**: `Running just check in {module_name} (this can take a
   while)…` with `flush=True` `main.py:1097-1100`. `just check` inherits
   stdout/stderr (no PIPE) so it streams live `main.py:1093-1106`.
6. On `just check` success (`main.py:1108-1112`), three separate prints:
   - `just check passed — {module_name} scaffold is valid.` `main.py:1109`.
   - `_print_init_summary(package_name, path)` `main.py:1110`.
   - `_print_next_commands(module_name)` `main.py:1111`.
7. On failure: single stderr message `just check failed with exit code … — see
   the check output above.` `main.py:1113-1117`, returns 1.
- **Blank lines / separation**: multi-line blocks are single `print()` calls of
  `'\n'.join([...])` — no explicit blank-line separators between sections. Each
  block header is the first list element; body lines are two-space indented.
  Error `RuntimeError` messages embed a `\n\n` between friendly and raw text
  (`main.py:845,855,1055`), but the init happy-path emits no blank lines.

## Q3: Where affirmative status words appear; how negative markers are built

### Findings
- **`[ok]` / `[FAIL]` markers** are both produced by one function
  `_format_check_line` `main.py:683-686`:
  ```python
  marker = '[ok]' if ok else '[FAIL]'
  return f'  {marker:<6} {label}'
  ```
  The `:<6` left-justifies the marker to 6 chars so `[ok]` (→ `[ok]  `) and
  `[FAIL]` align. Caller passes `ok=True`/`ok=False` at `main.py:883,885`.
- **`passed` / `valid`**: literal success line `f'just check passed —
  {module_name} scaffold is valid.'` `main.py:1109`.
- **`available`**: preflight label `'target directory available'` `main.py:873`.
- Other affirmative label text: `'package name valid'` `main.py:867`,
  `'required tools on PATH (...)'` `main.py:869`, `'template remote reachable'`
  `main.py:876`.
- **Failure counterparts**: `[FAIL]` (same `_format_check_line`), and stderr
  line `'just check failed with exit code …'` `main.py:1113-1114`. Verifier
  failures surface as `RuntimeError` messages (lowercase prose, e.g.
  `'required tool(s) not found on PATH: …'` `main.py:804`), printed at
  `main.py:1142`.
- Dry-run has no ok/fail markers; uses `'keeps template default'` vs the value
  `main.py:722-724`.

## Q4: How the format helpers are tested; exact asserted string content

### Findings
Helpers imported at `tests/test_main.py:21-23` (and `_format_check_line` is
tested only indirectly via preflight output).
- **`_format_check_line`** — no direct unit test; asserted via captured output:
  - `'  [ok]   package name valid'`, `'  [ok]   required tools on PATH (git,
    just, uv)'`, `'  [ok]   target directory available'`, `'  [ok]   template
    remote reachable'` (`test:742-746`, exact, order-checked `test:749-751`).
  - `'  [FAIL] template remote reachable'` `test:830`; `'  [FAIL] required tools
    on PATH (git, just, uv)'` `test:850`. Note the exact spacing: `[ok]` is
    followed by 3 spaces (`[ok]` padded to 6 = `[ok]  ` + 1 separator space),
    `[FAIL]` by 1 space.
- **`_format_init_summary`** `test:691-696`: substring asserts only —
  `'demo-pkg' in summary`, `str(demo_path) in summary`, `'0.0.1' in summary`.
- **`_format_next_commands`** `test:699-703`: `'cd my_package'`, `'just check'`,
  and `'&&'` all `in result`.
- **`_format_dry_run_plan`** `test:1508-1523`: asserts `'/tmp/foo'`,
  `'https://github.com/albertas/modernpackage'`, `'Ada Lovelace'`, `'keeps
  template default'`, `'modernpackage/ -> foo/'`, `'0.0.1'` all in plan.
  Backend/frontend variants assert `'add FastAPI backend' in plan`
  `test:1576`, absent by default `test:1589`, `'add React frontend'`
  `test:1736-1737,1750`.
- **Integration** (whole-message) asserts: `'just check passed' in call`
  (`test:687,718`), `'cd mypackage && just check'` `test:722`,
  `'Dry run — no changes will be made:'` `test:1538`, `'just check failed'`
  `test:775`.
- Assertions are **substring / exact-line** based (`in`, `==`), not
  style-aware; no test inspects ANSI codes or colors.

## Q5: Runtime dependencies, dep-management conventions, and TTY gating

### Findings
- **Runtime dependencies: none.** `pyproject.toml:18` `dependencies = []`.
  The CLI relies only on the stdlib (`os`, `re`, `shutil`, `sys`, `tomllib`,
  `argparse`, `subprocess`, `pathlib`, `dataclasses`) — imports `main.py:3-11`.
- **Dev group** (`[dependency-groups] dev`, `pyproject.toml:27-37`): ruff,
  mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, `vupi>=0.0.10`.
- **Conventions**: PEP 621 metadata; hatchling build (`pyproject.toml:46-55`);
  dynamic version from `modernpackage/__init__.py`; a custom uv index
  (`[[tool.uv.index]]` gitlab, `pyproject.toml:103-105`). Injected
  backend/frontend deps are appended lower-bound-only tuples in code
  (`_BACKEND_DEPENDENCIES` `main.py:566`, etc.) — not in root `pyproject.toml`.
- **No TTY / interactivity detection.** No `sys.stdout.isatty()`, no
  `NO_COLOR`/`FORCE_COLOR` handling, no piped-vs-interactive branching anywhere
  in `modernpackage/` (grep returned nothing). The only stdout-behavior
  distinction is that `just check` inherits fds (unbuffered live stream) while
  git/just-init are PIPE-captured (`main.py:1043-1106`) — a buffering choice,
  not a TTY check.

## Q6: Lint/format/type rules constraining output code

### Findings
- **`# noqa: T201`** on every `print` (`main.py:290,468,749,781,796,878,883,
  885,898,921,958,1097,1109,1113,1126,1142`). T201 is flake8-print "print found";
  ruff `select = ["ALL"]` (`pyproject.toml:68`) enables it, so each print must
  be individually suppressed.
- **`select = ["ALL"]`** `pyproject.toml:68` with a small `ignore` list
  (`D203,D213,COM812,ISC001`, `pyproject.toml:69-74`) — nearly all lint rules
  active, so new output code inherits the full ruleset (docstrings D*,
  exception-message EM*, etc.).
- **Quote style**: single quotes enforced — `inline-quotes = "single"`
  `pyproject.toml:61`; `quote-style = "single"` `pyproject.toml:64`.
- **Line length 88** `pyproject.toml:58`; note long output strings already use
  `# noqa: E501` where needed (e.g. `main.py:373`). (CLAUDE.md/code-practices
  mention 120, but this repo's `pyproject.toml` sets 88 — the authoritative
  value here.)
- **McCabe max-complexity = 8** `pyproject.toml:85`.
- **`docstring-code-format = true`** `pyproject.toml:65`.
- **mypy strict** `pyproject.toml:87-95` (`strict = true`, `python_version =
  "3.14"`, `warn_return_any`) — `_format_*` helpers are fully typed (`-> str`,
  keyword-only params). Any new output helper must satisfy strict typing.
- **deadcode** `pyproject.toml:97-101` ignores `main`, excludes `tests`; a new
  helper that is unused would be flagged.
- Tests run via `just check` / `just test`; pytest enforces
  `--cov-fail-under=95.0` (`pyproject.toml:40`), so new output branches need
  test coverage.

## Cross-Cutting Observations
- Consistent **format/print split**: every user-facing multi-line block has a
  pure `_format_*` builder (unit-testable, returns `str`) plus a `_print_*`
  wrapper — except `_format_check_line`, which is printed inline in the
  preflight loop rather than via a dedicated `_print_*` wrapper.
- Section headers are module constants (`_PREFLIGHT_HEADER`, `_DRY_RUN_HEADER`,
  `_INIT_SUMMARY_HEADER`, `_NEXT_COMMANDS_HEADER`, `main.py:674-680`).
- Success vs failure is expressed **lexically** (`[ok]`/`[FAIL]`, "passed",
  "failed") and by stream (stdout vs stderr) — never by color today.
- Tests assert **exact strings including whitespace** for preflight lines, so
  any change to marker text/padding would break `test:742-746,827-830,849-850`.

## Open Areas
- No existing precedent in the repo for terminal color/styling to model after;
  the codebase has zero color/TTY infrastructure. Questions did not ask for a
  proposal, and none is given.
