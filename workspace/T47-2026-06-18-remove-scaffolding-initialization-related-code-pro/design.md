# Design Discussion

## Current State

`modernpackage` is a self-replicating scaffolder. `init_new_package`
(`main.py:712-804`) clones the template, rewrites `pyproject.toml` metadata
(`_write_package_metadata`, `main.py:432-479`), runs `just init <module>`
(rename / version-reset / dir-move / git re-init, `Justfile:59-73`), then runs
`just check` as a post-scaffold gate. The clone is the **committed GitHub
template** (`_TEMPLATE_REPOSITORY_URL`, `main.py:71`).

The problem: the generated package inherits the scaffolder's own machinery
verbatim. After `just init`, the new package still contains:
- the entire clone/preflight/metadata/init CLI in `<module>/main.py`
  (`main.py:1-829`), wired as the `modernpackage`/`mp` console scripts
  (`pyproject.toml:23-25`);
- its tests — `tests/test_main.py` (~1413 lines, `test_main.py:10-33`) and
  `tests/test_e2e.py` (`test_e2e.py:53-104`);
- its docs — `docs/architecture.md`, `data_flows.md`, `invocation.md`,
  `overview.md`, `specification.md`, `vision.md`, `persona.md`,
  `backlog_formats.md`, plus `README.md`/`BACKLOG.md` that narrate the scaffold
  flow (`research.md` Q5).

`just check = check-format check-lint check-complexity check-typecheck test
audit` (`Justfile:52`); ruff/mypy target only `modernpackage tests`
(`Justfile:28-38`); pytest enforces `--cov=modernpackage --cov-fail-under=95.0
-m 'not e2e'` (`pyproject.toml:40`).

## Desired End State

A freshly scaffolded package ships **without the self-replicating CLI, its
tests, or its docs**, and still passes `just check`. After `init_new_package`:
- `<module>/main.py` is gone; `<module>/__init__.py` (version `0.0.1`) remains.
- `[project.scripts]` is removed (no dangling `main:main` entry points).
- `tests/test_main.py` is a minimal stub; `tests/test_e2e.py` is gone.
- `docs/` and the scaffolder `README.md`/`BACKLOG.md` are removed/replaced.
- The single `just init` commit captures the **already-clean** tree.

**Verification:** the existing e2e test (`test_e2e.py:53-104`), extended to drive
the new strip step, asserts the scaffolding files are absent, no `[project.scripts]`
remains, `__init__.py` contains `0.0.1`, and `just check` returns 0. New
`tmp_path` unit tests cover the strip function directly. The template repo's own
`just check` must stay green after the changes.

## Patterns to Follow

- **Clone-mutation in Python, before `just init`.** `_write_package_metadata`
  (`main.py:432-479`) already mutates the clone in Python between clone and
  `just init`. The new strip step mirrors this — same call site, same testing
  approach. Run it **before** `just init` so the rename sed
  (`Justfile:61-66`) and the single `git commit` (`Justfile:72`) operate on the
  stripped tree.
- **String-rename contract.** Stub files written with the literal
  `modernpackage` token are renamed to `<module>` by the existing
  `git grep -l 'modernpackage' | xargs sed` pass (`Justfile:61-66`). Stubs
  rely on this rather than interpolating the module name.
- **Constant-driven helpers + small functions** to stay under mccabe
  `max-complexity = 8` (`pyproject.toml:78-79`): a module-level tuple of paths
  to delete, looped over — like `_METADATA_FIELDS` driving
  `_write_package_metadata` (`main.py:132-158`).
- **SDK/seam patching in tests** on the `modernpackage.main` object
  (`test_main.py` convention) and **`tmp_path` fixtures** for filesystem work,
  exactly as `_write_package_metadata` is tested (`test_main.py:1144-1235`).
- **Naming/style:** `_`-private helpers, full-word names, `_RE`/constant
  conventions, frozen dataclasses where applicable (Code Best Practices).

Pattern to NOT follow: do **not** generate stub file contents via shell
heredocs inside the `just init` recipe — `just` runs each recipe line in its own
shell, making multi-line file writes brittle and untestable. Keep content
generation in Python.

## Design Decisions

1. **Strip in Python (`_strip_scaffolding`), not in the Justfile** — added to
   `main.py` and called from `init_new_package` between `_write_package_metadata`
   and the `just init` Popen (`main.py:762-764`). Rationale: symmetric with
   `_write_package_metadata`, unit-testable with `tmp_path`, and avoids shell
   heredocs. The e2e test (which calls `_write_package_metadata` directly,
   `test_e2e.py:66`) is extended to call `_strip_scaffolding` the same way.
2. **Run before `just init`** so the rename sed and the lone `git commit` capture
   the clean tree (no dirty working tree, no scaffolding in the initial commit).
3. **Delete `main.py` rather than ship a stub** — the task is to remove the
   self-replicating CLI; a "clean slate" package needs no placeholder. Remove
   `[project.scripts]` (`pyproject.toml:23-25`) so no entry point dangles.
4. **Keep `__init__.py`** (the package marker + hatch version source,
   `pyproject.toml:53-54`); `just init` resets it to `0.0.1` (`Justfile:67`).
5. **Replace `tests/test_main.py` with a one-test stub** that imports the package
   and asserts `__version__ == '0.0.1'`. Rationale: pytest needs ≥1 collected
   test (empty collection exits non-zero); importing the package keeps
   `--cov-fail-under=95.0` satisfied (after deleting `main.py`, the only package
   code is the `__version__` line, executed on import → ~100%). Written with the
   `modernpackage` token so sed renames the import.
6. **Delete `tests/test_e2e.py`** — it tests the scaffolder; `-m 'not e2e'`
   already excludes e2e from `just check`, so removal does not affect the gate.
7. **Delete `docs/` and replace `README.md`/`BACKLOG.md`** with a minimal generic
   `README.md` (required by `pyproject.toml:7` `readme`). Docs are not consumed by
   `just check`, but the task lists them explicitly.
8. **Tolerate absent paths and patch the seam in orchestration tests.** Existing
   `init_new_package` happy-path tests mock `Popen` with no real clone dir
   (`test_main.py:288-373`); they patch `_strip_scaffolding` on
   `modernpackage.main`. `_strip_scaffolding`'s own behavior is covered by
   dedicated `tmp_path` tests that seed a fake clone tree.
9. **Keep the diff surgical in `pyproject.toml`:** remove only `[project.scripts]`.
   Leave the `e2e` marker, `vupi` test dep, and `[tool.deadcode]` untouched
   (harmless once e2e/main are gone) to avoid scope creep.

## What We're NOT Doing

- **Not removing scaffolding recipes from the generated `Justfile`** (`init`,
  `test-e2e`, `vision`, `lifecycle`). The task enumerates the `main.py` CLI, its
  tests, and docs — not the recipe. Critically, `just init` must still exist to
  be invoked, so it cannot delete itself cleanly mid-run. The leftover recipes
  are inert and do not affect `just check`. Flagged as a follow-up.
- Not adding a hello-world / placeholder CLI to the generated package.
- Not changing the clone source, preflight, metadata-writing, or dry-run logic
  in the template scaffolder itself — only adding the strip step.
- Not altering coverage thresholds, ruff/mypy config, or `just check`
  composition.
- Not touching the template repo's own `main.py` CLI (it must remain a working
  scaffolder).

## Open Risks

- **Template `just check` regression.** `_strip_scaffolding` must be ruff-clean,
  mypy-strict, mccabe ≤ 8, and ≥95%-covered, or the template's own gate breaks.
  Mitigation: factor into small constant-driven helpers; add focused `tmp_path`
  tests.
- **Generated `Justfile` is not fully clean** — inert scaffolding recipes remain
  (see "NOT doing"). If a fully clean Justfile is required, a recipe self-strip
  or a refactor moving rename/mv/git out of `just init` is a separate task.
- **`git grep` over deleted files.** Deletions become deleted-but-tracked until
  `just init`'s `git add .` stages them; `git grep` skips them, and stub writes
  that retain the `modernpackage` token are renamed correctly. Verify ordering
  in the plan.
- **e2e cost/network.** The e2e test runs a full inner `just check` (sync +
  networked `pip-audit`), minutes-long and offline-failing
  (`test_e2e.py:7-15`); unchanged, but the extended assertions ride on it.
