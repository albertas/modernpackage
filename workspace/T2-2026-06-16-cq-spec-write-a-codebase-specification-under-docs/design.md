# Design Discussion

## Current State

`modernpackage` is a small self-replicating CLI that scaffolds new Python
packages by cloning itself and rewriting every `modernpackage` token to a new
name. The shape is fully mapped in `research.md`:

- **CLI**: two console scripts (`modernpackage`, `mp`) both point at
  `modernpackage.main:main` (`pyproject.toml:24-26`). `main()` orchestrates:
  `parse_args()` → version branch or `init_new_package()` (`main.py:54-62`).
  Validation via `check_alpha_numeric()` (`main.py:10-15`).
- **Scaffolding**: `init_new_package()` shells out to `git clone` then
  `make init <name>` (`main.py:37-51`); the `Makefile` `init` target does the
  string rename, version reset, dir rename, and git re-init (`Makefile:60-75`).
- **Build/tooling**: `hatchling` backend, dynamic version from
  `modernpackage/__init__.py:3` (`0.0.9`), strict ruff/mypy, pytest+coverage,
  pip-audit, deadcode — all configured in `pyproject.toml`, all invoked through
  the `Makefile` (`Makefile:10, 27-47`).
- **Tests**: a single `test_show_version()` (`tests/test_main.py:7-14`) covering
  only the `--version` branch.

**There is no `docs/` directory** (`ls` of repo root confirms). The only
prose documentation today is `README.md` (user-facing usage + toolset +
feature-request backlog) and `BACKLOG.md`. There is no single document that
explains how the pieces fit together for a contributor or a later automated
phase. That gap is exactly what this task fills.

## Desired End State

A new Markdown specification file under `docs/` that is an accurate, navigable
reference to the codebase: its goal, architecture, and the key parts (CLI entry
point, scaffolding flow, build/tooling config, test setup, repo structure).

**Verification** (this is documentation, so checks are review-based, not a test
suite):
1. File exists at `docs/specification.md` and renders as valid Markdown.
2. Every factual claim is traceable to a `file:line` reference matching the
   current code (cross-checked against `research.md`).
3. All five task-named parts are covered: CLI entry point, package-init flow,
   build/tooling config, test setup, overall structure.
4. No invented behaviour — known gaps (no error handling, version drift,
   Justfile divergence) are documented as *current state*, not as fixes.
5. `make check` still passes (the doc adds no code, but confirm nothing else
   regressed).

## Patterns to Follow

- **README section style** (`README.md:1-34`): short `##` headed sections,
  terse bullet lists, fenced code for commands. Match this register — the spec
  is a sibling reference, not a rewrite of the README.
- **`file:line` citation discipline** from `research.md` throughout — every
  architectural statement carries a reference so the doc stays auditable and
  re-verifiable by later phases.
- **`pyproject.toml` as the single config hub** narrative
  (`research.md:143-144`): describe tooling by pointing at the one canonical
  source rather than restating each tool's defaults.
- **`Makefile` as the canonical command hub** (`research.md:160-161`): document
  the real entry points (`make check`, `make publish`, `make init`).

**Patterns NOT to follow / call out:**

- Do **not** mirror the README's claim that `just check` / `just test` work —
  the present `Justfile` only defines `lifecycle` (`research.md:110-113`,
  `Justfile:1-4`). Document the divergence explicitly so it is not propagated.
- Do **not** treat `README.md` "Feature requests" (`README.md:36-79`) as
  implemented behaviour; they are a wishlist, including the documented
  no-network crash (`README.md:57-76`).
- Do **not** copy drifting numbers (coverage %, version) without a reference —
  cite `pyproject.toml` / `__init__.py` so the doc ages gracefully.

## Design Decisions

1. **Single file `docs/specification.md`**: One document, as the task says
   ("a single accurate reference"). A multi-file `docs/` tree would be
   speculative over-engineering for a ~2-module package (CLAUDE.md §2).
2. **Filename `specification.md`**: The task literally asks for a "codebase
   specification under `docs/`". Chosen over `architecture.md` / `README.md`
   to match the requested noun and avoid colliding with the root `README.md`.
3. **Audience = contributors + later automated phases**: per `task.md`. This
   pushes toward dense `file:line` anchoring (machine-checkable) over marketing
   prose (which the README already provides).
4. **Document current state, not aspirations**: known gaps (no error handling in
   `init_new_package`, version drift `0.0.9` vs `dist/` `0.0.8`, Justfile vs
   README divergence) are recorded as facts with references, not silently fixed
   or omitted. Scope is *describe*, not *repair*.
5. **Structure mirrors the six research questions**: Goal → Architecture
   overview → CLI → Scaffolding flow → Build/versioning/deps → Tooling → Tests →
   Repo structure → Known gaps. This maps 1:1 onto `research.md` Q1–Q6, so every
   section already has verified source material.
6. **Include one architecture diagram** as an ASCII/Mermaid flow of the
   self-replication path (CLI → `git clone` → `make init` → rename/reset/commit).
   This is the one genuinely non-obvious behaviour (`research.md:155-166`) and a
   diagram earns its place. Keep it small; no other diagrams.
7. **Length ~150–250 lines**: a reference for a tiny codebase. Long enough to
   cover all parts with citations, short enough to stay accurate.

## What We're NOT Doing

- Not modifying any code, config, `Makefile`, `Justfile`, or `pyproject.toml`.
- Not fixing the documented gaps (no-network crash, missing error handling,
  version drift, Justfile/README divergence, `main.py` help typo `main.py:30`).
  These are *reported* in the spec, not resolved.
- Not documenting `vupi` / `lifecycle` internals — external dependency, out of
  this repo's scope (`research.md:169`).
- Not creating a multi-page docs site, nav, or tooling (mkdocs/sphinx).
- Not adding new tests or changing coverage configuration.
- Not updating `README.md` or `BACKLOG.md` to cross-link the new doc (could be a
  follow-up, but is out of this task's stated scope).

## Open Risks

- **Reference drift**: `file:line` numbers reflect the tree at research time. If
  files change between now and implementation, citations must be re-verified
  against the working tree (cheap: the files are small).
- **Version ambiguity**: in-repo evidence disagrees on the published version
  (`__init__.py` 0.0.9 vs `dist/` 0.0.8, `research.md:174-175`). The spec will
  state both with references rather than assert a single "current version".
- **Scope temptation**: the README backlog is rich with near-design ideas; risk
  of the spec drifting into proposing fixes. Mitigated by Decision 4 and the
  "NOT Doing" list — describe only.
- **Filename convention unconfirmed**: no existing `docs/` precedent to match;
  `specification.md` is a judgment call (Decision 2) and is the easiest thing to
  rename if a reviewer prefers another name.
