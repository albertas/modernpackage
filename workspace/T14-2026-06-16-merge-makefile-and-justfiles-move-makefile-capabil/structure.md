# Structure Outline

## Approach

Fold every `Makefile` capability into the `Justfile` as thin `uv run` recipes,
then re-point each `make` caller (CLI, CI, docs) at `just`, and delete the
`Makefile` last so no step transiently breaks. Each phase is a self-contained,
independently verifiable capability rather than a layer; recipes stay thin
wrappers (no new `pyproject.toml` config).

Note: this task has no DB/service/API/UI stack — the "layers" a slice crosses are
**recipe (Justfile) → caller (CLI/CI/docs) → verification**. Slices are ordered so
each later caller-switch lands only after the Justfile capability it needs exists.

---

## Phase 1: Justfile capability parity (tool recipes + extended `check`)

Add the missing tool recipes so `just` covers every Makefile gate, and extend
`check` to preserve the Makefile gate coverage CI depends on.

**Files**: `Justfile`

**Key changes** (each recipe `: sync`-prerequisited except `publish`):
- `audit: sync` → `uv run pip-audit --skip-editable`
- `deadcode: sync` → `uv run deadcode modernpackage tests` (distinct from the
  existing `check-complexity` C901 recipe — both kept)
- `fix-lint: sync` → `uv run ruff check --fix --unsafe-fixes modernpackage tests`
  then `uv run deadcode --fix modernpackage tests` (hyphenated name per design §5)
- `fix: format fix-lint` — aggregate
- `publish:` (no `sync` prereq) → `rm -fr dist/*`; `uv build`; `uv publish`
- `check: check-format check-lint check-complexity check-typecheck test audit deadcode`
  (adds `audit` + `deadcode` to the existing aggregate)
- Do NOT add a `mypy` alias — existing `typecheck` already runs the identical
  `mypy` command (design §2).

**Verify**: `just --summary` lists `audit deadcode fix fix-lint publish`;
`just check` exits 0 and its trace shows pip-audit and deadcode running
(`just check 2>&1 | grep -E 'pip-audit|deadcode'`). `just fix` exits 0.
`just --evaluate` parses without error.

---

## Phase 2: Port `init` recipe into the Justfile

Add the self-replication `init` recipe with a named parameter (replacing Make's
`MAKECMDGOALS`/`%:` mechanism), OS branching inside the shell body.

**Files**: `Justfile`

**Key changes**:
- `init package_name="modernpackage":` — named param with default (design §1)
- Body (single recipe, `{{package_name}}` interpolated):
  - Linux branch: `if [ "$(uname)" = "Linux" ]; then git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'; fi`
  - Darwin branch: same with BSD `sed -i '' -e ...`
  - version reset: `sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py` (faithful GNU-only port — Open Risk noted)
  - `mv modernpackage {{package_name}}`
  - `rm -fr .git/ .venv`; `git init -b main .`; `git add .`;
    `git commit -m "Initial modern {{package_name}} package setup"`
  - final success echo (now says `cd … && just check`)
- No `@-exit 0` / `%:` / `.PHONY` carryover (design anti-patterns).

**Verify** (non-destructive, in a throwaway clone):
```
tmp=$(mktemp -d); git clone . "$tmp/probe"; cd "$tmp/probe"
cp ../../Justfile Justfile   # use the edited Justfile
just init mypackage
```
Check: `test -d mypackage && ! test -d modernpackage`; `grep -rq mypackage pyproject.toml`;
`grep -q '0.0.1' mypackage/__init__.py`; `git -C . log -1 --pretty=%s` contains
`mypackage`. (Run in tmp dir only — recipe is destructive: `rm -fr .git/`.)

---

## Phase 3: Switch the CLI to `just init`

Re-point the Python scaffolder at `just` and drop the Make-specific output marker.

**Files**: `modernpackage/main.py`, (optionally) `tests/test_main.py`

**Key changes**:
- `init_new_package(package_name: str)` — second `Popen` becomes
  `['just', 'init', package_name]` (was `['make', 'init', package_name]`),
  `cwd=new_package_path` unchanged, `# noqa: S603/S607` kept.
- Output line `…communicate()[0].decode().split('make:')[0].strip()` →
  `…communicate()[0].decode().strip()` (marker is Make-specific; result discarded).
- `git clone` `Popen` left intact.
- `tests/test_main.py::test_init_new_package` only asserts `popen_mock.called`
  — stays valid; update only if a `make`-specific assertion surfaces (none found).

**Verify**: `just test` passes (`tests/test_main.py` green). `grep -n 'make' modernpackage/main.py`
returns nothing. `grep -c "'just', 'init'" modernpackage/main.py` returns 1.

---

## Phase 4: Switch CI to `just`

Install `just` in both pipelines and replace the two `make` calls.

**Files**: `.gitlab-ci.yml`, `.github/workflows/check-modernpackage-on-python314.yml`

**Key changes**:
- Add a `just` install step before the build (e.g. `uv tool install rust-just`,
  consistent on `python:latest` and `ubuntu-latest`; avoid network-flaky methods).
- `make .venv` → `just sync`; `make check` → `just check` in both files.

**Verify**: `grep -rn 'make ' .gitlab-ci.yml .github/workflows/` returns no recipe
invocations. Each file contains a `just` install step and `just sync` + `just check`
(`grep -c 'just check' <file>` ≥ 1). YAML parses:
`python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .gitlab-ci.yml .github/workflows/check-modernpackage-on-python314.yml`.

---

## Phase 5: Documentation rewrite (`make` → `just`)

Mechanical rewrite of `make` references across the four doc files; relabel the
"canonical command hub" to the Justfile; fix the stale Justfile claim.

**Files**: `README.md`, `docs/overview.md`, `docs/architecture.md`,
`docs/specification.md`

**Key changes**:
- `make <target>` → `just <recipe>` (`make mypy` → `just typecheck`).
- `docs/architecture.md`: "canonical command hub" label moves to the Justfile.
- `docs/specification.md:145`: remove the stale "Justfile only defines a
  `lifecycle` target" claim.
- `README.md:56-75` offline traceback left as prose (note it now shows `just`).

**Verify**: `grep -rn 'make ' README.md docs/` returns only prose/historical hits
(e.g. the `README.md` traceback), no live `make <target>` command instructions.
`grep -rn 'canonical command hub' docs/architecture.md` resolves to the Justfile.

---

## Phase 6: Delete the `Makefile`

Remove the now-redundant `Makefile` — only after Phases 1-5 land.

**Files**: `Makefile` (deleted)

**Verify**: `test ! -e Makefile`. Full repo sweep
`grep -rn 'make ' . --include='*.py' --include='*.yml' --include='*.md' --include='Justfile'`
returns only prose/historical-traceback hits. `just check` still passes end-to-end.

---

## Testing Checkpoints

- **After Phase 1**: `just check` runs the full gate (format, lint, complexity,
  typecheck, test, audit, deadcode) and passes; `just fix`, `just publish` recipes
  parse. Justfile has capability parity with the Makefile (minus `init`).
- **After Phase 2**: `just init <name>` reproduces Makefile init behaviour in a
  throwaway clone (rename, version reset to `0.0.1`, dir move, git re-init+commit).
- **After Phase 3**: CLI spawns `just init <name>`; `just test` green; no `make`
  left in `modernpackage/main.py`.
- **After Phase 4**: both CI pipelines install `just` and run `just sync` +
  `just check`; YAML valid; no `make` recipe calls in CI.
- **After Phase 5**: no live `make` command instructions in docs; canonical hub =
  Justfile.
- **After Phase 6**: `Makefile` gone; repo-wide `make` sweep clean; `just check`
  still passes. End state from design "Desired End State" fully satisfied.
