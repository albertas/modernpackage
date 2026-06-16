# Implementation Plan

## Overview

Create a single new Markdown file, `docs/specification.md` (~150–250 lines), that
is an accurate, navigable, `file:line`-cited reference to the `modernpackage`
codebase: goal, architecture (with one self-replication diagram), CLI entry
point, scaffolding flow, build/tooling config, tests, repo structure, and known
gaps. **No code, config, `Makefile`, `Justfile`, or `pyproject.toml` changes** —
this task only *describes* current state.

### Conventions for every phase

- All work edits/creates the **one** file `docs/specification.md`. Phases append
  sections in order; a failed Phase N still leaves Phases 1..N-1 as a usable spec.
- Match README register (`README.md:1-34`): short `##` sections, terse bullets,
  fenced code for commands.
- Every architectural claim carries a `file:line` citation in backticks, e.g.
  `` `main.py:54-62` ``. Citations below were **re-verified against the working
  tree on 2026-06-16** (see "Verified citation table" at the end of this plan).
- Paths in citations are repo-relative and may be shortened to the filename
  (`main.py`, `Makefile`) as the README does; the full package path is
  `modernpackage/main.py`.
- Document gaps as *current state*, never as proposed fixes (design Decision 4).
- Verification commands assume the working directory is the repo root
  `/home/niekas/tools/modernpackage` (NOT the workspace artifact dir).

---

## Phase 1: File scaffold + Goal + Architecture overview (with diagram)

### Changes

#### 1. Create the spec file with title, Goal, Architecture overview + diagram
**File**: `docs/specification.md`
**Action**: create

Write, in order:

1. H1 title: `# modernpackage — Codebase Specification`
2. A one-line intro sentence (purpose of the doc: contributor + later-automated-phase reference).
3. `## Goal` — 2–4 bullets:
   - Self-replicating CLI scaffolder for new Python packages using a strict,
     modern toolset; cite `README.md:1-34`.
   - Invoked as `modernpackage <name>` / `mp <name>`; `main()` orchestrates a
     version branch or package init; cite `main.py:54-62`.
4. `## Architecture overview`:
   - A short module map paragraph/bullets: `modernpackage/__init__.py` (version
     constant) + `modernpackage/main.py` (CLI logic); `pyproject.toml` = config
     hub; `Makefile` = command hub. Cite `research.md:139-157`, `main.py:37-51`,
     `Makefile:60-75`.
   - One fenced ASCII diagram of the self-replication path. Use exactly this
     content (a fenced ` ``` ` block, no language tag):

```
modernpackage <name>
        │  main()  (main.py:54-62)
        ▼
init_new_package(name)            (main.py:37-51)
        │
        ├─▶ git clone albertas/modernpackage  ./<name>
        │
        └─▶ make init <name>   (cwd=./<name>)  (Makefile:60-75)
                  │
                  ├─ git grep + sed: rename every "modernpackage" → <name>
                  ├─ sed: reset __init__ version → 0.0.1
                  ├─ mv modernpackage/ → <name>/
                  └─ rm .git → git init → git add → git commit
```

### Verification
#### Automated
- [x] `test -f docs/specification.md` exits 0
- [x] `grep -qE '^# modernpackage — Codebase Specification' docs/specification.md`
- [x] `grep -qE '^## Goal$' docs/specification.md && grep -qE '^## Architecture overview$' docs/specification.md`
- [x] `grep -q 'git clone' docs/specification.md` (diagram present)
- [x] Markdown parses: balanced fences via `awk '/^```/{n++} END{exit (n%2)}' docs/specification.md` exits 0.

#### Manual
- [x] Cited orchestration still matches: `sed -n '54,62p' modernpackage/main.py` shows `main()` calling `parse_args()` then the version / `init_new_package` branches.
- [x] Cited init recipe still present: `sed -n '60,75p' Makefile` shows the rename/version-reset/mv/git-reinit steps.

---

## Phase 2: CLI entry point section (Q1)

### Changes

#### 1. Append the CLI section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## CLI entry point` with bullets covering:
- Two console scripts `modernpackage` and `mp`, both → `modernpackage.main:main`;
  cite `pyproject.toml:23-25`.
- `main()` control flow: `parse_args()` → if `version` print `modernpackage
  <__version__>`, elif `package_name` call `init_new_package()`, else no-op;
  cite `main.py:54-62`.
- `parse_args()` uses `argparse`: `-v/--version` (`store_true`, default `False`)
  and optional positional `package_name` (`nargs='?'`, `type=check_alpha_numeric`);
  cite `main.py:18-34`.
- `check_alpha_numeric()` rejects non-alphanumeric names by raising
  `ArgumentTypeError('Non-AlphaNumeric package name')`; cite `main.py:10-15`.
- `__version__` source is `modernpackage/__init__.py` (`0.0.9`); cite
  `__init__.py:3`.
- **Document as current state** (not a fix): the positional help text has a typo
  ("pacakge"); cite `main.py:30`.

### Verification
#### Automated
- [x] `grep -qE '^## CLI entry point$' docs/specification.md`
- [x] `grep -q 'check_alpha_numeric' docs/specification.md`
- [x] `grep -q 'main.py:54-62' docs/specification.md`
- [x] Typo documented: `grep -qi 'pacakge' docs/specification.md` (the doc quotes the typo as-is)

#### Manual
- [x] `sed -n '10,15p' modernpackage/main.py` shows `check_alpha_numeric` raising `ArgumentTypeError`.
- [x] `sed -n '30p' modernpackage/main.py` still contains the string `pacakge` (typo unchanged).

---

## Phase 3: Package-init (scaffolding) flow section (Q2)

### Changes

#### 1. Append the scaffolding-flow section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Package-init flow` with bullets covering:
- `init_new_package(package_name)` runs two `subprocess.Popen` commands:
  1. `git clone https://github.com/albertas/modernpackage <cwd>/<name>` (target
     `Path.cwd() / package_name`);
  2. `make init <name>` with `cwd=<new_package_path>`.
  Output captured via `.communicate()[0]`; the second result is decoded, split on
  `'make:'`, then **discarded** — **no return value, no error handling** (current
  state). `# noqa: S603/S607` suppress subprocess lint. Cite `main.py:37-51`.
- The `Makefile` `init` target transforms the clone (cite `Makefile:60-75`):
  rename every `modernpackage` token via `git grep -l | xargs sed`
  (Linux/Darwin variants), reset version → `0.0.1`, `mv modernpackage <name>`,
  `rm -fr .git/ .venv`, then `git init -b main` + `add` + `commit`.
- `args` default `modernpackage` (cite `Makefile:2`); catch-all `%:` / `@:` rule
  lets the bare package-name token be a make goal without error (cite
  `Makefile:77-78`).

### Verification
#### Automated
- [x] `grep -qE '^## Package-init flow$' docs/specification.md`
- [x] `grep -q 'make init' docs/specification.md`
- [x] `grep -q 'Makefile:60-75' docs/specification.md`
- [x] "no error handling" noted: `grep -qi 'no error handling' docs/specification.md`

#### Manual
- [x] `sed -n '60,75p' Makefile` matches the described rename/reset/reinit recipe.
- [x] `sed -n '77,78p' Makefile` shows the `%:` / `@:` catch-all rule.

---

## Phase 4: Build/versioning/deps + Tooling sections (Q3, Q4)

### Changes

#### 1. Append the build/versioning/dependencies section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Build, versioning & dependencies`:
- Backend `hatchling`; cite `pyproject.toml:42-44` (`[build-system]`). Build
  includes `**/*.py`, excludes `tests/**` (cite `pyproject.toml:46-48`).
- Dynamic version read from `modernpackage/__init__.py` via
  `[tool.hatch.version]`; cite `pyproject.toml:50-51`, value `0.0.9`
  (`__init__.py:3`).
- `requires-python = ">= 3.14"`; runtime `dependencies = []`; optional `test`
  group (hatch, ruff, mypy, pip-audit, deadcode, pytest, pytest-cov,
  vupi>=0.0.6); cite `pyproject.toml:8`, `pyproject.toml:18`,
  `pyproject.toml:27-37`.
- Publishing via `make publish` (clears `dist/*`, `hatch build`, `hatch -v
  publish`); cite `Makefile:22-25`.
- `requirements.txt` (runtime, empty) and `requirements-dev.txt` (full dev pins),
  both generated by `uv pip compile` via `make compile`; cite `Makefile:53-55`.
  Private `gitlab` uv index; cite `pyproject.toml:92-94`.

#### 2. Append the developer-tooling section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Developer tooling`:
- Narrative: **`pyproject.toml` is the single config hub**; **`Makefile` is the
  canonical command hub** (design Patterns). Cite `research.md:159-166`.
- Tools configured in `pyproject.toml`: ruff (`line-length=88`,
  `select=["ALL"]` with ignores, single quotes), mypy (`strict=true`,
  `python_version="3.14"`), deadcode (`ignore_names=["main"]`), pytest/coverage
  (`--cov-fail-under=50.0`), pip-audit. Cite `pyproject.toml:53-90`,
  `pyproject.toml:39-40`.
- `Makefile` command hub: `check: test lint mypy audit deadcode` (cite
  `Makefile:10`), plus `fix`, `lint`, `fixlint`, `format`, `mypy`, `audit`,
  `deadcode`, `test`, all depending on `.venv` (cite `Makefile:27-47`,
  `Makefile:13-20`).
- **Document the divergence** (current state): README/CLAUDE.md reference
  `just check`/`just test`, but the present `Justfile` defines only `lifecycle`;
  cite `Justfile:1-4`, `research.md:110-113`. (Full call-out belongs in Phase 6;
  a one-line pointer here is enough.)

### Verification
#### Automated
- [x] `grep -qE '^## Build, versioning & dependencies$' docs/specification.md`
- [x] `grep -qE '^## Developer tooling$' docs/specification.md`
- [x] `grep -q 'hatchling' docs/specification.md`
- [x] `grep -q 'make check' docs/specification.md`

#### Manual
- [x] `grep -n 'check:' Makefile` confirms `check: test lint mypy audit deadcode` (line 10).
- [x] `grep -n 'build-backend' pyproject.toml` confirms `hatchling.build` (line 44).
- [x] `sed -n '50,51p' pyproject.toml` shows `[tool.hatch.version]` path `modernpackage/__init__.py`.

---

## Phase 5: Test setup + Repo structure sections (Q5, Q6)

### Changes

#### 1. Append the tests section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Tests`:
- Single test `test_show_version()` in `tests/test_main.py`; patches
  `modernpackage.main.ArgumentParser` and `modernpackage.main.print`, forces
  `version = True`, calls `main()`, asserts `print` called once with
  `f'modernpackage {__version__}'`; cite `tests/test_main.py:7-14`.
- Only the `--version` branch is exercised; `check_alpha_numeric`,
  `init_new_package`, the package-name branch, and real arg parsing are
  **untested** (current state). No fixtures / `conftest.py`; per-test
  `unittest.mock.patch`. Coverage gate `--cov-fail-under=50.0`; cite
  `pyproject.toml:39-40`.

#### 2. Append the repository-structure section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Repository structure` — a file/module map (cite `research.md:139-157`):
- Package: `modernpackage/__init__.py`, `modernpackage/main.py` (imports
  `__version__` from `__init__`).
- Tests: `tests/__init__.py`, `tests/test_main.py`.
- Config/build: `pyproject.toml` (single config hub), `Makefile` (command hub),
  `Justfile` (only `lifecycle`).
- Deps: `requirements.txt`, `requirements-dev.txt`, `uv.lock`.
- CI: `.github/workflows/check-modernpackage-on-python311.yml`, `.gitlab-ci.yml`
  (both run `make check`).
- Docs/meta: `README.md`, `BACKLOG.md`, `issues/`, `workspace/`.
- Build output: `dist/` (0.0.8 wheel + sdist).
- One sentence restating the self-referential tie-in: the CLI clones this very
  repo and `make init` rewrites it (cite `research.md:155-157`).

### Verification
#### Automated
- [x] `grep -qE '^## Tests$' docs/specification.md`
- [x] `grep -qE '^## Repository structure$' docs/specification.md`
- [x] `grep -q 'test_show_version' docs/specification.md`

#### Manual
- [x] `sed -n '7,14p' tests/test_main.py` matches the described mock-based test.
- [x] `grep -n 'cov-fail-under' pyproject.toml` confirms `50.0`.

---

## Phase 6: Known gaps & divergences + full verification

### Changes

#### 1. Append the known-gaps section
**File**: `docs/specification.md`
**Action**: modify (append)

Add `## Known gaps & divergences` — each as a *current-state* fact with a
citation (no fixes):
- No error handling / discarded output in `init_new_package`; cite
  `main.py:37-51`, `research.md:171-173`.
- Version drift: `__init__.py` is `0.0.9`, `dist/` holds `0.0.8`; no in-repo
  evidence of which is published. State both, cite `__init__.py:3`,
  `research.md:174-175`.
- Justfile vs README/CLAUDE.md divergence: docs mention `just check`/`just test`
  but `Justfile` only defines `lifecycle`; cite `Justfile:1-4`.
- README "Feature requests" are an aspirational wishlist, **not** implemented —
  including the documented no-network crash traceback; cite `README.md:36-79`,
  `README.md:57-76`.
- Help-text typo "pacakge"; cite `main.py:30`.

### Verification
#### Automated
- [ ] `make check` passes (no code regressed — the doc adds no code)
  <!-- FAIL: pre-existing deadcode crash on Python 3.14 (ast.Str removed); not a regression from doc-only changes -->
- [x] `grep -qE '^## Known gaps & divergences$' docs/specification.md`
- [x] Version drift stated: `grep -q '0.0.9' docs/specification.md && grep -q '0.0.8' docs/specification.md`
- [x] All five task-named parts present:
  ```sh
  for h in 'CLI entry point' 'Package-init flow' 'Build, versioning' 'Developer tooling' 'Tests' 'Repository structure'; do
    grep -q "$h" docs/specification.md || echo "MISSING:$h"
  done
  ```
  prints nothing.
- [x] Length in range: `awk 'END{print (NR>=120 && NR<=270)?"OK":"OUT:"NR}' docs/specification.md` prints `OK`.

#### Manual
- [x] Every `file:line` citation in the doc resolves. Run this audit and confirm it prints no `BAD:` lines:
  ```sh
  grep -oE '[A-Za-z_./]+\.(py|toml|md):[0-9]+(-[0-9]+)?' docs/specification.md | sort -u | while read ref; do
    f="${ref%%:*}"; rng="${ref##*:}"; start="${rng%%-*}"
    case "$f" in main.py|__init__.py) f="modernpackage/$f";; esac
    [ -f "$f" ] && [ "$start" -le "$(wc -l < "$f")" ] || echo "BAD:$ref"
  done
  ```
  (Note: README/research/Makefile/pyproject/tests refs use bare or package paths;
  the `case` maps `main.py`/`__init__.py` to `modernpackage/`. `research.md`
  refs point at the workspace artifact and are expected to be flagged `BAD:` by
  this repo-root audit — visually confirm only those are flagged.)
  <!-- Only research.md:* lines flagged BAD — expected, workspace artifact outside repo root. All other citations pass. -->
- [ ] `git status --porcelain` shows only `docs/specification.md` added (and no
  modified tracked files), confirming the surgical, doc-only scope.
  <!-- NOTE: pre-existing modifications exist on Makefile, modernpackage/__init__.py, main.py, pyproject.toml, requirements-dev.txt; docs/ is new (untracked ??). Phase 6 only added docs/specification.md. -->

---

## Verified citation table (re-checked 2026-06-16 against working tree)

| Claim | Citation | Confirmed |
|---|---|---|
| Two console scripts → `main:main` | `pyproject.toml:23-25` | ✓ |
| `main()` orchestration | `main.py:54-62` | ✓ |
| `parse_args()` argparse | `main.py:18-34` | ✓ |
| `check_alpha_numeric` raises `ArgumentTypeError` | `main.py:10-15` | ✓ |
| Help typo "pacakge" | `main.py:30` | ✓ |
| `__version__ = '0.0.9'` | `__init__.py:3` | ✓ |
| `init_new_package` two Popen, no error handling | `main.py:37-51` | ✓ |
| `Makefile init` rename/reset/reinit | `Makefile:60-75` | ✓ |
| `args` default | `Makefile:2` | ✓ |
| catch-all `%:`/`@:` | `Makefile:77-78` | ✓ |
| `check: test lint mypy audit deadcode` | `Makefile:10` | ✓ |
| tool targets | `Makefile:27-47` | ✓ |
| `make publish` | `Makefile:22-25` | ✓ |
| `make compile` | `Makefile:53-55` | ✓ |
| build-system hatchling | `pyproject.toml:42-44` | ✓ |
| hatch version path | `pyproject.toml:50-51` | ✓ |
| coverage `--cov-fail-under=50.0` | `pyproject.toml:39-40` | ✓ |
| optional test deps | `pyproject.toml:27-37` | ✓ |
| ruff/mypy/deadcode config | `pyproject.toml:53-90` | ✓ |
| gitlab uv index | `pyproject.toml:92-94` | ✓ |
| single test | `tests/test_main.py:7-14` | ✓ |
| Justfile only `lifecycle` | `Justfile:1-4` | ✓ |
| README feature-request wishlist + no-network crash | `README.md:36-79`, `README.md:57-76` | ✓ |

---

## Assumptions resolved (no open questions)

1. **Project check command is `make check`**, not `just check` — the `Justfile`
   only defines `lifecycle` (`Justfile:1-4`). The CLAUDE.md `just`-based
   instructions do not apply to this repo's current state; design §5 and
   `research.md:114-117` (CI) confirm `make check` is the real gate. Phase 6 uses
   `make check`.
2. **Markdown render check** uses `python -c "import markdown..."` with a
   `markdownlint-cli` / balanced-fence fallback, since neither is guaranteed
   installed (Phase 1 verification lists all three).
3. **Filename** is `docs/specification.md` (design Decision 2); `docs/` is created
   implicitly by the create step.
4. **`research.md` citations** inside the spec point at the workspace artifact,
   which lives outside the repo root; the Phase 6 citation audit notes these are
   expected flags and must be confirmed visually rather than auto-passed.
