# Design Discussion

## Current State

Dependency management is split across **two coexisting pin mechanisms** and the
legacy `uv pip` workflow:

- Test/dev tooling lives in the only extra, `[project.optional-dependencies].test`
  (`pyproject.toml:27-37`): `ruff`, `mypy`, `pip-audit`, `deadcode`, `pytest`,
  `pytest-cov`, `pytest-xdist`, `vupi>=0.0.7`. Runtime `dependencies = []`
  (`pyproject.toml:18`). No PEP 735 `[dependency-groups]` exist.
- Three pinned artifacts are regenerated in lockstep by `just compile`
  (`Justfile:75-78`): `requirements.txt` (empty, from runtime deps),
  `requirements-dev.txt` (`uv pip compile --all-extras`, ~198 pinned lines), and
  the native `uv.lock` (`uv lock --upgrade`).
- The shared `sync` prerequisite is two `uv pip` calls
  (`Justfile:9-11`): `uv pip sync requirements-dev.txt` then
  `uv pip install -e .[test]`. Nearly every quality/test recipe depends on `sync`.
- `lifecycle` (`Justfile:1-4`) duplicates those two `uv pip` lines inline.
- `compile` uses `uv pip compile -U` twice plus `uv lock --upgrade`
  (`Justfile:75-78`).
- A private uv index `gitlab` is declared (`pyproject.toml:97-99`); it caps
  resolvable versions and may lag PyPI (`docs/architecture.md:1214-1222`).
- CI (`.gitlab-ci.yml:13-22`, `.github/workflows/check-modernpackage-on-python314.yml:26-34`)
  provisions `uv` + `rust-just`, then calls `just sync` and `just check`. Neither
  runs `just compile`; pins are committed.
- Docs already drift: several places say "uv sync" while the recipe is `uv pip
  sync` + `uv pip install -e .[test]` (`test_e2e.py:13-15`, `docs/invocation.md:388-392`),
  and `docs/specification.md:89` lists a stale `vupi>=0.0.6`.

## Desired End State

The template manages dependencies the recommended native-uv way:

- Test/dev tooling lives in a PEP 735 `[dependency-groups].dev` table; the `test`
  extra is removed. Runtime `dependencies` stays `[]`.
- `uv.lock` is the single source of truth. `requirements.txt` and
  `requirements-dev.txt` are deleted.
- `sync` becomes a single `uv sync` (creates the venv, installs the locked dev
  group, and installs the project editable in one step).
- The pin-refresh recipe becomes `uv lock --upgrade` only.
- `lifecycle` uses `uv sync` instead of the two `uv pip` lines.
- CI is functionally unchanged (still `just sync` / `just check`), now backed by
  native uv.
- Tests and docs reflect `[dependency-groups].dev` and `uv sync`/`uv lock`; the
  stale `vupi` version and "uv sync" wording are corrected to match reality.

**Verification:** `just check` passes locally and in CI; `just test`/`just test-e2e`
green; a fresh `uv sync` from a clean checkout installs the dev toolchain and the
editable project; `uv lock --upgrade` regenerates only `uv.lock`; no
`requirements*.txt` remain and nothing references them.

## Patterns to Follow

- Justfile recipe shape — `recipe: sync` prerequisite then a single `uv run <tool>`
  line (`Justfile:13-41`). Keep this; only the body of `sync` changes.
- Graceful, line-literal pyproject edits in scaffolding (`_apply_license`
  `main.py:482-497`, `_remove_project_scripts` `main.py:531-551`) key off exact
  `[project]` lines and the `[project.scripts]` header — leave these untouched; the
  group move does not affect them.
- CI delegating entirely to the Justfile (`.gitlab-ci.yml:13-22`) — preserve; do
  not inline uv commands into CI.
- Lockstep-regeneration framing in docs (`docs/architecture.md:1217-1222`,
  `docs/overview.md:67`) — rewrite to a single-lockfile story rather than three.

**Do NOT follow:** the dual pin mechanism (`uv pip compile` requirements files
*and* `uv.lock`, `research.md` Cross-Cutting) — it is exactly what this task
collapses. Do not preserve `requirements*.txt` "just in case." Do not copy the
docs' existing "uv sync" wording verbatim before fixing the underlying recipe.

## Design Decisions

1. **Group name `dev`, not `test`** — PEP 735 `[dependency-groups].dev` is the
   uv-default group installed automatically by `uv sync` (no `--group` flag
   needed). Renaming `test`→`dev` keeps `sync` a bare `uv sync`. Members carry
   over verbatim, including `vupi>=0.0.7` and the (still-commented) `deadcode`.
2. **Delete both requirements files** — `requirements.txt` was empty and
   `requirements-dev.txt` is fully superseded by `uv.lock` under native `uv sync`.
   Keeping them would re-introduce the dual mechanism we are removing.
3. **`sync` = single `uv sync`** — replaces `uv pip sync requirements-dev.txt` +
   `uv pip install -e .[test]`. `uv sync` installs locked deps + dev group + the
   project editable, matching prior behavior.
4. **Rename `compile`→`lock`, body `uv lock --upgrade`** — "compile" named the
   `uv pip compile` step that no longer exists. `lock` describes the single
   remaining action. Docs/README references updated accordingly.
5. **CI left structurally as-is** — `just sync`/`just check` already abstract the
   workflow; only their underlying uv calls change, so `.gitlab-ci.yml` and the
   GitHub workflow need no edits beyond confirming they still pass.
6. **Update scaffolding tests, not scaffolding logic** — `main.py` never parses
   `[project.optional-dependencies]`, so the move is transparent to it. But
   `test_strip_scaffolding_removes_project_scripts` asserts the extra survives
   stripping (`test_main.py:1327-1328`); retarget those assertions (and the
   `_seed_clone` fixture pyproject) to `[dependency-groups]` / `dev`.
7. **`audit` recipe unchanged** — `uv run pip-audit --skip-editable`
   (`Justfile:40-41`) works against the env `uv sync` produces (dev group present,
   project editable, hence skippable).
8. **Fix doc drift while here** — correct `vupi>=0.0.6`→`>=0.0.7`
   (`docs/specification.md:89`) and the "uv sync" prose now that it is literally
   true. Scope limited to the dependency-workflow sections the research cites.

## What We're NOT Doing

- Not adding any runtime dependencies — `dependencies` stays `[]`.
- Not changing the private `gitlab` uv index (`pyproject.toml:97-99`).
- Not touching `uv build` / `uv publish` in `publish` (`Justfile:54-57`).
- Not changing scaffolding string-replacement logic in `main.py`.
- Not removing or re-pinning `vupi`, nor un-commenting `deadcode`.
- Not introducing additional groups (e.g. separate `lint`/`type`) — one `dev`
  group mirrors the single existing `test` extra.
- Not rewriting `lifecycle`/`vision` beyond swapping their install step.

## Open Risks

- **e2e cost/network**: e2e `just check` runs a real `uv sync` against the private
  GitLab index (`test_e2e.py:13-15`); offline runners still fail at sync — behavior
  unchanged but worth confirming the message wording stays accurate.
- **`pip-audit --skip-editable`**: must keep finding the dev tools after `uv sync`;
  verify the audit still resolves the same set it did under `uv pip install`.
- **`_seed_clone` fixture coupling**: the test fixture seeds a pyproject snippet;
  if it hardcodes `[project.optional-dependencies]`, both the fixture and its
  assertions need updating together to stay valid TOML (`test_main.py:1329`).
- **uv-version assumption**: `[dependency-groups]` requires a reasonably recent uv;
  CI installs `uv` latest via pip, so fine, but pin awareness is worth a note.
- **Doc breadth**: dependency-workflow text is spread across README and four docs
  files; risk of missing a reference. Grep for `uv pip`, `requirements`, `compile`,
  and `optional-dependencies` after editing to confirm none dangle.
