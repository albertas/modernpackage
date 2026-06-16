# Structure Outline

## Approach

Write one Markdown file, `docs/specification.md` (~150–250 lines), structured to
mirror research Q1–Q6 (Goal → Architecture → CLI → Scaffolding → Build/Tooling →
Tests → Structure → Known gaps). Every architectural claim carries a `file:line`
citation re-verified against the working tree. No code, config, or `Makefile`
changes. Each phase below appends one cohesive, citation-anchored section to the
same file; phases are independently valuable (if Phase N fails, Phases 1..N-1
still leave a usable, accurate partial spec). "Vertical" here = each phase
delivers a complete reader-facing section spanning narrative + citations +
(where relevant) the diagram, not a half-written stub across all sections.

Verification is review-based (design.md "Verification" §1–5). Each phase is
checked with agent-runnable commands: file/heading presence (`grep`), citation
presence, and spot re-verification that a cited `file:line` still says what the
section claims (`sed -n`). The final phase runs `make check`.

---

## Phase 1: File scaffold + Goal + Architecture overview (with diagram)

Creates `docs/specification.md` with title, a "Goal" section, and an
"Architecture overview" section containing the single ASCII self-replication
diagram (CLI → `git clone` → `make init` → rename/reset/commit). Establishes the
file renders and the one non-obvious behaviour is captured.

**Files**: `docs/specification.md` (new)
**Key changes**:
- New file with `# modernpackage — Codebase Specification` H1.
- `## Goal` — self-replicating scaffolder; cite `README.md:1-34`, `main.py:54-62`.
- `## Architecture overview` — module map + ASCII diagram of the
  self-replication path; cite `research.md:155-166`, `main.py:37-51`,
  `Makefile:60-75`.

**Verify**: `test -f docs/specification.md` exits 0; `grep -qE '^## (Goal|Architecture overview)$' docs/specification.md`; `grep -q 'git clone' docs/specification.md` (diagram present); `python -c "import markdown,pathlib;markdown.markdown(pathlib.Path('docs/specification.md').read_text())"` runs without error (or `npx -y markdownlint-cli docs/specification.md` if no python markdown). Spot-check: `sed -n '54,62p' modernpackage/main.py` shows `main()` orchestration matching the Goal text.

---

## Phase 2: CLI entry point section (Q1)

Documents the two console scripts, `main()` control flow, `parse_args()`,
`-v/--version`, optional `package_name`, and `check_alpha_numeric()` validation.
Notes the `main.py:30` help-text typo as current state (not a fix).

**Files**: `docs/specification.md`
**Key changes**:
- `## CLI entry point` section with bullets citing `pyproject.toml:24-26`,
  `main.py:54-62`, `main.py:18-34`, `main.py:10-15`, `__init__.py:3`,
  `main.py:30` (typo, documented as-is).

**Verify**: `grep -qE '^## CLI entry point$' docs/specification.md`; `grep -q 'check_alpha_numeric' docs/specification.md`; `grep -q 'main.py:54-62' docs/specification.md`. Spot-check citation: `sed -n '10,15p' modernpackage/main.py` shows `check_alpha_numeric` raising `ArgumentTypeError`.

---

## Phase 3: Package-init (scaffolding) flow section (Q2)

Documents `init_new_package()` two-subprocess flow (`git clone` then
`make init`) and the `Makefile init` target's rename/version-reset/dir-move/
git-reinit steps. Records "no return value, no error handling" as current state.

**Files**: `docs/specification.md`
**Key changes**:
- `## Package-init flow` section citing `main.py:37-51`, `Makefile:60-75`,
  `Makefile:2`, `Makefile:77-78`.

**Verify**: `grep -qE '^## Package-init flow$' docs/specification.md`; `grep -q 'make init' docs/specification.md`; `grep -q 'Makefile:60-75' docs/specification.md`. Spot-check: `sed -n '60,75p' Makefile` shows the rename/reset/reinit recipe matching the section.

---

## Phase 4: Build/versioning/deps + Tooling sections (Q3, Q4)

Documents hatchling backend, dynamic version, scripts, deps/optional-deps,
`requires-python >= 3.14`, publishing via `make publish`, requirements files,
and the tool config hub (ruff/mypy/deadcode/pytest/pip-audit) plus `Makefile`
command hub (`check`, `fix`, `lint`, ...). Calls out `pyproject.toml` as single
config hub and `Makefile` as command hub.

**Files**: `docs/specification.md`
**Key changes**:
- `## Build, versioning & dependencies` — cite `pyproject.toml` build-system,
  `[tool.hatch.version]`, `Makefile:22-25`, `requirements*.txt`.
- `## Developer tooling` — cite `pyproject.toml` tool blocks, `Makefile:10,27-47`.

**Verify**: `grep -qE '^## Build, versioning & dependencies$' docs/specification.md`; `grep -qE '^## Developer tooling$' docs/specification.md`; `grep -q 'hatchling' docs/specification.md`; `grep -q 'make check' docs/specification.md`. Spot-check: `grep -n 'check:' Makefile` confirms `check: test lint mypy audit deadcode`.

---

## Phase 5: Test setup + Repo structure sections (Q5, Q6)

Documents the single `test_show_version()` test, its mocking approach, the
50% coverage gate, and that other branches are untested. Then the overall
file/module map and self-referential design tie-in.

**Files**: `docs/specification.md`
**Key changes**:
- `## Tests` — cite `tests/test_main.py:7-14`, `pyproject.toml` coverage opts.
- `## Repository structure` — cite `research.md:139-157`; module/test/config/CI map.

**Verify**: `grep -qE '^## Tests$' docs/specification.md`; `grep -qE '^## Repository structure$' docs/specification.md`; `grep -q 'test_show_version' docs/specification.md`. Spot-check: `sed -n '7,14p' tests/test_main.py` matches the described test.

---

## Phase 6: Known gaps & divergences + full verification

Adds a "Known gaps & divergences" section recording, as current state: no error
handling in `init_new_package`, version drift (`0.0.9` vs `dist/` `0.0.8`),
Justfile-vs-README divergence (`just check`/`just test` not defined), and the
README "Feature requests" wishlist (incl. no-network crash) being aspirational.
Then runs the full design.md verification checklist.

**Files**: `docs/specification.md`
**Key changes**:
- `## Known gaps & divergences` — cite `research.md:168-175`, `Justfile:1-4`,
  `README.md:36-79`, `README.md:57-76`, `main.py:30`.

**Verify**: `grep -qE '^## Known gaps & divergences$' docs/specification.md`; `grep -q '0.0.9' docs/specification.md && grep -q '0.0.8' docs/specification.md`; all five task parts present — `for h in 'CLI entry point' 'Package-init flow' 'Build, versioning' 'Developer tooling' 'Tests' 'Repository structure'; do grep -q "$h" docs/specification.md || echo MISSING:$h; done` prints nothing; line count in range — `awk 'END{print (NR>=120 && NR<=270)?"OK":"OUT:"NR}' docs/specification.md` prints `OK`; finally `make check` passes (no code regressed).

---

## Testing Checkpoints

- **After P1**: `docs/specification.md` exists, renders as Markdown, has Goal +
  Architecture overview with the self-replication diagram.
- **After P2**: CLI section complete with cited `main.py`/`pyproject.toml` refs;
  help typo documented as-is.
- **After P3**: Scaffolding flow documented; "no error handling" noted as fact.
- **After P4**: Build/deps + tooling sections present; `pyproject.toml` (config
  hub) and `Makefile` (command hub) narratives in place; `just` divergence flagged.
- **After P5**: Tests + repository-structure sections present; self-replication
  tie-in stated.
- **After P6**: Known-gaps section present; all five task-named parts covered;
  every claim carries a re-verified `file:line`; length 120–270 lines;
  `make check` passes. Matches design.md Verification §1–5.
