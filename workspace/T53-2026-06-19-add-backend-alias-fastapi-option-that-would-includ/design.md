# Design Discussion

## Current State

`modernpackage` is a CLI scaffolder that **clones itself** and mutates the clone in
place. There is no facility for *adding* files to a generated package — the whole
pipeline is clone → delete → rewrite → two hardcoded stubs → `just init` → `just check`.

- CLI is one flat `ArgumentParser`; booleans use `action='store_true', default=False`
  (`main.py:350-362`); aliases are multiple option strings on one `add_argument`
  (`main.py:351-352`). Flags flow `parse_args` → `main` → `init_new_package` kwargs
  (`main.py:885-900`), mapping each Namespace attr to a keyword-only param
  (`main.py:786-795`).
- Pipeline in `init_new_package` (`main.py:796-880`): normalize name → preflight →
  dry-run short-circuit (`main.py:802-812`) → `git clone` (`main.py:814-827`) →
  `_write_package_metadata` (`main.py:829-836`) → `_strip_scaffolding` (`main.py:838`) →
  `just init <module>` (`main.py:841-859`) → `just check` (`main.py:861-868`).
- `_strip_scaffolding` (`main.py:554-571`) deletes a fixed tuple
  (`_SCAFFOLDING_PATHS_TO_DELETE` = `modernpackage/main.py`, `tests/test_e2e.py`,
  `docs`, `BACKLOG.md`; `main.py:502-507`), writes two stubs (`_TEST_MAIN_STUB`,
  `_README_STUB`; `main.py:514-528`) that **retain the literal `modernpackage` token**
  so `just init`'s rename sed rewrites them (`main.py:511-513`), then strips
  `[project.scripts]` via `_remove_project_scripts` (`main.py:531-551`).
- `just init` (`Justfile:60-74`) renames the token with
  `git grep -l 'modernpackage' | xargs sed` (tracked files only), resets the version,
  `mv modernpackage <name>`, re-inits git, single commit. `_RESET_VERSION='0.0.1'` is
  convention-coupled to `Justfile:68`.
- Dry-run preview (`_format_dry_run_plan`, `main.py:599-635`) reports clone target,
  metadata substitutions, and the two `just init` outcomes; it does **not** enumerate
  strip/stub actions.
- Gates the result must pass: ruff `select=["ALL"]`, line-length 88, mccabe ≤ 8, mypy
  strict, and `--cov-fail-under=95.0` over `--cov=modernpackage` with `-m 'not e2e'`
  (`pyproject.toml:40,57,66-79,81-89`). The single e2e test scaffolds for real and
  asserts the generated package passes `just check` (`test_e2e.py:53-116`).
- Backend behaviour is fully specified in `docs/fastapi_backend.md` and
  `docs/containerization.md` as *illustrative, not-yet-committed* templates
  (`fastapi_backend.md:7-8`, `containerization.md:5-9`).

## Desired End State

`modernpackage <name> --backend` (alias `--fastapi`) produces a package that additionally
contains a working FastAPI service: app factory with `lifespan` engine/sessionmaker,
async SQLAlchemy 2.0 + asyncpg DI, a DB-aware health endpoint, Alembic async migrations,
a `Containerfile` + `compose.yml` (app + Postgres, migration-gated), and `just migrate` /
`just makemigration` recipes. Without the flag, output is **byte-for-byte unchanged** from
today.

Verify by: (1) unit tests for the new flag/alias and for backend-file injection on a
`tmp_path` clone; (2) an extended e2e test that scaffolds `--backend` and asserts the
generated package's `just check` passes and `/readyz` + migration recipes exist.

## Patterns to Follow

- **Store-true alias flag**: copy `-v/--version` shape (`main.py:350-356`); pass
  `'--backend', '--fastapi'` to one `add_argument(action='store_true')`.
- **Flag threading**: add a keyword-only `backend: bool = False` param to
  `init_new_package` (`main.py:786-795`) and pass `backend=parsed_args.backend`
  (`main.py:890-900`).
- **Token-survival contract**: any injected file that references the module must contain
  the literal `modernpackage` token so the existing rename sed handles it
  (`main.py:511-513`, `Justfile:62-67`). Do **not** add a second rename mechanism.
- **TOML table removal/append**: mirror `_remove_project_scripts` line-surgery style
  (`main.py:531-551`) for any pyproject edits; reuse `_toml_escape` for written values.
- **Recipe convention**: new recipes follow `<name>: sync` and run `uv run ...`
  (`Justfile:8-42`); migration recipes map to the documented Alembic commands
  (`fastapi_backend.md:304-312`).
- **Subprocess seam**: any new subprocess call uses `Popen` and is patched in tests as
  `patch('modernpackage.main.Popen')` with the byte-tuple `communicate` mock
  (`test_main.py:292-310`).
- **Graceful pyproject boundary**: missing-file paths return/notice, not raise
  (`main.py:452-458`, `main.py:539-542`).

Patterns to **avoid**: do not extend the Justfile's `git grep` to `--untracked`
(surgical-change violation); do not inline the entire backend as string constants
(would bloat `main.py` — split into files per CLAUDE.md §7).

## Design Decisions

1. **`--backend` is a store-true boolean with `--fastapi` as a true alias** — only one
   backend type exists, and a value-taking option would make a boolean alias incoherent.
   Matches the existing store-true pattern (`main.py:350-362`). *(Assumption: "option"
   in the task means a flag, not `--backend=<name>`.)*
2. **Inject via copy-tree from committed template data, not inline stubs or
   template-repo inversion** — backend files live in a top-level `backend_template/`
   directory committed to the modernpackage repo and shipped as package data (extend
   `[tool.hatch.build] include`, `pyproject.toml:49-51`). A new module-private
   `_add_backend(package_path)` copies the tree into the clone with `shutil.copytree`.
   Rejected alternatives: (a) inline string constants — would bloat `main.py`;
   (b) committing the backend into the package and *stripping it when the flag is
   absent* — would force the template repo to carry heavyweight FastAPI deps, tank its
   own coverage, and add fragile conditional-removal to the common (no-backend) path.
   The copy approach keeps the default path **identical to today**.
3. **Make injected files tracked before `just init`** — add one
   `git -C <clone> add -A` `Popen` call after `_add_backend` and before `just init`,
   so the copied files (which carry the `modernpackage` token) are seen by
   `git grep -l` and renamed by the existing sed (`Justfile:62-67`). This reuses the
   rename contract instead of duplicating it.
4. **Backend deps go in `[project.dependencies]` (PEP 621), appended by
   `_add_backend`** — fastapi, sqlalchemy[asyncio], asyncpg, alembic, and an ASGI
   server are runtime deps, not dev tooling, so PEP 621 not PEP 735
   (`fastapi_backend.md:325-334`). Pin nothing tighter than lower bounds.
5. **Health endpoint: emit `/livez` + `/readyz`, point the container HEALTHCHECK at
   `/readyz`** — reconciles the docs' `/health` (containerization) vs `/livez`+`/readyz`
   (`fastapi_backend.md:469-495`) split by adopting the richer Kubernetes-style pair and
   treating `/readyz` (the `SELECT 1` DB probe returning 503 on failure) as the
   container readiness target. *(Assumption: the `-z` pair supersedes the older
   `/health` naming.)*
6. **Migrations run as a one-shot compose service gated by
   `service_completed_successfully`** — never at app startup
   (`fastapi_backend.md:355-366`, `containerization.md:296-305`); the migration service
   appears explicitly in the generated `compose.yml` (the docs leave it as prose only).
7. **Dry-run announces backend inclusion** — `_format_dry_run_plan` gains a backend flag
   and appends a single `add FastAPI backend (app, migrations, container, recipes)` line
   when set (`main.py:599-635`), keeping the existing "level the code knows" granularity.
8. **`_add_backend` runs in the same slot as `_strip_scaffolding`** (after metadata
   write, before `just init`; `main.py:836-838`) so injection, rename, and the single
   commit all capture one clean tree.

## What We're NOT Doing

- Not changing output for runs **without** `--backend`.
- Not adding a generic template-rendering/file-injection engine — only the one
  `_add_backend` copy step for this feature.
- Not committing the FastAPI backend *into* the scaffolder's own package or running it
  under the repo's own lint/typecheck/coverage (it lives as inert package data).
- Not modifying the `just init` rename sed, `_RESET_VERSION` coupling, or the metadata
  rewrite logic.
- Not supporting multiple/selectable backends, ORMs, or databases.
- Not provisioning real infra, CI deployment, or non-Postgres engines.

## Open Risks

- **`git add -A` ordering / `.gitignore`**: copied files under a path matched by the
  cloned `.gitignore` (e.g. `__pycache__`) would be skipped by `git grep`; the template
  data must contain only source files, and tests must confirm the token rename reaches
  every injected file.
- **Coverage on the generated side**: the backend ships with its own tests so the
  generated package still clears `--cov-fail-under=95.0` (`pyproject.toml:40`); if those
  tests are thin, scaffolded `just check` fails. The e2e test must catch this.
- **Template-data drift**: because `backend_template/` is excluded from the repo's own
  ruff/mypy, backend source can rot silently — the extended e2e test is the only guard;
  weigh adding a lightweight lint pass over `backend_template/`.
- **New subprocess call**: every existing `Popen` test sets a `side_effect` sequence
  (`test_main.py:378-407`); adding `git add -A` shifts those sequences and will require
  updating existing tests — a known, mechanical change to flag during planning.
- **Dependency availability**: `pip-audit` (`Justfile:41-42`) and `uv sync` must resolve
  the new backend deps in the generated package; a yanked/vulnerable pin would fail
  `just check`.
