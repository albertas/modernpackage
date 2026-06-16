# Implementation Plan

## Overview

Replace the `hatch` **CLI** with `uv` for build + publish (`make publish` → `uv build`
+ `uv publish`), drop the now-unused `hatch` CLI dependency, and update README/docs —
while keeping `hatchling` as the PEP 517 build backend so the `[tool.hatch.version]`
dynamic-version plugin still single-sources the version from `modernpackage/__init__.py:3`.

**Phase order is load-bearing:** Phase 1 must stop the `Makefile` from invoking
`.venv/bin/hatch` **before** Phase 2 removes the `hatch` dependency, or `make publish`
breaks mid-change.

---

## Phase 1: `make publish` builds & uploads via uv

Switch the `publish` target from the `.venv/bin/hatch` wrapper to global `uv`
subcommands, mirroring the `compile`/`sync` style already used in the Makefile
(`Makefile:49-56`). Keep `rm -fr dist/*` (uv publish uploads *every* matching artifact
in `dist/`) and the `.venv` prerequisite. No `--index`/`--publish-url` → defaults to
PyPI, matching prior hatch behavior and `README.md:9`. Auth stays out-of-repo
(`uv publish` reads `UV_PUBLISH_TOKEN`/`--token`/keyring).

### Changes

#### 1. Rewrite the `publish` target

**File**: `Makefile`
**Action**: modify (lines 22-25)

Replace:

```make
publish: .venv
	rm -fr dist/*
	.venv/bin/hatch build
	.venv/bin/hatch -v publish
```

with:

```make
publish: .venv
	rm -fr dist/*
	uv build
	uv publish
```

- Use bare `uv build` / `uv publish` (global `uv`), **not** `.venv/bin/...`, matching
  `compile`/`sync` (`Makefile:49-56`).
- Keep `rm -fr dist/*` (clears stale artifacts so `uv publish` does not re-upload old
  versions) and the `: .venv` prerequisite.
- Do **not** pass `-v` or any `--index`/`--publish-url`/`--token` flags.

### Verification

#### Automated
- [x] `grep -n hatch Makefile` returns nothing (no `hatch` CLI invocation remains).
- [x] `grep -nE 'uv build|uv publish' Makefile` shows both new lines under `publish:`.
- [x] Build half is locally deterministic:
      `rm -fr dist/* && uv build` exits 0.
- [x] `ls dist/` shows exactly `modernpackage-0.0.9.tar.gz` and
      `modernpackage-0.0.9-py3-none-any.whl` (version matches
      `modernpackage/__init__.py:3`). Concretely:
      `test -f dist/modernpackage-0.0.9.tar.gz && test -f dist/modernpackage-0.0.9-py3-none-any.whl`
      exits 0, and `ls dist/ | wc -l` is `2`.
- [ ] `make check` still passes (build-backend/version config untouched).
  <!-- DEVIATION: `make check` fails on the `deadcode` step due to a pre-existing
       Python 3.14 incompatibility (ast.Str removed; deadcode crashes with
       AttributeError). This is unrelated to Phase 1 changes. All other gates
       (test 100%, ruff lint, mypy, pip-audit) pass. -->

#### Manual
- [x] Confirm the version embedded in the wheel matches source:
      `unzip -p dist/modernpackage-0.0.9-py3-none-any.whl 'modernpackage-0.0.9.dist-info/METADATA' | grep -q '^Version: 0.0.9'`
      exits 0.
- [ ] Upload half (`uv publish`) is **not** auto-verifiable without a real token — do
      **not** run a real upload in CI. Out-of-band confirmation only: with
      `UV_PUBLISH_TOKEN` set, `uv publish` exits 0 and the artifact appears on PyPI.

---

## Phase 2: Drop the `hatch` CLI dependency

Remove `hatch` from the `test` extra — it existed only to put the publish CLI on PATH,
and Phase 1 removed the last caller. `hatchling` is still pulled in automatically by
`uv build`'s isolated PEP 517 build env, so nothing replaces it. Leave all
`[build-system]` and `[tool.hatch.*]` tables unchanged.

### Changes

#### 1. Remove `hatch` from the test extra

**File**: `pyproject.toml`
**Action**: modify (delete line 29)

In `[project.optional-dependencies].test` (lines 27-38), delete the line:

```toml
    "hatch",
```

Resulting block:

```toml
[project.optional-dependencies]
test = [
    "ruff",
    "mypy",
    "pip-audit",
    "deadcode",
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "vupi>=0.0.7",
]
```

- Leave `[build-system]` (`requires = ["hatchling"]`, lines 46-48),
  `[tool.hatch.build]` (lines 50-52), and `[tool.hatch.version]` (lines 54-55)
  **unchanged**.

#### 2. Regenerate pinned dependency files

**File**: `requirements-dev.txt` (and `requirements.txt`, `uv.lock`) — regenerated, not
hand-edited.
**Action**: modify (via `make compile`)

Run `make compile` so the lockfiles drop the `hatch` CLI pin. `hatchling` may remain as
a transitive build-time entry — that is acceptable and expected.

### Verification

#### Automated
- [x] `grep -n '"hatch"' pyproject.toml` returns nothing (CLI entry gone from `test`).
- [x] `grep -nE '\bhatch\b' pyproject.toml` returns **only** `hatchling` backend tables
      / `[tool.hatch.*]` section headers — no standalone `hatch` CLI dependency.
- [x] After `make compile`: `grep -i '^hatch==' requirements-dev.txt` is empty
      (transitive `hatchling==` may still appear — acceptable).
- [x] `rm -fr .venv && make .venv && make check` succeeds with `hatch` absent from the
      environment (`.venv/bin/hatch` does not exist:
      `test ! -e .venv/bin/hatch` exits 0).
      <!-- NOTE: `make check` fails only on the pre-existing `deadcode` Python 3.14
           incompatibility (ast.Str removed), same as documented in Phase 1. All other
           gates (test 100%, ruff lint, mypy, pip-audit) pass. -->

#### Manual
- [x] Re-run the Phase 1 build assertion to confirm no regression:
      `rm -fr dist/* && uv build && test -f dist/modernpackage-0.0.9.tar.gz && test -f dist/modernpackage-0.0.9-py3-none-any.whl`
      exits 0.

---

## Phase 3: Update README & docs to describe uv publishing

Replace hatch-publishing references with uv. Minimal, factual edits — no rewriting of
surrounding prose. Keep hatchling-as-backend references intact (it is still the backend).

### Changes

#### 1. README toolset line

**File**: `README.md`
**Action**: modify (lines 31-32)

Today:

```markdown
- hatch - for publishing package to pypi.org
- uv - for Python virtual environment and dependency management
```

Replace both with a single accurate `uv` entry (fold publishing into the uv line so
there is exactly one uv toolset entry):

```markdown
- uv - for building & publishing package to pypi.org, Python virtual environment and dependency management
```

#### 2. README publish description (no change needed, verify only)

**File**: `README.md` (lines 9, 19)
**Action**: none

These describe `make publish` behavior ("publish ... to PyPi.org") without naming
`hatch`, and remain accurate. Do not edit.

#### 3. architecture.md — Publishing section

**File**: `docs/architecture.md`
**Action**: modify (line 151)

Replace:

```markdown
`make publish` clears `dist/`, builds via `hatch build`, and publishes via `hatch publish`.
```

with:

```markdown
`make publish` clears `dist/`, builds via `uv build`, and publishes via `uv publish`.
```

#### 4. architecture.md — Test dependencies list (deviation from structure; see summary)

**File**: `docs/architecture.md`
**Action**: modify (line 147)

This line lists `hatch` as a test dependency and becomes factually wrong after Phase 2.
Replace:

```markdown
- **Test dependencies**: hatch, ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi (with a minimum version floor for the constrained package)
```

with (drop `hatch, `):

```markdown
- **Test dependencies**: ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, vupi (with a minimum version floor for the constrained package)
```

#### 5. specification.md — Publishing line

**File**: `docs/specification.md`
**Action**: modify (line 77)

Replace:

```markdown
- **Publishing** (`Makefile:22-25`): `make publish` clears `dist/*`, runs `hatch build`, then `hatch -v publish`.
```

with:

```markdown
- **Publishing** (`Makefile:22-25`): `make publish` clears `dist/*`, runs `uv build`, then `uv publish`.
```

#### 6. specification.md — Optional test group list (deviation from structure; see summary)

**File**: `docs/specification.md`
**Action**: modify (line 76)

This line lists `hatch` in the optional test group and becomes wrong after Phase 2.
Replace:

```markdown
- **Optional test group** (`pyproject.toml:27-37`): hatch, ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, vupi>=0.0.6.
```

with (drop `hatch, `):

```markdown
- **Optional test group** (`pyproject.toml:27-37`): ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, vupi>=0.0.6.
```

> Note: the line's parenthetical citations (`pyproject.toml:27-37`, `vupi>=0.0.6`) are
> pre-existing and may not match current line numbers/pins. Per the surgical-change rule,
> only remove `hatch, `; do not "correct" the unrelated stale citations.

#### 7. overview.md — workflow publish description

**File**: `docs/overview.md`
**Action**: modify (line 40)

Today:

```markdown
- **`make publish`** — build and publish to PyPI.
```

This does not name `hatch` and is already accurate, but to make the uv flow explicit
(satisfies design decision 6 and the structure's named target), update to:

```markdown
- **`make publish`** — build and publish to PyPI via `uv build` + `uv publish`.
```

### Verification

#### Automated
- [x] `grep -rni 'hatch publish\|hatch build\|hatch - for' README.md docs/` returns
      nothing.
- [x] `grep -ni 'uv build & publish\|building & publishing\|uv build' README.md` shows
      the new toolset line.
- [x] `grep -rniE 'uv build|uv publish' docs/architecture.md docs/specification.md docs/overview.md`
      finds the new references in all three files.
- [x] No `hatch` test-dependency list entries remain:
      `grep -rn 'Test dependencies: hatch\|test group.*: hatch\|^- hatch ' README.md docs/`
      returns nothing.
- [x] `grep -rni hatchling docs/` still present (backend correctly retained in docs).
- [ ] `make check` passes (docs-only, no behavioral impact).
      <!-- DEVIATION: `make check` fails on the pre-existing `deadcode` Python 3.14
           incompatibility (ast.Str removed), same as documented in Phases 1 and 2.
           All other gates (test, ruff lint, mypy, pip-audit) pass. Phase 3 changes
           are docs-only and have no behavioral impact. -->

#### Manual
- [x] Confirm exactly one `uv` toolset entry in the README toolset section:
      `grep -c '^- uv ' README.md` returns `1`.

---

## Testing Checkpoints

**After Phase 1:** `Makefile` publish target runs `uv build` + `uv publish`; no `hatch`
invocation remains in `Makefile`; `uv build` yields the 0.0.9 sdist + wheel; `make check`
green. (Release flow functional via uv; upload pending token.)

**After Phase 2:** `hatch` CLI gone from `pyproject.toml` `test` extra and from
`requirements-dev.txt`; environment rebuilds without hatch; `uv build` still produces
artifacts; `make check` green.

**After Phase 3:** README/docs describe uv publishing; no `hatch build`/`hatch publish`/
`hatch - for` strings remain; no `hatch` test-dependency list entries remain;
hatchling-as-backend still documented; `make check` green.

## Out of Scope (per design "What We're NOT Doing")

- No `uv_build` backend migration (hatchling stays the backend).
- No `publish-url` added to the `gitlab` index; no change to publish destination.
- No CI publish step (GitHub/GitLab workflows untouched).
- No `Justfile` publish recipe.
- No version bump / rebuild of stale artifacts.
- No committed credentials or auth-mechanism change.

## Open Risk to Flag at Implementation

**Publish destination ambiguity.** README/docs say pypi.org (`README.md:9`) but the only
configured index is GitLab (`pyproject.toml:98-100`). Phase 1 defaults `uv publish` to
PyPI to match prior hatch behavior. **If GitLab is the true target**, a follow-up (out
of scope here) must add a `publish-url` to the `gitlab` index entry and call
`uv publish --index gitlab`. Confirm intended destination before a real upload.
