# Plan

## Phase 1: Relax package-name validation to PEP 508 / PyPI distribution names

### Background

`modernpackage/main.py` validates the CLI `package_name` argument via
`check_alpha_numeric`, which rejects anything where `value.isalnum()` is false.
This refuses valid distribution names such as `my-package` or `my_package`.

PEP 503 / PEP 508 defines a valid distribution name as matching (case-insensitive):

```
^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$
```

i.e. it must start and end with an alphanumeric, and may contain hyphens,
underscores, and dots in between. The project has `dependencies = []`, so the
`packaging` library is **not** available — use a hand-rolled compiled regex
(no new runtime dependency).

Scope note: this task only **relaxes validation**. Normalizing an accepted name
into an import-safe module name and rejecting stdlib collisions are separate
BACKLOG items and are explicitly out of scope here.

### Changes (`modernpackage/main.py`)

1. Add a module-level compiled regex constant near the other `_*_RE`-style
   constants, e.g.:

   ```python
   # PEP 503 / PEP 508 valid distribution name: alphanumeric ends, with
   # -, _, . permitted internally. Case-insensitive.
   _PACKAGE_NAME_RE: re.Pattern[str] = re.compile(
       r'^([a-z0-9]|[a-z0-9][a-z0-9._-]*[a-z0-9])$',
       re.IGNORECASE,
   )
   ```

2. Replace `check_alpha_numeric` with a validator that uses the regex. Rename it
   to `validate_package_name` (the old name and message — "Non-AlphaNumeric" —
   become inaccurate once hyphens/underscores are allowed):

   ```python
   def validate_package_name(value: str) -> str:
       """Validate value is a PEP 508 / PyPI distribution name."""
       if not _PACKAGE_NAME_RE.match(value):
           message = f'Invalid package name: {value!r}'
           raise ArgumentTypeError(message)
       return value
   ```

3. Update the `parse_args` `type=check_alpha_numeric` reference to
   `type=validate_package_name`.

### Changes (`tests/test_main.py`)

1. Update the import `check_alpha_numeric` → `validate_package_name`.
2. Keep a valid-name test (`'mypackage'`) and add cases for the newly accepted
   names: `'my-package'`, `'my_package'`, `'my.package'`, and a mixed/edge case
   like `'a'`.
3. Update the invalid test to use a name that is still invalid under PEP 508
   (e.g. `'-bad'`, `'bad-'`, `'has space'`, or `''`) and match the new error
   message (`Invalid package name`).

### Verification

- `just check` passes (format, lint, complexity, typecheck, tests) — coverage
  must stay ≥ 95%.
- Specifically confirm: `validate_package_name('my-package') == 'my-package'`
  and `validate_package_name('my_package') == 'my_package'` no longer raise,
  while a leading/trailing-separator name (e.g. `'-bad'`) and a name with a
  space still raise `ArgumentTypeError`.
