# Structure Outline

## Approach

Add one module-private writer helper, `_write_package_metadata`, that reads the
freshly-cloned `pyproject.toml`, applies targeted `str.replace` substitutions
for each supplied metadata value (TOML-escaped), and writes it back. Call it
inside `init_new_package` **after clone, before `just init`** so the values land
in the package's initial commit and survive the `modernpackage`→name sed pass.
`None` fields and a missing `pyproject.toml` are no-ops. No new dependency, no
TOML round-trip, no `Justfile` change. (design.md Decisions 1–8.)

The feature is small and has no DB/API/UI layers; the "vertical" axis here is
**per-behavior**: each slice adds a substitution behavior end-to-end (escape →
writer branch → wired into `init_new_package` → directly unit-tested), and the
final slice proves the real on-disk transform via e2e.

---

## Phase 1: Writer foundation + plain-string fields

Establishes the escape helper, the `_write_package_metadata` skeleton (read /
missing-file degradation / write-back), the hook call inside
`init_new_package`, and the four plain-placeholder substitutions: author name,
author email, description, and `homepage` URL. Each is an independent
`str.replace` of a known literal; `None` values are skipped.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_toml_escape(value: str) -> str` — new; escapes `\` then `"`.
- `_write_package_metadata(package_path: Path, *, author_name: str | None, author_email: str | None, description: str | None, package_license: str | None, repository_url: str | None) -> None`
  — new. Reads `package_path / "pyproject.toml"`; if absent, prints a `[dim]`
  notice and returns. Applies replacements for each non-`None` field:
  - `"Name Surname"` → escaped `author_name`
  - `"email@example.com"` → escaped `author_email`
  - `"Package configuration example using bleeding edge toolset."` → escaped `description`
  - `"https://github.com/albertas/modernpackage"` → escaped `repository_url`
  (License left for Phase 2.) Writes file back only if changed.
- `init_new_package` (`main.py:373`): remove the `del …` line (`main.py:385`);
  after the clone `returncode` check (`main.py:403`) and before the `just init`
  block, call `_write_package_metadata(new_package_path, author_name=…, …)`
  forwarding all five kwargs.

**Verify**: `just test` passes. New unit tests import the helper directly
(`from modernpackage import main; main._write_package_metadata`) against a
`tmp_path` containing a copy of the template `pyproject.toml`:
- fully-populated call → file contains supplied name/email/description/URL and
  none of the four placeholder literals remain.
- all-`None` call → file byte-identical to input.
- missing `pyproject.toml` → returns without raising (assert no exception).
- a value containing `"` is escaped (e.g. `Acme "Inc"` → `\"` present, valid).
Existing `Popen`-mocked tests (`test_init_new_package*`) still pass: the clone
is mocked so no real file exists → writer hits the missing-file branch and
returns. Confirm with `just test -- -k init_new_package` (3 `Popen` calls
unchanged).

---

## Phase 2: License field + classifier removal

Extends `_write_package_metadata` with the license behavior: when
`package_license` is supplied, insert `license = "<escaped>"` into `[project]`
and remove the hardcoded MIT trove classifier line; when `None`, leave both
untouched. (design.md Decision 5.)

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- In `_write_package_metadata`, add a `package_license` branch:
  - insert `license = "<_toml_escape(package_license)>"` as a new `[project]`
    key (e.g. replace the `description = …` line with `description …\nlicense = …`,
    or insert after `name = "modernpackage"` — exact anchor chosen at plan time
    from the template literal).
  - remove the line `    "License :: OSI Approved :: MIT License",\n` from
    `classifiers`.

**Verify**: `just test` passes. New unit tests on `tmp_path` template copy:
- `package_license="Apache-2.0"` → file contains `license = "Apache-2.0"` and
  does NOT contain `License :: OSI Approved :: MIT License`; remaining
  classifiers intact (assert `Natural Language :: English` still present).
- `package_license=None` → MIT classifier line still present, no `license =`
  key added.
- `tomllib.loads(result)` parses without error (proves valid TOML after edits).

---

## Phase 3: e2e assertion of generated contents

Proves the real clone→write→`just init` transform produces a `pyproject.toml`
with the supplied values and still passes `just check`. Because the e2e test
clones directly (it does not call `init_new_package`,
`test_e2e.py:52-83`), it must invoke `_write_package_metadata` itself at the
same hook point (after clone, before `just init`).

**Files**: `tests/test_e2e.py`

**Key changes**:
- New `@pytest.mark.e2e` test (or extend `test_scaffolded_package_passes_check`):
  after the successful `git clone` (`test_e2e.py:62-63`) and before `just init`
  (`:65`), call `main._write_package_metadata(destination, author_name="Test
  Author", author_email="test@example.org", description="An e2e generated
  package.", package_license="Apache-2.0", repository_url="https://example.org/repo")`.
  After `just init`, read `destination / "pyproject.toml"` and assert it
  contains each supplied value and `license = "Apache-2.0"`, lacks the MIT
  classifier, and lacks the original placeholder literals. Keep the existing
  `just check` exit-0 assertion (`:82-83`).

**Verify**: `just test -- -m e2e` (or the project's e2e recipe) passes on a host
with `git`/`just` on PATH (test self-skips otherwise, `test_e2e.py:54-56`);
generated `pyproject.toml` contains `Test Author`, `test@example.org`,
`license = "Apache-2.0"`; `just check` returns 0.

---

## Testing Checkpoints

- **After Phase 1**: `_toml_escape` and `_write_package_metadata` exist;
  author/email/description/URL substitutions work and are unit-tested; the
  writer is wired into `init_new_package`; all existing `Popen`-mocked tests
  still green; `just check` on the tool repo passes (95% coverage gate met for
  the new branches via direct `tmp_path` tests, `pyproject.toml:40`).
- **After Phase 2**: license field written and MIT classifier removed when
  supplied, untouched when absent; result still parses as valid TOML; unit
  tests cover both license branches.
- **After Phase 3**: real clone→write→init produces correct on-disk metadata
  and the scaffold still passes `just check`.

### Notes / risks carried from design.md
- `repository_url` containing the literal `modernpackage` would be rewritten by
  `just init`'s sed (Open Risk). Accepted; not handled this iteration.
- Placeholder literals are matched exactly — template drift silently no-ops
  (mitigated by the Phase 3 e2e content assertions).
