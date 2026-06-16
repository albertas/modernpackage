# Structure Outline

## Approach

Replace the `hatch` **CLI** with `uv` for build+publish while keeping `hatchling`
as the PEP 517 backend (so the `[tool.hatch.version]` dynamic-version plugin still
single-sources the version from `modernpackage/__init__.py:3`). Three thin vertical
slices: (1) swap the `make publish` commands to `uv build` + `uv publish`, (2) drop
the now-unused `hatch` CLI dependency, (3) update README/docs. Phase order matters:
the Makefile must stop invoking `.venv/bin/hatch` (Phase 1) **before** the `hatch`
dependency is removed (Phase 2), or publish breaks mid-change.

This is a tooling/release change with no DB/service/API/UI layers. The "vertical"
unit per slice is: the command/config that does the work + its verification. Each
slice is independently valuable and independently testable.

---

## Phase 1: `make publish` builds & uploads via uv

Switch the `publish` target from `hatch` to `uv`, mirroring the existing
global-`uv` style used by `compile`/`sync` (`Makefile:49-56`). Keep `rm -fr dist/*`
(uv publish uploads *every* matching artifact in `dist/`) and the `.venv`
prerequisite for a surgical change.

**Files**: `Makefile`

**Key changes** (`Makefile:22-25`):
```make
publish: .venv
	rm -fr dist/*
	uv build          # was: .venv/bin/hatch build
	uv publish        # was: .venv/bin/hatch -v publish
```
- No `--index`/`--publish-url` → defaults to PyPI, matching prior hatch behavior
  and `README.md:9`.
- Auth stays out-of-repo: `uv publish` reads `UV_PUBLISH_TOKEN`/`--token`/keyring.

**Verify**:
- `grep -n hatch Makefile` returns nothing (CLI no longer invoked).
- Build half is fully local & deterministic:
  `rm -fr dist/* && uv build` exits 0 and produces exactly
  `dist/modernpackage-0.0.9.tar.gz` and
  `dist/modernpackage-0.0.9-py3-none-any.whl`
  (assert with `ls dist/` — version matches `modernpackage/__init__.py:3`).
- `make check` still passes (build-backend/version config untouched).
- Upload half (`uv publish`) is NOT auto-verifiable without a token — note for
  manual/out-of-band confirmation; do not attempt a real upload in CI.

---

## Phase 2: Drop the `hatch` CLI dependency

Remove `hatch` from the `test` extra — it existed only to put the publish CLI on
PATH (Phase 1 removed the last caller). `hatchling` is still pulled in
automatically by `uv build`'s isolated PEP 517 build env, so nothing replaces it.

**Files**: `pyproject.toml`

**Key changes**:
- Delete `"hatch",` from `[project.optional-dependencies].test` (`pyproject.toml:29`).
- Leave `[build-system]` (`requires = ["hatchling"]`, `pyproject.toml:46-48`),
  `[tool.hatch.build]` (`50-52`), and `[tool.hatch.version]` (`54-55`) **unchanged**.

**Verify**:
- `grep -rn '\bhatch\b' pyproject.toml` returns **only** the retained `hatchling`
  backend tables / `[tool.hatch.*]` sections — no `hatch` CLI entry in `test`.
- `make compile` regenerates `requirements*.txt` with no `hatch==` line
  (`grep -i '^hatch==' requirements-dev.txt` is empty; `hatchling` may still appear
  transitively — acceptable).
- `make .venv && make check` succeeds with hatch absent from the environment.
- `make publish` up to `uv build` still produces the two `dist/` artifacts
  (re-run Phase 1 build assertion to confirm no regression).

---

## Phase 3: Update README & docs to describe uv publishing

Replace hatch-publishing references with uv. Minimal, factual edits — no rewriting
of surrounding prose.

**Files**: `README.md`, `docs/architecture.md`, `docs/specification.md`,
`docs/overview.md`

**Key changes**:
- `README.md:31` — Toolset line: `hatch - for publishing package to pypi.org`
  → `uv - for publishing package to pypi.org` (and fold into the existing
  `uv` line `README.md:32`, or replace in place; keep one accurate uv entry).
- `docs/architecture.md:149-151` — Publishing section: `hatch build` / `hatch
  publish` → `uv build` / `uv publish`.
- `docs/specification.md:77` — publishing-flow line → uv build+publish.
- `docs/overview.md:40` — workflow `publish` description → uv.

**Verify**:
- `grep -rni 'hatch publish\|hatch build\|hatch - for' README.md docs/` returns
  nothing.
- `grep -rni 'uv build\|uv publish' README.md docs/architecture.md
  docs/specification.md docs/overview.md` finds the new references.
- `grep -rni hatchling docs/` still present (backend correctly retained in docs).
- `make check` passes (docs-only, no behavioral impact).

---

## Testing Checkpoints

After **Phase 1**: `Makefile` publish target runs `uv build` + `uv publish`; no
`hatch` invocation remains in `Makefile`; `uv build` yields the 0.0.9 sdist+wheel;
`make check` green. (Release flow now functional via uv; upload pending token.)

After **Phase 2**: `hatch` CLI gone from `pyproject.toml` `test` extra and from
`requirements-dev.txt`; environment builds without hatch; `uv build` still
produces artifacts; `make check` green. (No stray hatch dependency.)

After **Phase 3**: README/docs describe uv publishing; no `hatch build`/`hatch
publish` strings remain; hatchling-as-backend still documented; `make check` green.

**Out of scope (per design "What We're NOT Doing")**: no `uv_build` backend
migration, no `publish-url` on the gitlab index, no CI publish step, no `Justfile`
publish recipe, no version bump, no committed credentials.

**Open risk to flag at implementation**: publish destination ambiguity — README
says pypi.org but the only configured index is GitLab (`pyproject.toml:98-100`).
Phase 1 defaults to PyPI to match prior behavior; if GitLab is the true target,
a follow-up adds `publish-url` to the index and uses `uv publish --index gitlab`.
