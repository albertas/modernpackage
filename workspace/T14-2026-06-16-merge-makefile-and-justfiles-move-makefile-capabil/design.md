# Design Discussion

## Current State

The repo maintains two parallel task-runner surfaces that have drifted apart:

- **`Makefile`** (`Makefile:1-79`) — the canonical hub that everything actually
  invokes. Targets: `lifecycle`, `check`, `fix`, `.venv`, `publish`, `lint`,
  `fixlint`, `format`, `mypy`, `audit`, `deadcode`, `test`, `sync`, `compile`,
  `init`, plus a `%:` catch-all. Invokes tools via `.venv/bin/<tool>` and builds
  a real `.venv` target once (`Makefile:13-20`).
- **`Justfile`** (`Justfile:1-43`) — a partial mirror. Recipes: `lifecycle`,
  `sync`, `test`, `test-e2e`, `format`, `lint`, `typecheck`, `check-format`,
  `check-lint`, `check-complexity`, `check-typecheck`, `check`, `compile`.
  Invokes tools via `uv run <tool>` with a `sync` prerequisite on each recipe.

Everything that *calls* a runner calls `make`, never `just`:

- **Python CLI**: `init_new_package` runs `['make', 'init', package_name]` via
  `Popen` in the cloned dir (`main.py:48-54`); output decoded, split on the
  literal `make:` marker, then discarded.
- **CI**: `.gitlab-ci.yml:16-21` runs `make .venv` then `make check`; the GitHub
  workflow `check-modernpackage-on-python314.yml` does the same two steps.
- **Docs**: `README.md:8-21,33`, `docs/overview.md:31-75`,
  `docs/architecture.md:13-18,66,151,290-328`, `docs/specification.md` all
  reference `make` targets and label the Makefile the "canonical command hub".

Makefile targets with **no** Justfile equivalent: `publish`, `fix`, `fixlint`,
`audit`, `deadcode`, `init`, `.venv`, `%:` (research.md Q1, `Makefile:21-44,60-79`).
Naming drift: `mypy`↔`typecheck`, `deadcode`↔`check-complexity (C901)` (these run
*different* tools), and `check` has different composition between the two files.

## Desired End State

A single `Justfile` carries every capability the `Makefile` provided; the
`Makefile` is deleted; every `make` caller (CLI, CI, docs) uses `just`.

**Verification:**
- `Makefile` no longer exists; `grep -rn 'make ' ` over source/CI/docs returns
  only prose/historical-traceback hits (e.g. `README.md:56-75`).
- `just check` runs the full gate (format, lint, complexity, typecheck, test,
  audit, deadcode) and passes via `just check`.
- `just init mypackage` reproduces the Makefile `init` behaviour: renames
  `modernpackage`→`mypackage` across tracked files, resets version to `0.0.1`,
  moves the package dir, re-inits git, commits.
- `init_new_package` invokes `just init <name>`; `just test` passes (the existing
  `test_init_new_package` only asserts `Popen` was called — `test_main.py:42-45`).
- CI green: both pipelines install `just`, then run `just sync` + `just check`.

## Patterns to Follow

- **`uv run <tool>` invocation** (`Justfile:11-35`) — port Makefile's
  `.venv/bin/<tool>` recipes (`Makefile:27-47`) to `uv run`. Do NOT carry over the
  `.venv` real-file target or `.venv/bin/` paths.
- **`sync` prerequisite** (`Justfile:6-8,10-35`) — recipes that need the editable
  install depend on `sync`. New tool recipes (`fixlint`, `audit`, `deadcode`,
  `mypy`-equivalent) follow this; `compile`/`publish`/`init` do not need it.
- **Hyphenated sub-recipe names** (`Justfile:25-32`: `check-format`,
  `check-typecheck`) — name the new fix sub-recipe `fix-lint`, not `fixlint`.
- **Variadic args** (`Justfile:10-14`: `test *args` + `{{args}}`) — `init` takes a
  named parameter instead of Make's `MAKECMDGOALS`/`%:` mechanism
  (`Makefile:2,78-79`).
- **`@`-silenced echo lines** (`Justfile:2-4,7`) — match for quiet recipe bodies.
- **Tool config centralized in `pyproject.toml`** (research.md Cross-Cutting) —
  recipes only invoke tools; add no new config.

**Anti-patterns NOT to follow:** the `%:`/`@:` catch-all (`Makefile:78-79`),
`.PHONY` (`Makefile:1`), `ifndef UV` uv-bootstrap (`Makefile:14-17`), the
`@-exit 0` "up-to-date" workaround and its NOTE (`Makefile:58-60,76`), and the
`.split('make:')` output marker (`main.py:54`) are all Make-specific artifacts
with no place in the Just port.

## Design Decisions

1. **Port `init` as `init package_name="modernpackage":`** — named parameter with
   a default (mirrors Make's `args` default, `Makefile:2`). OS branching
   (Linux/Darwin `sed -i` forms, `Makefile:62-68`) lives inside the recipe shell
   body via `if [ "$(uname)" = ... ]`, since `just` has no `ifeq` directive.
   Reference `{{package_name}}` in the body.
2. **Keep `typecheck`, do not add `mypy`** — Justfile's `typecheck`
   (`Justfile:22-23`) runs the identical `mypy` command; adding a `mypy` alias
   duplicates it. Docs that said `make mypy` map to `just typecheck`.
3. **Add `deadcode` and `audit` as distinct recipes** — `deadcode` runs the
   `deadcode` tool (`Makefile:43-44`), which is NOT the same as the existing
   `check-complexity` ruff-C901 recipe (`Justfile:31-32`). Both kept.
4. **Extend `check` to preserve Makefile's gate coverage** — new `check` =
   `check-format check-lint check-complexity check-typecheck test audit deadcode`.
   Makefile `check` included `audit`+`deadcode` (`Makefile:10`); since CI runs
   `make check`→`just check`, those gates must survive the merge.
5. **Add `fix` + `fix-lint`** — `fix: format fix-lint`; `fix-lint` runs
   `ruff check --fix --unsafe-fixes` and `deadcode --fix` (`Makefile:30-32`).
6. **Add `publish` without a `sync` prereq** — `rm -fr dist/*`, `uv build`,
   `uv publish` (`Makefile:22-25`); build does not need the editable install.
7. **CLI: `['just', 'init', package_name]`; drop the `make:` marker** — replace
   the command (`main.py:49`) and simplify line 54 to `.decode().strip()` since
   the `make:`-marker split is Make-specific and the result is discarded anyway.
   Keep the surrounding `Popen`/`# noqa` structure and the `git clone` call intact.
8. **CI installs `just`** — add a `just` install step before
   `just sync`/`just check` in both `.gitlab-ci.yml` and the GitHub workflow
   (e.g. `uv tool install rust-just` or the official installer); `python:latest`
   does not ship `just`. Replace `make .venv`→`just sync`, `make check`→`just check`.
9. **Delete `Makefile` last** — only after CLI, CI, and docs are switched, so no
   step transiently breaks.
10. **Docs: mechanical `make`→`just` rewrite** — update `README.md`,
    `docs/overview.md`, `docs/architecture.md`, `docs/specification.md`; relabel
    the "canonical command hub" to the Justfile; fix the stale claim that the
    Justfile "only defines a lifecycle target" (`specification.md:145`). Leave the
    historical offline-traceback in `README.md:56-75` as prose (note it now shows
    `just`).

## What We're NOT Doing

- Not changing tool behaviour, flags, or `pyproject.toml` config — recipes stay
  thin wrappers.
- Not adding new recipes beyond porting Makefile capabilities (no speculative
  `test-e2e` Makefile parity — `test-e2e` already exists only in Just).
- Not rewriting `test_init_new_package` to assert the `just` argv — it only
  checks `Popen` was called and stays valid (`test_main.py:42-45`). May update if
  a `make`-specific assertion is found, but none exists.
- Not introducing a uv/just bootstrap inside recipes (Make's `ifndef UV`).
- Not changing the `lifecycle` or `compile` recipes (already mirrored).

## Open Risks

- **CI `just` availability**: `python:latest`/`ubuntu-latest` need `just`
  installed; pick an install method that works on both without network flakiness.
- **`init` shell portability**: the `0.0.1` version-reset `sed -i` line
  (`Makefile:69`) is GNU-only and was never OS-branched in the Makefile; porting
  faithfully carries the same macOS gap. Decision: replicate as-is (faithful port,
  not a fix) unless testing on Darwin is in scope.
- **`init` is hard to test non-destructively** — it `rm -fr .git/` and re-inits;
  no existing test exercises the real recipe. Manual/e2e verification only.
- **Doc reference sprawl** — many `make` mentions across four doc files; risk of
  missing one. Mitigate with a final `grep -rn 'make '` sweep.
- **`just init` arg parsing** — confirm `just init mypackage` passes the name as
  `{{package_name}}` and that the CLI's `cwd`-scoped `Popen` resolves `just`.
