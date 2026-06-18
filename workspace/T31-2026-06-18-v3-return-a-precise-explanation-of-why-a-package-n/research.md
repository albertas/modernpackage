# Research Findings

Scope: CLI package-name handling in `modernpackage/main.py` and its tests in
`tests/test_main.py`. All references are `file:line`.

## Q1: How `validate_package_name` decides acceptability, what `_PACKAGE_NAME_RE` enforces, and the exact rejection messages

### Findings
- `validate_package_name` is defined at `modernpackage/main.py:69-81`. Docstring:
  "Validate value is a PEP 508 / PyPI distribution name not shadowing stdlib."
- Two sequential gates (order matters):
  1. **Regex gate** — `if not _PACKAGE_NAME_RE.match(value)` (`main.py:71`). On
     failure raises `ArgumentTypeError` with message
     `f'Invalid package name: {value!r}'` (`main.py:72-73`). Note `value!r`
     wraps the name in quotes (e.g. `Invalid package name: '-bad'`).
  2. **Stdlib-collision gate** — only reached if the regex passes. Computes
     `module_name = normalize_module_name(value)` (`main.py:74`) and checks
     `if module_name in _STDLIB_MODULE_NAMES` (`main.py:75`). On collision raises
     `ArgumentTypeError` with message (`main.py:76-80`):
     `f'Package name {value!r} collides with the Python standard-library module {module_name!r}'`.
- On success returns `value` unchanged (`main.py:81`) — it returns the original
  string, NOT the normalized module name.
- `_PACKAGE_NAME_RE` (`main.py:58-61`):
  `r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$'` with `re.IGNORECASE`.
  - Anchored `^...$` (full-string match).
  - Two alternatives: a **single** alphanumeric char, OR an alphanumeric start +
    any run of `[a-z0-9._-]` + an alphanumeric end.
  - Net effect: must **start and end with alphanumeric**; `.`, `_`, `-` allowed
    only **internally**. Case-insensitive (uppercase accepted by regex).
  - Uses `.match` (not `.fullmatch`), but the trailing `$` anchor makes it
    equivalent to a full match here.
- Comment at `main.py:56-57` cites the intent: "PEP 503 / PEP 508 valid
  distribution name: alphanumeric ends, with -, _, . permitted internally.
  Case-insensitive."

## Q2: Categories rejected / treated out of scope, and where documented

### Findings
- **Rejected by the regex** (`main.py:58-61`):
  - Empty string `''` — neither alternative matches. (Tested: `main.py` via
    `test_main.py:55`.)
  - Leading/trailing separator: `-bad`, `bad-` (also `.`/`_` at ends).
    (Tested: `test_main.py:55`.)
  - Disallowed characters, e.g. whitespace `has space`. (Tested:
    `test_main.py:55`.) Any char outside `[a-z0-9._-]` is rejected.
- **Rejected by the stdlib gate** (`main.py:75`): names whose normalized module
  form equals a stdlib top-level module name, e.g. `json`, `os`, `email`.
  (Tested: `test_main.py:60-65`.)
- **Explicitly OUT OF SCOPE — accepted despite being invalid Python modules**,
  documented in `normalize_module_name` docstring (`main.py:88-91`):
  - **Leading-digit names** e.g. `9lives` — pass the regex (digits are
    alphanumeric) and are NOT rejected. Docstring: "Leading-digit names
    (e.g. `9lives`) ... remain invalid module names — out of scope".
  - **Python keywords** e.g. `class` — pass the regex and are NOT rejected (and
    `class` is not in `sys.stdlib_module_names`). Docstring: "Python keywords
    (e.g. `class`) remain invalid module names — out of scope (see plan Open
    Risks / design Open Risks)."
- Note on regex: it does NOT collapse or limit consecutive separators, so e.g.
  `a--b` and `a..b` are accepted (`a--b` confirmed valid via
  `test_normalize_module_name`, `test_main.py:36`).
- The stdlib set source is documented at `main.py:63-66`: "All Python
  standard-library top-level module names for the running interpreter (a
  frozenset; available since 3.10). A normalized module name equal to any of
  these would shadow a stdlib module on import, so reject it."
  `_STDLIB_MODULE_NAMES = sys.stdlib_module_names` (`main.py:66`) — interpreter-
  dependent set.

## Q3: How `humanize_git_clone_error` maps failure text to ordered explanations; wording/precedence conventions

### Findings
- Function: `main.py:47-53`. Lowercases the input
  (`lowercased = stderr_text.lower()`, `main.py:49`), iterates the ordered list
  `_GIT_CLONE_ERROR_MESSAGES`, returns the **first** message whose compiled
  pattern `.search()` matches (`main.py:50-52`); returns `None` if none match
  (`main.py:53`). Docstring: "Return the first friendly message for a known git
  clone failure, or None."
- The table `_GIT_CLONE_ERROR_MESSAGES` (`main.py:12-44`) is a
  `list[tuple[re.Pattern[str], str]]`. **Precedence = list order**; the leading
  comment states "Ordered most-specific first so that a more precise pattern
  wins over a broad one." (`main.py:11`).
- Five categories in order:
  1. Network — `could not resolve host|could not read from remote|failed to
     connect|connection timed out|network is unreachable` →
     `'repository unreachable — check your network connection'` (`main.py:14-20`).
  2. Repo not found — `repository.*not found|remote: not found|does not exist` →
     `'template repository not found — it may have moved or been removed'`
     (`main.py:22-25`). Comment notes git may insert the URL between words, hence
     `.*` (`main.py:21`).
  3. Auth — `permission denied \(publickey\)|authentication failed|could not
     read username` → `'authentication failed — check your git credentials or
     access rights'` (`main.py:27-33`). Comment: "must precede broad 'permission
     denied'" (`main.py:26`).
  4. Destination occupied — `already exists and is not an empty directory` →
     `'destination directory already exists — choose a different package name'`
     (`main.py:35-38`).
  5. Filesystem perms (broad, intentionally last) — `permission denied|could not
     create|unable to create` → `'cannot write to the destination directory —
     check filesystem permissions'` (`main.py:39-43`). Comment: "broad,
     intentionally last" (`main.py:39`).
- **Wording conventions observed**: lowercase short phrase, an em-dash (`—`)
  separating the diagnosis from an actionable hint (e.g. "... — check your
  network connection"). Precedence convention: specific patterns before broad
  ones; the publickey/auth ordering exists specifically so the broad "permission
  denied" filesystem rule does not capture SSH auth failures.
- Patterns are matched case-insensitively via the `.lower()` of input rather
  than `re.IGNORECASE` (the patterns themselves are lowercase).

## Q4: How validation failures propagate through argparse; exit codes and streams

### Findings
- `validate_package_name` is wired as `type=validate_package_name` on the
  positional `package_name` argument (`main.py:105-110`), within `parse_args`
  (`main.py:95-111`). `nargs='?'` makes it optional (`main.py:108`).
- When a `type=` callable raises `ArgumentTypeError`, argparse catches it inside
  `parse_args()` and calls `parser.error(...)`, which prints the program usage
  line plus `<prog>: error: argument package_name: <message>` to **stderr** and
  terminates the process via `sys.exit(2)`. (Standard `argparse` behavior; the
  code does not override `error`/`exit`.) Exit code is **2**.
- This path happens during `parse_args()` (`main.py:177` in `main`), i.e. before
  `main`'s own try/except around `init_new_package`. So validation rejections
  exit with code 2 via argparse, distinct from the code-1 scaffolding-failure
  path in `main` (`main.py:183-187`).
- By contrast, runtime scaffolding failures raise `RuntimeError` caught in `main`
  (`main.py:185-187`): printed to stderr (`print(error, file=sys.stderr)`) and
  `main` returns **1**.
- No test exercises the argparse-to-exit-code path directly; tests call
  `validate_package_name` in isolation and assert the raised `ArgumentTypeError`
  (`test_main.py:54-65`). (See Open Areas.)

## Q5: How `normalize_module_name` relates to validation; assumptions about pre-validated input

### Findings
- Definition `main.py:84-92`. Returns `value.replace('.', '_').replace('-', '_')`
  (`main.py:92`) — replaces `.` and `-` with `_`; `_` preserved; case unchanged.
- Relationship to validation: it is called *inside* `validate_package_name`
  (`main.py:74`) to compute the candidate module name for the stdlib-collision
  check, and again in `init_new_package` (`main.py:116`) to build the clone
  destination path / `just init` argument.
- **Documented assumption** (docstring, `main.py:85-91`): "Input is already
  validated by `validate_package_name`, so this never returns None." It assumes
  the input already satisfies the regex (alphanumeric ends, only `._-` internal
  separators). It performs no validation itself and would happily transform
  invalid input.
- Out-of-scope cases it explicitly does NOT fix (docstring `main.py:88-91`):
  leading-digit names (`9lives`) and Python keywords (`class`) "remain invalid
  module names — out of scope". Runs are not collapsed: `a--b` → `a__b` (design
  intent, `test_main.py:35-36`).

## Q6: How tests exercise valid/invalid/stdlib-collision names and asserted text

### Findings
- **Valid names** — `test_validate_package_name_valid` (`test_main.py:41-51`):
  asserts `validate_package_name` returns the input unchanged for `mypackage`,
  `my-package`, `my_package`, `my.package`, `a`. Also "near-miss" names that
  *contain* a stdlib substring but do not normalize to one: `my-json`,
  `jsonschema`, `email_utils` (`test_main.py:47-50`), plus
  `normalize_module_name('my-json') == 'my_json'` (`test_main.py:51`).
- **Invalid names** — `test_validate_package_name_invalid` (`test_main.py:54-57`):
  iterates `('-bad', 'bad-', 'has space', '')` and asserts
  `pytest.raises(ArgumentTypeError, match='Invalid package name')`.
- **Stdlib collisions** — `test_validate_package_name_rejects_stdlib_collision`
  (`test_main.py:60-65`): iterates `('json', 'os', 'email')`, asserts
  `pytest.raises(ArgumentTypeError, match='collides with the Python standard-library module')`.
- **Normalization** — `test_normalize_module_name` (`test_main.py:29-38`) maps:
  `my-cool.package→my_cool_package`, `my_package→my_package`, `a→a`,
  `my-cool_pkg.v2→my_cool_pkg_v2`, `a--b→a__b` (comment: "runs are preserved,
  not collapsed (design intent)", `test_main.py:36`).
- Assertions use `match=` substring regex on the exception message, not exact
  equality — so they assert on the *prefix/phrase*, not the full message with the
  `!r`-quoted name.
- `humanize_git_clone_error` tests assert **exact** message equality for each
  category and `None` for unknown input (`test_main.py:211-244`); an end-to-end
  network case asserts the friendly + raw composite via `init_new_package`
  (`test_main.py:282-294`).

## Cross-Cutting Observations
- Two distinct "friendly error" mechanisms with different conventions:
  - Validation messages (`main.py:72, 76-80`): capitalized, include the offending
    value via `!r`, raised as `ArgumentTypeError` (argparse path, exit 2).
  - Git-clone messages (`main.py:12-44`): lowercase, em-dash + actionable hint,
    ordered most-specific-first, returned as plain strings; combined with raw
    stderr as `f'{friendly}\n\n{raw}'` in `init_new_package` (`main.py:131`).
- Ordering/precedence is the recurring pattern: the git error table is ordered
  specific→broad (`main.py:11`); `validate_package_name` checks regex before
  stdlib so malformed input never reaches the collision branch.
- `normalize_module_name` is the single shared normalizer used both for the
  collision check and for filesystem/`just` target naming, ensuring the validated
  name and the on-disk module name agree.
- Error stream/exit convention: argparse validation → stderr, exit 2; runtime
  failures → `RuntimeError` → stderr, return 1 (`main.py:185-187`); `just check`
  failure → stderr, return 1 (`main.py:167-172`).

## Open Areas
- **Q4 exit-code behavior is inferred from standard `argparse` semantics**, not
  from an override or a test in this repo. No test invokes `parse_args()` with an
  invalid `package_name` to confirm the `SystemExit`/exit-code-2/usage-on-stderr
  behavior; the code does not subclass `ArgumentParser` or override `error`/`exit`
  (`main.py:95-111`).
- `_STDLIB_MODULE_NAMES` content is interpreter-version dependent
  (`sys.stdlib_module_names`, `main.py:66`); exactly which names collide depends
  on the running Python version (≥3.10).
- The regex's acceptance of uppercase (`re.IGNORECASE`, `main.py:60`) and of
  repeated/mixed separators (`a..b`, `a-_-b`) is not directly asserted by tests.
