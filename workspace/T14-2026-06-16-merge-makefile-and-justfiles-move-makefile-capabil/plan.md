# Implementation Plan

## Overview

Fold every `Makefile` capability into the `Justfile` as thin `uv run` recipes,
re-point each `make` caller (CLI, CI, docs) at `just`, then delete the
`Makefile` last so no step transiently breaks. End state: a single `Justfile`
command hub; `make` exists only in historical prose.

Phases follow `structure.md` order. Each later caller-switch lands only after
the Justfile capability it needs already exists.

---

## Phase 1: Justfile capability parity (tool recipes + extended `check`)

Add the missing tool recipes so `just` covers every Makefile gate, and extend
`check` to preserve the gate coverage CI depends on.

### Changes

#### 1. Add tool recipes to the Justfile

**File**: `Justfile`
**Action**: modify

Current `Justfile:37` is `check: check-format check-lint check-complexity check-typecheck test`.
Insert the new recipes after the existing tool recipes (the `compile` recipe
stays last). Match existing style: two-space indentation, `@`-silenced echo
lines where appropriate, `sync` prerequisite on every recipe that needs the
editable install. Port commands faithfully from `Makefile:30-44` but invoke via
`uv run` instead of `.venv/bin/<tool>` (design "Patterns to Follow").

Add these recipes (place `audit`/`deadcode`/`fix-lint`/`fix` near the other
tool recipes, and `publish` near `compile`):

```just
audit: sync
  uv run pip-audit --skip-editable

deadcode: sync
  uv run deadcode modernpackage tests

fix-lint: sync
  uv run ruff check --fix --unsafe-fixes modernpackage tests
  uv run deadcode --fix modernpackage tests

fix: format fix-lint

publish:
  rm -fr dist/*
  uv build
  uv publish
```

Notes / resolved decisions:
- `publish` has **no** `sync` prereq (build does not need the editable install —
  design §6; Makefile `publish` depended on `.venv` only for the venv, which
  `uv build` recreates).
- `fix-lint` is hyphenated (design §5, "Hyphenated sub-recipe names"), not
  `fixlint`.
- `fix-lint` runs `ruff check --fix --unsafe-fixes` then `deadcode --fix`
  (faithful port of `Makefile:31-32`; flag order normalized to match the
  Justfile's existing `modernpackage tests` trailing-args style).
- Do **NOT** add a `mypy` alias — `typecheck` (`Justfile:22-23`) already runs the
  identical `mypy modernpackage tests` command (design §2).
- `deadcode` is a distinct recipe from `check-complexity` (ruff `--select C901`).
  Both are kept (design §3).

#### 2. Extend the `check` aggregate

**File**: `Justfile`
**Action**: modify

```just
check: check-format check-lint check-complexity check-typecheck test audit deadcode
```

Adds `audit` + `deadcode` to the existing aggregate so `just check` matches the
Makefile gate set (`Makefile:10` ran `test lint mypy audit deadcode`); since CI
switches `make check`→`just check` in Phase 4, those gates must survive
(design §4).

### Verification

#### Automated
- [x] `just --evaluate` parses the Justfile without error
- [x] `just --summary` output contains `audit`, `deadcode`, `fix`, `fix-lint`, `publish`
      (`just --summary | tr ' ' '\n' | grep -Eqx 'audit|deadcode|fix|fix-lint|publish'` per name)
- [ ] `just check` exits 0
      NOTE: Pre-existing deviation — `deadcode` 2.4.1 (latest) crashes on Python 3.14 with
      `AttributeError: module 'ast' has no attribute 'Str'` (removed in 3.12). The Makefile's
      `make check` also includes `deadcode` and would fail identically. This is a tool
      compatibility bug predating Phase 1, not introduced by this change.
- [ ] `just fix` exits 0
      NOTE: Same pre-existing deviation as above — `fix-lint` calls `deadcode --fix` which also crashes.

#### Manual
- [x] `just --show check` output ends with `... test audit deadcode`
      (`just --show check | grep -q 'test audit deadcode'`)
- [x] `just check 2>&1 | grep -Eq 'pip-audit|pip_audit'` (pip-audit ran in the gate)
- [x] `just check 2>&1 | grep -q 'deadcode'` (deadcode ran in the gate)
- [x] `just --show fix-lint | grep -q 'unsafe-fixes'` and `just --show publish | grep -q 'uv publish'`

---

## Phase 2: Port `init` recipe into the Justfile

Add the self-replication `init` recipe with a named parameter (replacing Make's
`MAKECMDGOALS`/`%:` mechanism), with OS branching inside the shell body.

### Changes

#### 1. Add the `init` recipe

**File**: `Justfile`
**Action**: modify

Add after the tool recipes (before or after `compile` — order is cosmetic).
Port `Makefile:60-76` faithfully. `just` has no `ifeq`; OS branching lives in
the shell body via `if [ "$(uname)" = ... ]`. The package name is a named
parameter with default `modernpackage` (design §1), interpolated as
`{{package_name}}`.

```just
init package_name="modernpackage":
  @echo "Initializing {{package_name}}..."
  @if [ "$(uname)" = "Linux" ]; then \
    git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'; \
  fi
  @if [ "$(uname)" = "Darwin" ]; then \
    git grep -l 'modernpackage' | xargs sed -i '' -e 's/modernpackage/{{package_name}}/g'; \
  fi
  @sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py
  @mv modernpackage {{package_name}}
  @rm -fr .git/ .venv
  @git init -b main .
  @git add .
  @git commit -m "Initial modern {{package_name}} package setup"
  @echo "Finished initializing {{package_name}}. You can now run: \033[0;32m cd {{package_name}} && just check\033[0m"
```

Resolved decisions / faithful-port notes:
- Final echo now says `cd … && just check` (was `make check`) — the only
  intentional content change in the port.
- The `0.0.1` version-reset line (`Makefile:69`) uses GNU `sed -i` form and was
  never OS-branched in the Makefile. Replicate as-is (faithful port, not a fix —
  design "Open Risks": macOS gap carried over knowingly).
- Do **NOT** carry over Make artifacts: `@-exit 0` (`Makefile:76`), the `%:`/`@:`
  catch-all (`Makefile:78-79`), `.PHONY`, the `## NOTE` comment, or
  `MAKEFLAGS += --quiet` (design "Anti-patterns NOT to follow").
- No `sync` prereq — `init` rewrites and re-inits the tree; it must not trigger a
  dependency install (mirrors Makefile `init`, which had no `.venv` dep).
- Each recipe line runs in its own shell under `just`'s default shell behavior;
  the `if ...; then ...; fi` blocks are single logical lines (continued with
  `\`), matching how the Makefile already wrote them.

### Verification

#### Automated
- [x] `just --evaluate` parses without error
- [x] `just --show init | grep -q 'package_name="modernpackage"'` (named param + default present)
- [x] `just --show init | grep -q 'just check'` (success echo updated)
- [x] `just --show init` contains no `exit 0`, no `%:`, no `MAKEFLAGS`

#### Manual (destructive — run only in a throwaway clone)

The recipe runs `rm -fr .git/` and re-inits, so never run it in the working
tree. Exercise it in a temporary clone:

```bash
tmp=$(mktemp -d)
git clone . "$tmp/probe"
cp Justfile "$tmp/probe/Justfile"   # use the edited Justfile
cd "$tmp/probe"
just init mypackage
```

- [x] `test -d "$tmp/probe/mypackage" && ! test -d "$tmp/probe/modernpackage"` (dir renamed/moved)
- [x] `grep -rq mypackage "$tmp/probe/pyproject.toml"` (occurrences rewritten)
- [x] `grep -q '0.0.1' "$tmp/probe/mypackage/__init__.py"` (version reset)
- [x] `git -C "$tmp/probe" log -1 --pretty=%s | grep -q mypackage` (re-init commit subject)
- [x] cleanup: `rm -rf "$tmp"`

---

## Phase 3: Switch the CLI to `just init`

Re-point the Python scaffolder at `just` and drop the Make-specific output marker.

### Changes

#### 1. Replace the `make` subprocess call

**File**: `modernpackage/main.py`
**Action**: modify

Change the second `Popen` command from `make` to `just`, and simplify the output
line (the `make:` split marker is Make-specific and the result is discarded
anyway — design §7). Keep the `git clone` `Popen` and all `# noqa: S603/S607`
comments intact.

`main.py:48-54` becomes:

```python
    pipe = Popen(  # noqa: S603
        ['just', 'init', package_name],  # noqa: S607
        stdin=PIPE,
        stdout=PIPE,
        cwd=new_package_path,
    )
    pipe.communicate()[0].decode().strip()
```

Also update the docstring on `init_new_package` (`main.py:38`) which currently
says "run `make init` in it" → "run `just init` in it" (one-word change, traces
directly to the command switch).

### Changes — tests

#### 2. No test change required

**File**: `tests/test_main.py`
**Action**: none

`test_init_new_package` (`tests/test_main.py:41-44`) only asserts
`popen_mock.called` — it does not assert the argv, so it stays valid. No
`make`-specific assertion exists anywhere in the test (design "What We're NOT
Doing"). Leave the file unchanged.

### Verification

#### Automated
- [x] `just test` passes (all of `tests/test_main.py` green)

#### Manual
- [x] `grep -n 'make' modernpackage/main.py` returns nothing
- [x] `grep -c "'just', 'init'" modernpackage/main.py` returns `1`
- [x] `grep -q "split('make:')" modernpackage/main.py` returns non-zero (marker removed)

---

## Phase 4: Switch CI to `just`

Install `just` in both pipelines and replace the two `make` calls.

### Changes

#### 1. GitLab CI

**File**: `.gitlab-ci.yml`
**Action**: modify

Install `just` in `before_script` (the image is `python:latest`, which has `uv`
available via the cache flow but not `just` — design §8). Use
`uv tool install rust-just` for a consistent, non-network-flaky install on both
pipelines, then expose it on `PATH` (uv installs tools to `~/.local/bin`).
Replace `make .venv`→`just sync` and `make check`→`just check`.

```yaml
before_script:
  - uv tool install rust-just
  - export PATH="$HOME/.local/bin:$PATH"
  - just sync

test:
  script:
    - export PATH="$HOME/.local/bin:$PATH"
    - just check
```

Resolved assumption: `uv` is present on `python:latest`? It is not guaranteed by
the base image, but the existing pipeline already relied on `make .venv`'s
`ifndef UV` bootstrap (`pip install uv`). To keep `uv tool install` working,
prepend `pip install uv` before `uv tool install rust-just` in `before_script`:

```yaml
before_script:
  - pip install uv
  - uv tool install rust-just
  - export PATH="$HOME/.local/bin:$PATH"
  - just sync
```

#### 2. GitHub Actions workflow

**File**: `.github/workflows/check-modernpackage-on-python314.yml`
**Action**: modify

Replace the "Install dependencies" and "Run checks" steps. `ubuntu-latest` does
not ship `just`; install it the same way (via `uv`, for parity with GitLab and
to avoid network-flaky external installers — design §8 / "Open Risks").

```yaml
    - name: Install dependencies
      run: |
        pip install uv
        uv tool install rust-just
        echo "$HOME/.local/bin" >> "$GITHUB_PATH"
        just sync
    - name: Run checks
      run: |
        just check
```

(`$GITHUB_PATH` persists `PATH` across subsequent steps, so the "Run checks"
step finds `just`.)

### Verification

#### Automated
- [x] Both files parse as YAML:
      `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .gitlab-ci.yml .github/workflows/check-modernpackage-on-python314.yml`

#### Manual
- [x] `grep -rnE '\bmake (\.venv|check|init|publish)\b' .gitlab-ci.yml .github/workflows/` returns nothing (no `make` recipe invocations)
- [x] `grep -c 'just check' .gitlab-ci.yml` ≥ 1 and `grep -c 'just check' .github/workflows/check-modernpackage-on-python314.yml` ≥ 1
- [x] `grep -q 'just sync' .gitlab-ci.yml` and `grep -q 'just sync' .github/workflows/check-modernpackage-on-python314.yml`
- [x] Each file contains a `just` install step:
      `grep -q 'rust-just' .gitlab-ci.yml` and `grep -q 'rust-just' .github/workflows/check-modernpackage-on-python314.yml`

---

## Phase 5: Documentation rewrite (`make` → `just`)

Mechanical rewrite of `make` references across the four doc files; relabel the
"canonical command hub" to the Justfile; fix the stale Justfile claim.

### Changes

#### 1. README.md

**File**: `README.md`
**Action**: modify

- `README.md:8-9`: `make check`→`just check`, `make publish`→`just publish`.
- `README.md:17-21` (Development): `make check`→`just check`, `make fix`→`just fix`,
  `make publish`→`just publish`, `make compile`→`just compile`, `make sync`→`just sync`.
- `README.md:33`: replace the toolset line
  `- Makefile - aliases for commonly used command line commands.` →
  `- Justfile - aliases for commonly used command line commands.`
- `README.md:38`: feature-request "remove init Makefile alias and cli.py command
  python files." — leave as-is (historical backlog prose; not a live command).
- `README.md:48`: feature-request "make compile and make sync does not work when
  virtual environment is activated" — leave as-is (historical prose).
- `README.md:56-75`: the offline-traceback block — leave as prose (it shows the
  old `make init` Popen failure; it is historical, design §10 / structure Phase 5).

#### 2. docs/overview.md

**File**: `docs/overview.md`
**Action**: modify

- Line 12: dev-workflow tooling sentence mentions `Makefile` and `Justfile` — keep
  `Justfile`, drop the `Makefile` reference (it no longer exists). Reword to
  "Development workflow via `Justfile` for common tasks: ...".
- Lines 31-40: the `make check/fix/compile/test/test-e2e/lint/format/mypy/audit/deadcode/publish`
  bullet list → rewrite each to its `just` recipe. Map `make mypy`→`just typecheck`
  (design §2). `make audit`/`make deadcode`→`just audit`/`just deadcode`.
- Lines 42-53: the "Alternatively, use equivalent `just` targets" block is now
  redundant (there is no longer a Makefile to be an alternative to). Collapse:
  remove the "Alternatively" framing; keep the accurate `just` recipe
  descriptions. Update line 44 `just check` description to
  `check-format check-lint check-complexity check-typecheck test audit deadcode`
  (the new aggregate from Phase 1). Update line 53
  "Both `Makefile` and `Justfile` targets depend on synced dependencies" →
  "`Justfile` recipes depend on synced dependencies (dev and test extras)."
- Line 57: "orchestrates `git clone` + `make init`" → "+ `just init`".
- Line 58: "the `Makefile init` target uses `git grep + sed`" →
  "the `just init` recipe uses `git grep + sed`".
- Line 59: "the Makefile and Justfile delegate to them via `uv run`" →
  "the Justfile delegates to them via `uv run`".
- Line 60: "`make compile` and `just compile` regenerate ... in lockstep" →
  "`just compile` regenerates ... in lockstep" (drop the make half).
- Line 75: "ensure `just check` (or `make check`) passes" →
  "ensure `just check` passes".

#### 3. docs/architecture.md

**File**: `docs/architecture.md`
**Action**: modify

- Lines 18-19: the structure block —
  `├── Makefile             # canonical command hub` and
  `└── Justfile             # just-based command shortcuts`. Remove the `Makefile`
  line; relabel the `Justfile` line as the canonical hub:
  `└── Justfile             # canonical command hub` (design §10 / structure Phase 5).
- Line 66: "Spawns `make init <package_name>`" → "Spawns `just init <package_name>`".
- Line 70: "The `Makefile init` target ... performs the actual transformation:" →
  "The `just init` recipe ... performs the actual transformation:".
- Line 151: "`make publish` clears `dist/` ..." → "`just publish` clears `dist/` ...".
- Line 160: "Both `Makefile` and `Justfile` define a `compile` recipe ..." →
  "The `Justfile` defines a `compile` recipe ...".
- Lines 204-224: the "#### Makefile (canonical)" / "#### Justfile" subsections —
  remove the Makefile subsection; keep the Justfile subsection and relabel it as
  canonical. Update the Justfile recipe list to include the recipes added in
  Phase 1 (`audit`, `deadcode`, `fix`, `fix-lint`, `publish`) so the reference is
  accurate.
- Line 234: "The Makefile and Justfile delegate to them via `uv run`" →
  "The Justfile delegates to them via `uv run`".
- Lines 290-292: example block `make test` / `make test-e2e` / `make check` →
  `just test` / `just test-e2e` / `just check`.
- Line 304: "The Makefile `init` target (in the clone) transforms it" →
  "The `just init` recipe (in the clone) transforms it".
- Line 316: "Both `git clone` and `make init` subprocess calls ... missing `make`
  command" → "Both `git clone` and `just init` subprocess calls ... missing `just`
  command".
- Lines 324-329: the "### Justfile and Makefile alignment" subsection — the
  Makefile no longer exists, so the "alignment" framing is obsolete. Retitle to
  "### Justfile command surface" and rewrite lines 326-329 to describe `just`
  recipes only; drop line 329's "Future work: ... merge the Makefile into the
  Justfile" (now done).

#### 4. docs/specification.md

**File**: `docs/specification.md`
**Action**: modify

- Line 17: "**`Makefile`**: canonical command hub — all development and
  publishing commands route through it (`Makefile:1-78`)." → relabel to the
  Justfile as canonical command hub.
- Line 29: diagram `└─▶ make init <name>   (cwd=./<name>)  (Makefile:60-75)` →
  `└─▶ just init <name>   (cwd=./<name>)`.
- Line 56: "Spawns second `subprocess.Popen`: `make init <name>`" → "`just init <name>`".
- Line 60: "**`Makefile init` target** (`Makefile:60-75`) transforms ..." →
  "**`just init` recipe** transforms ...".
- Lines 65-67: "**Make argument handling** (`Makefile:2`, `Makefile:77-78`)" and
  the `%:`/`@:` catch-all note — replace with a short note that `just init`
  receives the name via the named `package_name` parameter (no catch-all needed).
- Line 77: "**Publishing** (`Makefile:22-25`): `make publish` clears `dist/*` ..." →
  "**Publishing**: `just publish` clears `dist/*` ...".
- Line 78: "**Dependency pinning** (`Makefile:53-55`): `make compile` ..." →
  "`just compile` ...".
- Line 83: "**Narrative**: ... `Makefile` is the canonical command hub
  (`pyproject.toml:1-94`, `Makefile:1-78`). All development commands are invoked
  through the Makefile, which manages virtual environment setup (`.venv` target) ..."
  → rewrite: the `Justfile` is the canonical command hub; recipes delegate to
  tools via `uv run` with a `sync` prerequisite (no `.venv` target).
- Line 90: "simply invoked via `make audit`" → "`just audit`".
- Lines 91-96: "**Makefile command hub** (`Makefile:1-50`)" subsection — retitle
  to "**Justfile command hub**" and rewrite the recipe references:
  `check` now = `check-format check-lint check-complexity check-typecheck test audit deadcode`;
  `fix` = `format fix-lint`; mention `publish`, `compile`, `sync` as `just` recipes.
- Lines 121-122: repository-structure block —
  `Makefile` — command hub ... and `Justfile` — currently defines only
  `lifecycle` target. Remove the `Makefile` line; **fix the stale claim**: the
  `Justfile` is the command hub (it defines the full recipe set), not "only a
  `lifecycle` target" (research Open Areas; design §10).
- Line 130: "Both run `make check` as the primary gate." → "Both run `just check`
  as the primary gate."
- Line 139: "then `make init` rewrites the clone ... (`main.py:37-51`,
  `Makefile:60-75`)" → "then `just init` rewrites the clone ... (`main.py:37-51`)".
- Line 143: "If `git clone` or `make init` fail ..." → "If `git clone` or
  `just init` fail ...".
- Line 145: "**Justfile vs. BACKLOG divergence** ... the present `Justfile` only
  defines a `lifecycle` target — so those `just` commands do not work. README
  correctly documents `make check` / `make fix` ..." — **remove this stale gap
  entirely** (the Justfile now defines the full recipe set and is the documented
  hub; the divergence no longer exists — design §10, research Open Areas).

### Verification

#### Automated
- [ ] `just check` still passes (docs changes are inert; this confirms nothing
      else regressed)
      NOTE: Pre-existing deviation — `deadcode` 2.4.1 (latest) crashes on Python 3.14 with
      `AttributeError: module 'ast' has no attribute 'Str'`. This is the same pre-existing
      tool compatibility bug documented in Phase 1; not introduced by Phase 5 docs changes.

#### Manual
- [x] `grep -rnE '\b(make) (check|fix|publish|compile|sync|init|test|test-e2e|lint|format|mypy|audit|deadcode|\.venv)\b' README.md docs/`
      returns only the historical traceback in `README.md:56-75` and the two
      backlog-prose lines (`README.md:38,48`) — no live `make <target>` command
      instructions.
      NOTE: grep also matches README.md:42 (`make check` / `make publish` inside a
      feature-request bullet) — this is also historical backlog prose and is left as-is
      per the plan's guidance for feature-request sections.
- [x] `grep -rn 'canonical command hub' docs/architecture.md docs/specification.md`
      every hit refers to the `Justfile` (not the `Makefile`)
- [x] `grep -rqn "only defines a .lifecycle. target" docs/` returns nothing (stale
      claim removed)
- [x] `grep -q 'Justfile' README.md` (toolset line updated) and
      `grep -q 'Makefile - aliases' README.md` returns nothing

---

## Phase 6: Delete the `Makefile`

Remove the now-redundant `Makefile` — only after Phases 1-5 land.

### Changes

#### 1. Delete the Makefile

**File**: `Makefile`
**Action**: delete

```bash
git rm Makefile
```

### Verification

#### Automated
- [ ] `just check` still passes end-to-end (full gate: format, lint, complexity,
      typecheck, test, audit, deadcode)
      NOTE: Pre-existing deviation — `deadcode` 2.4.1 crashes on Python 3.14 with
      `AttributeError: module 'ast' has no attribute 'Str'`. All other gates
      (format, lint, complexity, typecheck, test, pip-audit) pass. Same pre-existing
      tool compatibility bug documented in Phases 1 and 5.
- [x] `just test` passes

#### Manual
- [x] `test ! -e Makefile`
- [x] Repo-wide `make` sweep is clean of live recipe invocations:
      `grep -rnE '\bmake (check|fix|publish|compile|sync|init|test|test-e2e|lint|format|mypy|audit|deadcode|\.venv)\b' . --include='*.py' --include='*.yml' --include='*.yaml' --include='*.md' --include='Justfile'`
      returns only the historical traceback / backlog prose in `README.md`.
- [x] `grep -rn 'Makefile' . --include='*.py' --include='*.yml' --include='*.yaml' --include='*.md'`
      returns only intentional historical/prose references (none labeling it the
      command hub).

---

## Testing Checkpoints

- **After Phase 1**: `just check` runs the full gate (format, lint, complexity,
  typecheck, test, audit, deadcode) and passes; `just fix`, `just publish` parse.
  Justfile has capability parity with the Makefile (minus `init`).
- **After Phase 2**: `just init <name>` reproduces Makefile init behaviour in a
  throwaway clone (rename, version reset to `0.0.1`, dir move, git re-init+commit).
- **After Phase 3**: CLI spawns `just init <name>`; `just test` green; no `make`
  left in `modernpackage/main.py`.
- **After Phase 4**: both CI pipelines install `just` and run `just sync` +
  `just check`; YAML valid; no `make` recipe calls in CI.
- **After Phase 5**: no live `make` command instructions in docs; canonical hub =
  Justfile; stale "Justfile only defines lifecycle" claim removed.
- **After Phase 6**: `Makefile` gone; repo-wide `make` sweep clean; `just check`
  still passes. End state from design "Desired End State" fully satisfied.
