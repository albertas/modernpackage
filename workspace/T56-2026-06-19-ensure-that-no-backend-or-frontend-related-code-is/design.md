# Design Discussion

## Current State

The scaffolder (`modernpackage/main.py`) clones the source repo, mutates the
clone, and optionally injects backend/frontend templates. Backend/frontend are
already opt-in behind `--backend`/`--fastapi` and `--fullstack`/`--reactjs`
(`main.py:363-376`, gated at `main.py:1065-1066`).

The default (no-flag) guarantee is **already largely enforced** by stripping:

- `_strip_scaffolding` (`main.py:640-657`) unconditionally deletes
  `_SCAFFOLDING_PATHS_TO_DELETE` (`main.py:519-526`), which includes
  `backend_template` and `frontend_template`. So template trees never reach a
  generated package, even when flags are present (re-injection copies from the
  installed package path, not the clone — `main.py:514-518,552-561`).
- The source `pyproject.toml` ships `dependencies = []` (`pyproject.toml:18`)
  and the source `Justfile` carries no FastAPI/React recipes (`Justfile:53-77`).
  Backend/frontend deps and recipes exist only as `main.py` constants
  (`main.py:565-614`) appended *conditionally* by `_add_backend`/`_add_frontend`.
- `docs/` (which contains `fastapi_backend.md`, `reactjs_frontend.md`, etc.) is
  in the delete list (`main.py:519-526`), so feature docs never leak either.

What verification exists today is **partial**. The no-flag e2e test
`test_scaffolded_package_passes_check` (`test_e2e.py:53-117`) asserts only
`not (destination/'backend_template').exists()` (`test_e2e.py:108-114`). There
is **no** assertion that `frontend_template`/`frontend` are absent, no check
that `pyproject.toml` lacks fastapi/sqlalchemy/asyncpg/alembic/uvicorn, no check
that the `Justfile` lacks `migrate`/`frontend-*` recipes, and no content scan
for the import strings (`import fastapi`, React/Vite markers).

## Desired End State

A package scaffolded with no extra flags provably contains **zero** backend or
frontend code, config, dependencies, recipes, or references — and a test suite
locks this in so a future change cannot silently reintroduce leakage.

Verify by: a dedicated test that scaffolds a no-flag package and asserts the
**absence** of every backend/frontend marker (directories, files, dependency
strings, recipe names, and import/source tokens). `just check` and `just test`
(`tests/test_e2e.py`, `tests/test_main.py`) pass.

## Patterns to Follow

- **Strip-list as single source of truth**: keep `_SCAFFOLDING_PATHS_TO_DELETE`
  (`main.py:519-526`) as the place that removes template trees; do not duplicate
  removal logic elsewhere. Absent paths are tolerated (`main.py:649-654`).
- **e2e test structure**: mirror `test_scaffolded_package_passes_check`
  (`test_e2e.py:53-117`) — clone local repo, `_write_package_metadata`,
  `_strip_scaffolding`, `just init`, then assert on the destination tree. Reuse
  its absence-assertion style (`test_e2e.py:108-114`).
- **Mocked unit-test style**: `tests/test_main.py` patches `Popen` and asserts
  call counts / which injectors ran (`test_main.py:296-307,1592-1603`). Follow
  this for any no-flag negative assertions at the unit level.
- **Constants drive markers**: derive the list of forbidden tokens from the
  existing injection constants — `_BACKEND_DEPENDENCIES` (`main.py:565-571`),
  `_BACKEND_RECIPES` (`main.py:579-588`), `_FRONTEND_RECIPES` (`main.py:595-614`)
  — rather than hand-copying strings, so the test tracks the constants.
- **Naming/style**: full-word identifiers, `def test_*` functions with plain
  `assert`, `tmp_path`/`monkeypatch` fixtures (per `Code Best Practices`).

Patterns to **avoid**: do not add a runtime dependency or a separate config
file to express the forbidden-token list; keep it inline in the test, derived
from `main.py` constants. Do not weaken graceful-degradation boundaries
(`main.py:467-472,892-898`) — they are intentional.

## Design Decisions

1. **Primary deliverable is verification, not behavior change** — the no-flag
   strip already prevents leakage; research found no actual leak. The task
   explicitly asks to "add verification to keep it that way," so the work is a
   comprehensive negative test plus any small gap-closing. *Assumption*: no
   behavioral bug exists; if the new test surfaces one, fix it minimally.

2. **One new e2e test for the no-flag guarantee** — add
   `test_scaffolded_package_has_no_backend_or_frontend` to `tests/test_e2e.py`,
   scaffolding via the same flow as the existing no-flag test. It asserts:
   - dirs absent: `backend_template`, `frontend_template`, `frontend`,
     `migrations`, plus files `alembic.ini`, `compose.yml`, `Containerfile`,
     `.dockerignore`;
   - `pyproject.toml` still reads `dependencies = []` and contains none of
     fastapi/sqlalchemy/asyncpg/alembic/uvicorn/httpx;
   - `Justfile` contains none of `migrate`/`makemigration`/`migration-check`/
     `frontend-`/`generate-client`;
   - source tree contains no `import fastapi`/`sqlalchemy`/React/Vite tokens.

   *Why e2e*: only a real scaffold exercises strip + `just init` together; this
   catches the whole pipeline, matching `test_e2e.py:53-117`.

3. **Add a cheap mocked unit guard too** — in `tests/test_main.py`, assert that
   no-flag `init_new_package` invokes neither `_add_backend` nor `_add_frontend`
   (complementing existing `test_main.py:1592-1603,1808-1820`). *Why*: fast
   regression signal without the full clone, and it pins the gate at
   `main.py:1065-1066`.

4. **Strengthen the existing no-flag e2e minimally rather than replace it** —
   leave `test_scaffolded_package_passes_check` as-is (it validates `just check`
   passes); the new test owns the absence assertions. *Why*: surgical, avoids
   reworking a passing test (CLAUDE.md §3).

5. **Forbidden-token list derived from constants** — build the marker set in the
   test from `main._BACKEND_DEPENDENCIES`, `main._BACKEND_RECIPES`,
   `main._FRONTEND_RECIPES` where practical, plus a small explicit token list
   for import strings. *Why*: keeps the test honest as constants evolve.

## What We're NOT Doing

- Not changing how `--backend`/`--fullstack` inject (out of scope; opt-in path
  stays exactly as-is).
- Not removing or editing `backend_template/`, `frontend_template/`, `docs/`, or
  their `pyproject.toml` build-include / ruff-ignore entries
  (`pyproject.toml:51,78-81`) — they are needed for the opt-in feature.
- Not adding a `--fullstack` e2e test (noted as an open gap in research, but
  outside this task's no-flag guarantee).
- Not adding new CLI flags, dependencies, or Justfile recipes to the scaffolder.
- Not refactoring `_strip_scaffolding` or the injection helpers.

## Open Risks

- **Token false-positives**: scanning source text for `alembic`/`react` could
  match incidental substrings (e.g. in comments or unrelated words). Mitigate by
  scanning specific files (`pyproject.toml`, `Justfile`) for dependency/recipe
  tokens and limiting import-string scans to the package source dir.
- **e2e cost/markers**: e2e tests are marked and excluded from default `pytest`
  (`pyproject.toml:40`, `-m 'not e2e'`); ensure the new test carries the same
  `e2e` marker so `just check` behavior is unchanged and it runs under
  `just test-e2e`.
- **`just init` token rename**: the literal `modernpackage` is retained then
  sed-renamed (`main.py:528-547`; `Justfile:62-67`); assertions must run against
  the renamed module dir, not a hardcoded `modernpackage/` path — follow the
  destination-path resolution in `test_e2e.py:97-117`.
- **Coverage gate**: new tests must not drop coverage below
  `--cov-fail-under=95.0` (`pyproject.toml:40`); negative tests add little
  executed code, so risk is low but worth confirming via `just check`.
