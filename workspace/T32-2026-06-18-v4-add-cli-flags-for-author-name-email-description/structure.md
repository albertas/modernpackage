# Structure Outline

## Approach

Add five optional long-only metadata flags to the CLI and thread their parsed
values through `parse_args → main → init_new_package` as keyword arguments
defaulting to `None`. Two flags (`--author-email`, `--repository-url`) get
parse-time `type=` validators with `_RE` constants; the other three are free
strings. Values reach `init_new_package`'s signature but are **not** written to
`pyproject.toml` (deferred V4 work). Slices are grouped by validation tier so
each phase is an independently testable end-to-end addition (add_argument →
Namespace attr → `main` forwarding → `init_new_package` param → tests).

All work is in `modernpackage/main.py` and `tests/test_main.py`. Verify every
phase with `just check` (format + lint + complexity + typecheck + test); lint is
`select = ["ALL"]` (`pyproject.toml:67`), line-length 88, mccabe ≤ 8.

### Two cross-cutting constraints the plan must honor (beyond design.md)

- **`A002` builtin-argument-shadowing**: a function param named `license` shadows
  the `license` builtin and `select=["ALL"]` will flag it. The `init_new_package`
  param must be named e.g. `package_license`, with `main` forwarding
  `package_license=parsed_args.license` (the Namespace attr stays `.license`).
- **`ARG001` unused-argument**: the five new params are accepted but unconsumed.
  Acknowledge them minimally (a single `del author_name, author_email,
  description, package_license, repository_url` statement documenting "threaded,
  consumed in later V4 work") rather than disabling the rule. Fall back to scoped
  `# noqa: ARG001` only if `del` does not satisfy ruff. Confirm via `just check`.

---

## Phase 1: Free-string flags + threading foundation

Adds `--author-name`, `--description`, `--license` (no validation) and
establishes the full vertical wiring: parse → forward → accept. After this phase
users can pass these three flags and they land on the `init_new_package`
signature.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `parse_args()` — three new `parser.add_argument('--author-name', help=…,
  default=None)` calls (mirror style at `main.py:125-137`); `--license` uses
  `dest` left as default (`.license`). Returns Namespace now carrying
  `author_name`, `description`, `license`.
- `init_new_package(package_name: str, *, author_name: str | None = None,
  description: str | None = None, package_license: str | None = None) -> int`
  — additive keyword-only params, default `None`; body adds a `del …`
  acknowledgement (see constraints above). No behavior change otherwise.
- `main()` — extend the call at `main.py:211` to
  `init_new_package(package_name=…, author_name=parsed_args.author_name,
  description=parsed_args.description, package_license=parsed_args.license)`.

**Verify**: `just test` passes. New tests:
`test_parse_args_author_name` etc. patch `sys.argv` to
`['modernpackage', 'mypkg', '--author-name', 'Ada']` and assert
`result.author_name == 'Ada'` (and `description`, `license`); update
`test_main_with_package_name` (`test_main.py:167-177`) so
`init_mock.assert_called_once_with(...)` includes the three new kwargs (defaults
`None`). Run: `just check` exits 0.

---

## Phase 2: Validated `--author-email` flag

Adds `--author-email` with parse-time email-shape validation, threaded like
Phase 1. Invalid emails are rejected with `ArgumentTypeError` (exit 2).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_EMAIL_RE: re.Pattern[str]` — module-level constant near `main.py:58-65`,
  permissive shape `^\S+@\S+\.\S+$` with explanatory comment (design Decision 4).
- `validate_author_email(value: str) -> str` — top-level validator mirroring
  `validate_package_name` (`main.py:95-108`); raises
  `ArgumentTypeError(f'Invalid author email: {value!r} — …')` on no match, else
  returns `value`.
- `parse_args()` — `add_argument('--author-email', type=validate_author_email,
  default=None, help=…)`.
- `init_new_package(…, author_email: str | None = None)` — new keyword param;
  add to the `del` acknowledgement. `main()` forwards
  `author_email=parsed_args.author_email`.

**Verify**: `just test` passes. New tests:
`test_validate_author_email_accepts` (`'a@b.co'` returns unchanged);
`test_validate_author_email_rejects` (`pytest.raises(ArgumentTypeError)` for
`'not-an-email'`); a `parse_args` test asserting `result.author_email`; extend
the `main` kwargs assertion. Run: `just check` exits 0.

---

## Phase 3: Validated `--repository-url` flag

Adds `--repository-url` requiring an `http(s)://` scheme (no network call),
threaded identically. Completes the five-flag set.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_REPOSITORY_URL_RE: re.Pattern[str]` — module-level constant, `^https?://\S+$`
  with comment (design Decision 5).
- `validate_repository_url(value: str) -> str` — top-level validator, same
  shape as Phase 2; raises `ArgumentTypeError(f'Invalid repository URL: …')`.
- `parse_args()` — `add_argument('--repository-url',
  type=validate_repository_url, default=None, help=…)`; Namespace attr
  `repository_url`.
- `init_new_package(…, repository_url: str | None = None)` — final keyword param,
  added to the `del` acknowledgement. `main()` forwards
  `repository_url=parsed_args.repository_url`.

**Verify**: `just test` passes. New tests:
`test_validate_repository_url_accepts` (`'https://x.com/r'`);
`test_validate_repository_url_rejects` (`pytest.raises(ArgumentTypeError)` for
`'ftp://x'` and `'x.com'`); a `parse_args` test for `result.repository_url`;
finalize the `main` kwargs assertion to all five flags. Run: `just check`
exits 0.

---

## Testing Checkpoints

- **After Phase 1**: `parse_args` returns `author_name`/`description`/`license`
  (default `None`); `init_new_package` signature accepts them keyword-only;
  `main` forwards them; `just check` green. The `del`/ARG001 and `package_license`
  builtin-shadow decisions are settled here and reused unchanged in later phases.
- **After Phase 2**: `--author-email` parses; bad emails exit 2 with
  `ArgumentTypeError`; value threaded; `just check` green.
- **After Phase 3**: all five flags parse; bad email/URL exit 2; `main` calls
  `init_new_package` with all five kwargs (verifiable via the single extended
  `init_mock.assert_called_once_with(...)`); `just check` green.
- **Resume aid**: each phase is purely additive and independently valuable — if
  Phase 3 stalls, Phases 1-2 ship working flags. No `pyproject.toml`, `Justfile`,
  or `just init` changes in any phase (design "What We're NOT Doing").
