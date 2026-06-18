# Design Discussion

## Current State

`validate_package_name` (`modernpackage/main.py:69-81`) has two sequential
gates:

1. **Regex gate** (`main.py:71-73`): `if not _PACKAGE_NAME_RE.match(value)` →
   raises `ArgumentTypeError(f'Invalid package name: {value!r}')`. This is the
   problem: every malformed name — empty string, leading/trailing separator,
   embedded space, illegal punctuation — collapses into the *same* generic
   message. The user learns the name is bad but not *why*.
2. **Stdlib-collision gate** (`main.py:74-80`): already precise — names the
   colliding module (`f'Package name {value!r} collides with the Python
   standard-library module {module_name!r}'`).

The regex `_PACKAGE_NAME_RE` (`main.py:58-61`,
`r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$'`, `re.IGNORECASE`) enforces:
alphanumeric start and end, with `.`, `_`, `-` allowed only internally. It does
not distinguish *which* rule a rejected name broke.

Existing tests (`tests/test_main.py:54-57`) iterate `('-bad', 'bad-', 'has
space', '')` and assert only the substring `match='Invalid package name'` — so
all four currently exercise one indistinguishable path. The stdlib test
(`test_main.py:60-65`) asserts `match='collides with the Python
standard-library module'`.

The sibling pattern `humanize_git_clone_error` (`main.py:47-53`) already
demonstrates the codebase's approach to actionable diagnostics: an ordered
`list[tuple[pattern, message]]` (`main.py:12-44`) scanned most-specific-first
(`main.py:11`), returning a short phrase + em-dash + actionable hint.

## Desired End State

When a name is refused, the `ArgumentTypeError` message states the *specific*
reason, picked from these categories (the ones the task names):

- **Empty value** → e.g. `Invalid package name: '' — name must not be empty`
- **Leading/trailing separator** → e.g. `Invalid package name: '-bad' — name
  must start and end with a letter or digit`
- **Disallowed character** → e.g. `Invalid package name: 'has space' — name
  contains a disallowed character: ' ' (only letters, digits, '.', '_', '-'
  are allowed)`
- **Stdlib collision** → unchanged (already precise, `main.py:76-80`).

**Verify correctness**: each category has a test asserting its distinct reason
phrase; the existing `test_validate_package_name_invalid` assertions
(substring `Invalid package name`) and the stdlib test still pass unchanged;
valid names still return the input unchanged (`test_main.py:41-51`); `just
check` and `just test` are green.

## Patterns to Follow

- **Ordered most-specific-first diagnosis** — mirror
  `_GIT_CLONE_ERROR_MESSAGES` precedence (`main.py:11`,
  `humanize_git_clone_error` `main.py:47-53`). Implement reason detection as an
  ordered sequence of checks where the first match wins, so overlapping
  failures resolve deterministically.
- **`!r`-quoted offending value** — keep the validation-message convention of
  embedding the value via `{value!r}` (`main.py:72`, `main.py:77`). This is the
  established style for `ArgumentTypeError` messages and what differentiates
  them from the lowercase git-clone strings (Cross-Cutting Observations,
  `research.md:177-182`).
- **Em-dash + actionable hint** — adopt the `… — <hint>` shape from the git
  table (`main.py:19,24,32,37,42`) for the appended reason, so validation
  messages gain the same actionable tone.
- **Regex stays the source of truth** — `_PACKAGE_NAME_RE` (`main.py:58-61`)
  remains the single accept/reject authority. The new code only *explains* a
  rejection after the regex has already said no; it must never accept a name
  the regex rejects, nor reject one it accepts.
- **Single shared normalizer** — leave `normalize_module_name` (`main.py:84-92`)
  and its pre-validated-input assumption untouched; the stdlib gate keeps using
  it (`main.py:74`).
- **Test style** — top-level `def test_*`, `pytest.raises(..., match=...)`
  substring assertions (`test_main.py:54-65`), per `Code Best Practices`.

Pattern NOT to follow: do **not** lowercase the whole validation message like
the git strings do — validation messages are capitalized and value-quoted
(`research.md:179`). Keep that distinction.

## Design Decisions

1. **Explain-after-reject, not regex-replacement**: Keep `_PACKAGE_NAME_RE` as
   the gate; add a private helper `_explain_invalid_package_name(value) -> str`
   that runs only when the regex fails and returns the precise reason phrase.
   *Why*: minimal, surgical change (CLAUDE.md §3); the regex already encodes the
   rules correctly, so re-deriving acceptance from scratch risks drift between
   the two.
2. **Preserve the `Invalid package name: {value!r}` prefix, append ` — <reason>`**:
   *Why*: existing tests assert the substring `Invalid package name`
   (`test_main.py:56`) and must keep passing without edits (CLAUDE.md §3,
   surgical). Appending the reason adds precision while staying
   backward-compatible.
3. **Reason precedence order**: (1) empty → (2) disallowed character → (3)
   leading/trailing separator. *Why*: empty is the most distinct case; a
   disallowed character (space, `/`, `@`) is a hard removal the user must make
   and is more specific than separator placement, so it wins when a name has
   both (e.g. `-has space` reports the space). Mirrors most-specific-first
   (`main.py:11`).
4. **Disallowed-character message names the exact character and the allowed
   set**: report the first character outside `[a-z0-9._-]` (case-insensitive),
   shown via `!r`, plus the allowed-set hint. *Why*: directly actionable — the
   task explicitly calls out "the specific disallowed character". First-offender
   reporting keeps the message short and unambiguous.
5. **Leading/trailing separator phrased as a positive rule**: "name must start
   and end with a letter or digit" rather than enumerating which separator is
   misplaced. *Why*: one phrase covers leading/trailing `.`, `_`, and `-`
   uniformly; matches the regex's actual constraint (`main.py:56-57`).
6. **Out-of-scope cases stay out of scope**: leading-digit names (`9lives`) and
   Python keywords (`class`) still pass validation (`main.py:88-91`,
   `research.md:49-57`). *Why*: the task is about explaining *refusals*, not
   adding new ones; expanding rejection scope would be scope creep.
7. **Helper is module-private (`_`-prefixed)**: tested via direct import per
   convention (`Code Best Practices`, "Public / private API"). *Why*: it is an
   internal explanation detail, not public surface.

## What We're NOT Doing

- Not changing which names are accepted/rejected — acceptance set is identical.
- Not adding new rejection categories (no keyword check, no leading-digit
  check, no consecutive-separator collapse; `a--b`/`a..b` stay valid,
  `research.md:58-60`).
- Not touching the stdlib-collision message — already precise (`main.py:76-80`).
- Not altering `normalize_module_name`, `parse_args`, or the argparse exit-code
  path (exit 2 to stderr, `research.md:108-128`).
- Not converting validation messages to the lowercase git-string style.
- Not adding an end-to-end argparse exit-code test (pre-existing gap,
  `research.md:193-198`) unless trivially warranted.

## Open Risks

- **Disallowed-character display for whitespace/control chars**: `repr(' ')`
  renders as `"' '"`, which is readable, but tab/newline render as `'\t'`/`'\n'`
  — acceptable and arguably clearer. Confirm the message stays legible in test
  assertions.
- **Reason precedence ambiguity** for names breaking multiple rules
  simultaneously (e.g. `-a b`): decision 3 fixes the order, but reviewers may
  prefer separator-first. Documented so it can be revisited cheaply.
- **Uppercase acceptance** (`re.IGNORECASE`, `main.py:60`): the disallowed-char
  check must treat `A-Z` as allowed to stay consistent with the regex; an
  off-by-one in the allowed set would wrongly flag valid uppercase names. Cover
  with a test.
- **Interpreter-dependent stdlib set** (`sys.stdlib_module_names`,
  `main.py:66`): unaffected by this change, but stdlib-collision tests remain
  version-sensitive (`research.md:199-201`).
