# Design Discussion

## Current State

A complete containerization document **already exists** at `docs/containerization.md`
(328 lines, modified today 2026-06-19) and is already wired into the docs hub:

- It opens with the correct H1 `# modernpackage — Containerization`
  (`docs/containerization.md:1`) and the line-3 back-link `[overview.md](overview.md)`
  (`docs/containerization.md:3`), matching the convention every non-index page follows
  (`research.md` Q1; `docs/backlog_formats.md:3`).
- `docs/overview.md:27` already lists a `containerization.md` row in the Documentation
  Files table with the bold purpose summary.
- It correctly states the repo "ships no container artifacts today"
  (`docs/containerization.md:5-9`) and frames all code blocks as illustrative templates.
- It covers all six research areas: image authoring (`:11-101`), Podman/Docker
  compatibility (`:103-170`), security & runtime (`:172-254`), and multi-service stacks
  (`:256-328`).

No container build artifacts exist in-repo (`research.md` Q1: no `Containerfile`,
`compose.yml`, `.dockerignore`). The toolchain the examples target is `uv` + `just`,
Python `>= 3.14` (`pyproject.toml:8`), runtime `dependencies = []` (`pyproject.toml:18`),
and a private GitLab uv index named `gitlab` (`pyproject.toml:97-99`) whose credential
env vars are `UV_INDEX_GITLAB_USERNAME` / `UV_INDEX_GITLAB_PASSWORD` (`research.md` Q2).

**Conclusion:** This is not a blank-slate authoring task. It is a *reconcile-and-finish*
task — verify the existing doc against the 2026 external findings, close the small gaps,
correct the few divergences, and confirm conventions hold.

## Desired End State

`docs/containerization.md` remains the single deliverable: a forward-looking reference,
accurate against `research.md` Q3–Q6, internally consistent, and convention-compliant.

Verification (no automated markdown gate exists — `just check` does not lint docs, so
verification is a manual checklist):
1. Every external best-practice claim in `research.md` Q3–Q6 is either present in the doc
   or consciously scoped out under "What We're NOT Doing".
2. Conventions hold: H1 form, line-3 back-link, language-tagged fences, pipe tables,
   present-tense declarative tone (`research.md` Q1).
3. `docs/overview.md:27` table entry still accurate; no other docs page needs editing.
4. No container build artifacts are added to the repo (doc stays "no artifacts today").
5. All inline `file:line` / external links resolve; code fences are syntactically valid.

## Patterns to Follow

- **H1 + back-link**: `# modernpackage — <Topic>` then bare `[overview.md](overview.md)`
  on line 3 — already correct (`docs/containerization.md:1-3`).
- **Doc-hub table entry**: keep the existing row at `docs/overview.md:27`; do not add
  duplicate navigation.
- **Fenced code with language tags**: `dockerfile`, `bash`, `yaml` already used
  (`docs/containerization.md:66,131,298`); preserve this.
- **Illustrative-not-committed framing**: every Containerfile/Compose block is captioned
  as a template (`docs/containerization.md:67,299`). Keep this — it is the contract that
  prevents these snippets from being mistaken for real build files.
- **uv-in-Docker canonical pipeline** (`research.md` Q3): distroless `COPY --from` uv bin,
  two-phase `uv sync` with cache + bind mounts, `--no-editable`, `PATH` venv activation —
  already encoded at `docs/containerization.md:66-93`.
- **Build-secret for the GitLab index** (`research.md` Q5): `RUN --mount=type=secret`
  feeding `UV_INDEX_GITLAB_PASSWORD`, never `ARG`/`ENV` — already at
  `docs/containerization.md:216-222`.

**Pattern NOT to follow / divergence to correct:** the existing `.dockerignore`
recommendation lists six entries (`docs/containerization.md:39-40`). The official Astral
example ships **exactly one** entry, `.venv` (`research.md` Q3); `.git`/`__pycache__`/`*.pyc`
are community additions, and `.ruff_cache`/`.mypy_cache` are not cited anywhere in the
research. Keep the practical set but attribute it honestly (mark `.venv` as the only
official entry, the rest as recommended additions) rather than implying all six are
canonical.

## Design Decisions

1. **Refine the existing doc, do not rewrite** — chosen because it is already accurate,
   convention-compliant, and hub-linked. A rewrite would violate CLAUDE.md §3 (surgical
   changes) and risk regressing correct content. Edits are scoped to the specific gaps below.
2. **Treat the deliverable as already 90% done** — record this explicitly so downstream
   structure/plan steps size the work as a short edit pass, not a from-scratch write.
3. **Close `--frozen` vs `--locked` gap** — `research.md` Q3 notes `--frozen` is
   recommended for the first workspace sync; the doc only uses `--locked`. Add a one-line
   note. Low risk, single sentence.
4. **Correct the `.dockerignore` attribution** (see Patterns) — re-frame the six-entry
   list so `.venv` is the official baseline and the rest are clearly optional additions.
5. **Compose filename naming** — `research.md` Q6 calls `compose.yaml` the canonical
   filename; the doc uses `compose.yml` in captions (`docs/containerization.md:299`). Add
   a note that `compose.yaml` is canonical and `compose.yml` is also recognized; do not
   mass-rename, to keep the diff small.
6. **Add brief mentions for the missing readiness details** — `start_interval` (Engine
   25+), `service_completed_successfully` for init/migration containers, and exit-code
   semantics (0/1/2) from `research.md` Q6 are worth one sentence each in the healthcheck
   section. Kept terse to avoid bloat.
7. **Do NOT add Quadlet coverage** — `research.md` Q6 mentions Quadlet `.container` units
   as a systemd alternative, but it is "not a Compose drop-in" and out of scope for a
   Compose-portability doc preparing a future backend. Note as scoped-out, not omitted.
8. **Leave the Python 3.14 tag caveat as-is** — already flagged at
   `docs/containerization.md:95-97`; `research.md` Open Areas confirms registry tag
   availability is still unverified. No change beyond what exists.

## What We're NOT Doing

- **Not committing any container artifacts** — no `Containerfile`, `compose.yaml`, or
  `.dockerignore` files are added. The repo stays "no artifacts today"; everything remains
  illustrative in the doc.
- **Not rewriting the document** — only targeted edits for the gaps in Design Decisions.
- **Not adding Quadlet / systemd unit guidance** (Decision 7).
- **Not touching other `docs/` pages** beyond confirming the `overview.md:27` row is
  accurate (it already is).
- **Not tracing `vupi`'s resolution source** (PyPI vs the `gitlab` index) — flagged in
  `research.md` Open Areas; not required to finish a best-practices doc.
- **Not adding a markdown-lint recipe to the Justfile** — out of scope; verification stays
  a manual checklist.

## Open Risks

- **No automated verification for docs.** `just check` does not lint markdown, so
  correctness rests on the manual checklist in Desired End State. Mitigate by reviewing
  every external claim against `research.md` Q3–Q6 explicitly.
- **External findings may drift.** uv's official private-index Docker-auth guidance is
  still pending upstream (uv issue #11740, `research.md` Open Areas); the secret-mount
  pattern in the doc is community-documented, not Astral-official. Keep the doc's wording
  attributing it as current best practice, not vendor-blessed.
- **3.14 base-image tags unverified.** If `python:3.14-slim` / `ghcr.io/astral-sh/uv:
  python3.14-*` do not exist yet, the example's caveat (`docs/containerization.md:95-97`)
  must remain prominent; do not present 3.14 tags as confirmed.
- **Scope-creep temptation.** The doc is already strong; the risk is over-editing. Hold
  every change to a line in Design Decisions and trace it to a `research.md` finding.
