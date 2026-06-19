# Design Discussion

This task produces a **documentation artifact** (a new reference file under `docs/`), not
code. "Implementation" means authoring one Markdown file that captures current
containerization best practices, Podman-primary and Docker-compatible, for a `uv` +
`Justfile` Python project. Success is a doc that is accurate, current, and indistinguishable
in style from the existing `docs/` set.

## Current State

- **No container artifacts exist in-repo**: a `Glob` for `Containerfile`/`Dockerfile`/`compose*`
  returned nothing (`research.md:3`). There is no in-repo containerization pattern to mirror;
  Q4–Q7 are answered entirely from external best-practice sources (`research.md:106`).
- **Doc set** (`docs/`): `overview.md` (index), `specification.md`, `architecture.md`,
  `invocation.md`, `data_flows.md`, `backlog_formats.md`, `vision.md`, `persona.md`
  (`research.md:10`).
- **Tooling is uv + just centric end-to-end**: `pyproject.toml` is the single config hub;
  `Justfile` delegates every task to `uv run`; both CI systems do
  `pip install uv → uv tool install rust-just → just sync → just check`
  (`research.md:101`, `research.md:30`, `research.md:45-47`).
- **Repo-specific constraints**: `requires-python >= 3.14` (`pyproject.toml:8`) and a GitLab
  private uv index named `gitlab` (`pyproject.toml:97-99`); external sources use 3.12/3.13 and
  public PyPI, so version/index specifics are not externally prescribed (`research.md:107`).
- The package is a **CLI scaffolder** (`overview.md:7`); long-running-service practices
  (healthchecks, app+DB compose) are externally documented but not obviously applicable to this
  codebase's own runtime (`research.md:108`).

## Desired End State

A new file `docs/containerization.md` exists that:

1. Documents image authoring, builds, running, security, and Podman/Docker compatibility for a
   modern `uv`-managed Python project, grounded in the external findings of `research.md` Q4–Q7.
2. Frames guidance as **forward-looking reference** for the scaffolder's future backend/FastAPI
   feature (per `task.md`), explicitly noting no containerization exists in-repo today.
3. Matches existing `docs/` conventions exactly (see Patterns to Follow).
4. Is registered in the `overview.md:21-28` documentation index table.

**Verification** (no automated test harness for docs):
- `docs/containerization.md` opens with `# modernpackage — <Subtitle>` and a line-3
  `[overview.md](overview.md)` back-link.
- `overview.md` index table has a new row linking to it.
- All external claims trace to a source URL already cited in `research.md` (no new
  un-researched claims).
- `just check` still passes (the doc adds no Python; this guards against accidental edits).

## Patterns to Follow

All references are from `research.md`, which carries the underlying `file:line` citations.

- **H1 + subtitle**: `# modernpackage — <Subtitle>`, Title Case, em-dash subtitle
  (`research.md:11`).
- **Back-link nav**: standalone `[overview.md](overview.md)` on line 3 (`research.md:13`).
- **Intro paragraph**: 1–2 sentences before the first H2 (`research.md:12`).
- **Headings**: H2/H3 Title Case; H4 only if documenting per-item entries (`research.md:14`).
- **Code blocks**: language-hinted fences — `bash` for CLI, `ini`/`toml`-style for
  `pyproject.toml` excerpts; bare ``` for terminal output and diagrams; annotate expected
  output inline with `#` comments inside `bash` blocks (`research.md:15`).
- **Inline code**: backticks for identifiers, flags, paths, env vars, filenames
  (`research.md:16`).
- **Tables**: 2-col `Term | Purpose` style with `**bold term**: description` lead-ins
  (`research.md:17`).
- **Cross-references**: relative links; `§` anchor notation for intra-doc sections
  (`research.md:18`).
- **Callouts**: bold-prefixed standalone paragraphs `**Note**:` / `**Important**:` — **NOT**
  GitHub `> [!NOTE]` admonitions and **no** YAML front-matter (`research.md:23`).
- **Index registration**: add a row to the `overview.md:21-28` table with the
  `**Bold lead-in**: description.` cell style (`research.md:102`).

**Patterns to NOT follow**: do not adopt the rigid per-function H4 template from
`architecture.md` (`research.md:21`) — this is a conceptual reference, not an API reference, so
the flat `##`-sections-plus-bullets style of `specification.md` (`research.md:20`) is the right
model. Do not invent admonition syntax or front-matter the rest of the docs lack.

## Design Decisions

1. **Filename `docs/containerization.md`**: matches the existing flat, lowercase,
   single-word/underscore naming (`overview.md`, `data_flows.md`) — `research.md:10`. No
   subdirectory; the doc set is flat.
2. **Conceptual reference, not a Containerfile to commit**: the task says "write a reference
   document," and no container runtime exists in-repo (`research.md:3`). The doc presents
   **annotated example** Containerfile/compose snippets as illustrative guidance, clearly
   marked as templates for the future backend feature — it does NOT add a real
   `Containerfile`/`compose.yml` to the repo root.
3. **Podman-primary, Docker-compatible framing throughout**: per `task.md`. Lead with Podman
   commands/conventions; call out the compatibility rules (name file `Containerfile`, OCI
   format, vendor-neutral Compose spec, `x-podman.*` for Podman-only knobs) as a recurring
   theme (`research.md:103`).
4. **Accommodate repo constraints in examples**: examples use a Python **3.14** base image and
   note the GitLab private uv index (`pyproject.toml:8,97-99`; `research.md:61,107`), rather
   than copying the 3.12/3.13 + public-PyPI examples verbatim from sources.
5. **Cover both CLI-style and service-style images**: the package is a CLI today
   (`overview.md:7`) but the doc explicitly guides a future FastAPI backend (`task.md`).
   Include both PATH-activated CLI/distroless guidance and service guidance (healthchecks,
   app+DB compose), labeling the latter as "for the upcoming service backend."
6. **Mirror the uv+just workflow**: container recipes are presented as `just`-invokable and
   `uv`-driven to match the project's existing surface (`research.md:101`); suggest (not
   mandate) future `Justfile` recipes like `container-build`/`container-run`.
7. **Section structure follows the research's Q4–Q7 split**: Image Authoring → Podman Usage &
   Docker Compatibility → Security & Runtime → Local Multi-Service Stacks. This keeps the doc
   traceable back to researched sources.
8. **~250–350 line target for the doc itself** (the doc, not this design): long enough to be a
   useful reference, consistent with mid-size docs like `invocation.md` (606 lines is the
   upper bound; `data_flows.md` is shorter). Err toward completeness over brevity since it is
   reference material.
9. **Every external claim must cite a source URL** already present in `research.md` (e.g.
   Astral uv Docker guide, Red Hat rootless/compose blogs, OWASP, Compose Spec) — no new
   un-vetted claims introduced at design→doc time (`research.md:54,68,72,81,93`).

## What We're NOT Doing

- **Not** adding a real `Containerfile`, `Dockerfile`, `compose.yml`, `.dockerignore`, or
  `Justfile` container recipes to the repo. This task is documentation only; those land with
  the future backend feature.
- **Not** implementing the FastAPI backend or any runtime service — the doc only *prepares* for
  it.
- **Not** restructuring existing docs, the `overview.md` intro, or the `Justfile` beyond adding
  the single index-table row.
- **Not** prescribing CI/CD container-build pipeline changes (`.gitlab-ci.yml` /
  `.github/workflows/`); the doc may *mention* registry-push as future work but adds no
  pipeline.
- **Not** writing Kubernetes/quadlet production-deployment runbooks beyond a brief
  pointer; scope is authoring/build/run/local-dev compatibility per `task.md`.

## Open Risks

- **Currency of external guidance**: tool versions and defaults move fast (uv image tags,
  Podman 5.x pasta default, Compose `version:` deprecation). The doc should pin/version-note
  where the source did and avoid hard-coding a uv version that will drift (`research.md:54,69,93`).
- **3.14 base-image availability**: external uv examples assume 3.12/3.13 base tags; a
  `python:3.14-slim` / Astral `uv:python3.14-*` tag must be confirmed to exist before the doc
  asserts it as a concrete example (`research.md:61,107`). If unavailable, the doc should show
  the pattern with a placeholder tag and note the constraint.
- **GitLab private index in builds**: documenting `uv sync` against the `gitlab` index inside a
  build requires credential/secret handling (`research.md:83`); the doc must show the
  build-secret pattern rather than baking tokens into layers.
- **Scope drift toward a full tutorial**: the temptation is to write a step-by-step backend
  containerization tutorial. Keep it a *reference* of patterns and decisions, deferring concrete
  artifacts to the backend feature (guarded by "What We're NOT Doing").
- **Applicability mismatch**: service-oriented practices may read as premature for a CLI repo;
  mitigated by Decision 5's explicit "for the upcoming service backend" labeling.
```
