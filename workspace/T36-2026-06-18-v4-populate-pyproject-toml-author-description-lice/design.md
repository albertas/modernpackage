# Design Discussion

## Current State

`init_new_package` already receives all five metadata values but throws them
away. Its signature takes keyword-only `author_name`, `author_email`,
`description`, `package_license`, `repository_url` (`main.py:373-381`), then
immediately discards them: `del author_name, author_email, description,
package_license, repository_url` (`main.py:385`). The `del` is documented as
plumbing "for later V4 work (writing metadata into pyproject.toml); not yet
consumed."

The function then performs three subprocess steps, all against
`new_package_path` (`Path.cwd() / module_name`):

1. **clone** the template from GitHub (`main.py:390-403`)
2. **`just init`** in the clone (`main.py:405-424`) — runs the `Justfile`
   recipe (`Justfile:59-73`) that seds `modernpackage` → the new name across
   all files, resets the version to `0.0.1`, renames the package dir, and makes
   an initial git commit. It does **not** touch author/email/description/
   license/URL.
3. **`just check`** (`main.py:426-443`) — validates the scaffold.

`main()` resolves precedence in `parse_args()` and maps the Namespace into the
kwargs (`main.py:455-462`), renaming `.license` → `package_license`.

The template `pyproject.toml` (which the generated package receives verbatim,
pre-sed) holds the placeholders the task must replace:

- `[project].authors = [{name = "Name Surname", email = "email@example.com"}]`
  (`pyproject.toml:3-5`)
- `[project].description = "Package configuration example using bleeding edge
  toolset."` (`pyproject.toml:6`)
- **License has no dedicated field** — only the trove classifier
  `"License :: OSI Approved :: MIT License"` (`pyproject.toml:11`)
- `[project.urls].homepage = "https://github.com/albertas/modernpackage"`
  (`pyproject.toml:20-21`)

Only `tomllib` (stdlib, read-only) is wired in (`main.py:6`); no TOML writer is
imported or declared anywhere.

## Desired End State

After `init`, the generated package's `pyproject.toml` reflects the values the
user supplied (via flag/env/git/config, already resolved by `parse_args`):

- supplied `author_name` replaces `"Name Surname"`; supplied `author_email`
  replaces `"email@example.com"` (independently — either can be set without the
  other)
- supplied `description` replaces the placeholder description
- supplied `package_license` is written as a `[project].license = "<value>"`
  SPDX string, and the MIT trove classifier line is removed
- supplied `repository_url` replaces the `homepage` URL value

When a value is `None` (not resolved from any source), the corresponding
placeholder is left untouched — and the `homepage` placeholder, still
containing `modernpackage`, is renamed by `just init`'s sed pass as today.

**Verification:** a new unit test asserts the resulting file contents for a
fully-populated and a partially-populated case; the e2e test asserts the
on-disk generated `pyproject.toml` contains the supplied values and that
`just check` still passes (exit 0).

## Patterns to Follow

- **Read pattern for the per-user config** (`_load_config_file`,
  `main.py:219-240`) shows the codebase convention: `Path.open('rb')` +
  graceful degradation (print a notice, return empty) when the file is missing
  or unreadable. Mirror this resilience for the write step.
- **Empty/None-as-unset coercion** (`_config_file_default`, `main.py:243-253`)
  — only act on non-empty values. Write step does the same: skip fields whose
  value is `None`.
- **Module-private `_`-prefixed helpers** with focused responsibility
  (`_apply_config_file_defaults`, `main.py:256-274`) — add the new writer as a
  private helper, unit-tested by importing it directly.
- **Subprocess + on-disk sed transforms** in `Justfile:59-73` are the existing
  scaffolding mechanism. **Do NOT extend the Justfile** to carry metadata:
  passing arbitrary author names/descriptions/URLs through `sed` requires
  fragile shell escaping. Python `str.replace` on known placeholder literals is
  safer and keeps the values in the language that already resolved them.
- **Graceful boundary degradation** (CLAUDE/best-practices "degrade gracefully
  at process/external boundaries") — missing `pyproject.toml` → notice +
  continue, not a crash.

## Design Decisions

1. **Targeted string replacement, not a TOML round-trip** — Use
   `Path.read_text()` → `str.replace(placeholder, value)` → `write_text()`.
   A full `tomllib`-read / writer round-trip would require a new dependency
   (none declared; `tomli-w` is only transitive per research) and would destroy
   the template's comments, ordering, and formatting — which matter because the
   repo is its own template. Replacing exact placeholder literals is surgical.

2. **Write step is a private helper `_write_package_metadata(package_path,
   *, ...)`** called inside `init_new_package`. Keeps `init_new_package`
   readable and lets the writer be unit-tested directly against a `tmp_path`
   fixture (matching the `_`-helper test convention).

3. **Hook point: after clone, before `just init`** — so the metadata is present
   in the package's *initial* git commit (made by `just init`), rather than
   left as an uncommitted edit. The `modernpackage` → name sed pass then runs
   over our values; author/email/description/license never contain that token,
   so they are safe. (See Open Risks for `repository_url`.)

4. **Independent author name/email replacement** — replace `"Name Surname"` and
   `"email@example.com"` as two separate string substitutions, because their
   precedence chains differ (name/email have a git-config fallback; the others
   do not) and either may be `None` independently.

5. **License → `[project].license` SPDX field + drop the MIT classifier** — the
   input is a free-form string (e.g. `MIT`, `Apache-2.0`); no design record
   prescribes a layout. Writing a PEP 639 `license = "<value>"` SPDX string is
   the modern, tooling-supported form and avoids fabricating an invalid trove
   classifier from an arbitrary string. To avoid a contradictory hardcoded MIT
   classifier, remove the `"License :: OSI Approved :: MIT License"` line when a
   license value is supplied; leave it when none is supplied.

6. **TOML-escape values before insertion** — a small helper escapes `\` and `"`
   so a value containing quotes can't produce invalid TOML. Keeps replacement
   robust without a writer library.

7. **Skip `None` fields; no-op `replace` is safe** — only supplied values are
   written. If a placeholder is absent (template drift), `str.replace` is a
   harmless no-op rather than an error.

8. **Missing `pyproject.toml` → notice + continue** — consistent with Decision 6
   graceful degradation, and it lets the existing `Popen`-mocked unit tests
   (which never create a real clone) pass unchanged.

## What We're NOT Doing

- Not adding a TOML-writer dependency (`tomli-w`, `tomlkit`) or any new runtime
  dep.
- Not extending the `Justfile` `init` recipe or passing metadata through `sed`.
- Not validating or normalizing the license string into a canonical SPDX
  identifier (it stays a free-form value, matching today's `--license`).
- Not touching unrelated `[project]` keys (`name`, `readme`, `requires-python`,
  `version`, `dependencies`, `scripts`) or any `[tool.*]` tables.
- Not changing CLI parsing, precedence resolution, or the kwarg mapping in
  `main()` — those already work.
- Not reformatting or reordering the template `pyproject.toml`.

## Open Risks

- **`repository_url` containing `modernpackage`** — because the write happens
  before `just init`'s sed pass, a user-supplied URL containing the literal
  token would be rewritten to the new package name. Low likelihood; accepted in
  exchange for clean initial-commit metadata. If this surfaces, move the write
  to after `just init`.
- **Template drift** — placeholder literals are matched exactly. If
  `pyproject.toml` placeholders change, replacements silently no-op. Mitigated
  by the e2e test asserting the generated contents.
- **License layout is a judgment call** (Decision 5) — no `docs/` record
  prescribes SPDX-field vs classifier. If a maintainer prefers keeping the
  classifier, the decision is cheap to reverse since it is isolated in the
  writer helper.
- **Unit-test coverage** — the 95% `--cov-fail-under` gate (`pyproject.toml:40`)
  means the new helper's branches (each field present/absent, missing file)
  must be exercised by the direct `tmp_path` unit test.

---

Next: run `/lifecycle:4_structure workspace/T36-2026-06-18-v4-populate-pyproject-toml-author-description-lice/`
