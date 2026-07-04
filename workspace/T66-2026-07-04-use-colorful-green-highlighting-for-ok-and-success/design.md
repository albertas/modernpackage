# Design Discussion

## Current State

All CLI output in `modernpackage/main.py` is **plain text**. There is no
color, no ANSI escapes, no color library, and no TTY detection anywhere in the
package (`research.md` Q1, Q5 — grep for `isatty|ansi|colorama|rich|NO_COLOR`
returns zero matches).

Output follows a **two-tier convention**: pure `_format_*` builders return
strings; thin `_print_*` wrappers call `print()` (`main.py:683-796`). Section
headers are module constants (`_PREFLIGHT_HEADER` etc., `main.py:674-680`).

Affirmative status appears in three places:
- `[ok]` marker built by `_format_check_line` (`main.py:683-686`), padded to 6
  chars (`f'  {marker:<6} {label}'`) so `[ok]` and `[FAIL]` align. Printed
  inline in the preflight loop at `main.py:883,885`.
- `just check passed — {module_name} scaffold is valid.` (`main.py:1109`).
- The negative counterpart `[FAIL]` (same function) and the stderr line
  `just check failed …` (`main.py:1113-1116`).

The **init happy path emits no blank lines** (`research.md` Q2). Sections run
back-to-back: preflight header + four check lines (`main.py:878-885`) →
`Running just check …` progress line (`main.py:1097-1100`) → live `just check`
output → `just check passed …` → `_print_init_summary` → `_print_next_commands`
(`main.py:1108-1111`). Multi-line blocks are single `print('\n'.join([...]))`
calls with no separator lines.

Tests assert **exact strings including whitespace** for preflight lines
(`test_main.py:742-746,830,850`) and substrings for the other blocks
(`research.md` Q4). No test inspects ANSI codes. Coverage gate is
`--cov-fail-under=95.0` (`pyproject.toml:40`).

## Desired End State

1. When the CLI writes to an interactive terminal, affirmative status
   tokens — the `[ok]` marker and the words `passed`/`valid` in the success
   line — render in **green**. Failure markers stay uncolored.
2. The package-init output has **blank lines between logical sections** so the
   terminal is easy to scan.
3. When stdout is **not** a TTY (piped, redirected, or captured under pytest),
   output is byte-for-byte identical to today's plain text — so every existing
   exact-string test still passes without modification.

**Verify:** existing `just check` / `just test` suite passes unchanged
(gating proves no regression); a new unit test asserts `_green()` wraps text in
the ANSI green/reset codes and is a no-op when color is disabled; a new test
confirms blank-line separators appear at section boundaries in captured init
output; manual run in a real terminal shows green markers and spaced sections.

## Patterns to Follow

- **Format/print split** (`main.py:683-796`): keep `_format_*` builders pure and
  string-returning; do color and blank-line composition so unit tests on the
  builders stay stable.
- **Module-constant headers/tokens** (`main.py:674-680`): define color codes as
  module-level `_`-prefixed constants with type annotations, next to the header
  constants, per code-practices ("`_RE`/constant naming", annotate constants).
- **`# noqa: T201` on every `print`** (`research.md` Q6): any new print site must
  carry it; `ruff select = ["ALL"]` (`pyproject.toml:68`).
- **Graceful boundary style** (`main.py:895-902`): environment/TTY probing must
  never raise — degrade to plain text.
- **Single quotes, line-length 88** (`pyproject.toml:58,61,64`); mypy `strict`
  (`pyproject.toml:87-95`) — new helpers fully typed with keyword-only params
  where they mirror existing signatures.

**Do NOT follow / avoid:**
- Do **not** add a runtime dependency. `dependencies = []` is a hard project
  convention (`pyproject.toml:18`, `research.md` Q5) — no `rich`/`colorama`.
- Do **not** bake color into the `_format_*` return values unconditionally; that
  would embed escape codes into strings the exact-match tests compare
  (`test_main.py:742-746`) and break them.
- Do **not** insert blank lines *inside* a format block — the four `[ok]` lines
  are order-checked as consecutive (`test_main.py:749-751`). Blanks go only at
  section boundaries in the orchestration code.

## Design Decisions

1. **Stdlib ANSI, no dependency**: add module-private `_ANSI_GREEN = '\033[32m'`
   and `_ANSI_RESET = '\033[0m'` constants and a `_green(text: str) -> str`
   helper in `main.py`. Rationale: zero-runtime-dep convention is authoritative;
   green highlighting needs ~15 lines of stdlib, not a library.

2. **TTY + `NO_COLOR` gating**: a `_color_enabled() -> bool` helper returns
   `sys.stdout.isatty() and os.environ.get('NO_COLOR') is None` (`os`, `sys`
   already imported, `main.py:3-11`). `_green()` returns its input unchanged when
   color is disabled. Rationale: this is the single mechanism that keeps piped
   output and pytest `capsys` (non-TTY → no color) byte-identical to today, so
   no existing test needs editing; `NO_COLOR` honors the community standard.

3. **Color the marker, preserve alignment**: in `_format_check_line`, compute the
   padded field on the *plain* marker first (`field = f'{marker:<6}'`), then wrap
   with `_green(field)` only when `ok`. Rationale: padding width must be measured
   before escape codes are added, or columns misalign; `[FAIL]` stays uncolored
   (task asks only for affirmative highlighting — red is out of scope).

4. **Color affirmative words in the success line**: wrap `passed` and `valid`
   via `_green()` in the `just check passed …` line (`main.py:1109`). Keep the
   sentence structure identical so the `'just check passed' in call` substring
   test still matches when color is off. Rationale: these are the "success"
   words the task names.

5. **Blank lines via orchestration, not builders**: emit separator blank lines
   with bare `print()  # noqa: T201` calls in `init_new_package` /
   `_run_preflight_checks` at section boundaries — after the preflight block,
   before the `just check` progress line, and between the passed-line, summary,
   and next-steps blocks. `_format_*` builders keep returning unpadded,
   blank-free strings. Rationale: keeps builders pure/unit-testable and avoids
   touching the order-checked check-line block.

6. **Keep color logic in `main.py`**: add the ~15 lines inline rather than a new
   `_style.py` module. Rationale: all output already lives in `main.py`; a new
   module for three constants and two helpers would be over-abstraction
   (CLAUDE.md §2). Revisit only if the color surface grows.

7. **Failure/stderr output unchanged**: `[FAIL]` and `just check failed …` stay
   plain. Rationale: task scope is affirmative highlighting only; adding red is
   unrequested scope creep (CLAUDE.md §2).

## What We're NOT Doing

- Not adding red/other colors, bold, or a full theming system.
- Not adding any runtime dependency (`rich`, `colorama`, `termcolor`).
- Not adding a `--color`/`--no-color` CLI flag (env `NO_COLOR` + TTY is enough).
- Not colorizing preflight *labels*, dry-run output, `[FAIL]`, or stderr text.
- Not changing marker text, padding widths, or any asserted string content.
- Not restructuring the format/print split or extracting a new module.

## Open Risks

- **Exact-line tests under an unexpected TTY**: if CI ever runs pytest attached
  to a real TTY, `capsys` still captures via a pipe (non-TTY), so gating holds —
  but confirm during implementation that no test forces `isatty` true.
- **Coverage of both color branches**: `_green()` enabled vs disabled and
  `_color_enabled()` true/false paths need direct unit tests (monkeypatch
  `sys.stdout.isatty` / `NO_COLOR`) to stay above the 95% gate
  (`pyproject.toml:40`).
- **Blank-line placement vs. `just check` live stream**: the child process
  inherits fds and writes directly (`main.py:1093-1106`); a separator printed
  before/after it must use `flush=True` to stay ordered relative to the child's
  output (mirrors the existing `flush=True` at `main.py:1099`).
- **Green-wrapping padded trailing spaces** (`[ok]  `) tints invisible spaces —
  harmless, but note it so a reviewer doesn't mistake it for a bug.
