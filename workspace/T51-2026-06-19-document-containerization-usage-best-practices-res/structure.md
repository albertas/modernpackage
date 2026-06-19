# Structure Outline

## Approach

`docs/containerization.md` already exists, is ~90% complete, convention-compliant, and
hub-linked. This is a **reconcile-and-finish** pass, not an authoring task: apply the
five targeted edits from `design.md` Design Decisions 3–7, then run a final
reconciliation checklist. The single deliverable is `docs/containerization.md`; no
container artifacts are added.

**Slicing note (deviation from the standard vertical-slice model):** there is only one
layer here — a markdown file. There is no DB/service/API/UI to cross. Each "slice" is
therefore one self-contained, independently-revertable edit to a distinct section of the
doc, each closing one cited `research.md` gap. Because `just check` does not lint
markdown (`design.md` Open Risks), every verification is a concrete `grep`/script
assertion the agent can run unattended, not a visual judgement. Phases are ordered
smallest-blast-radius first; any phase can fail without invalidating the others.

---

## Phase 1: `.dockerignore` attribution (Decision 4)

Re-frame the six-entry `.dockerignore` list so `.venv` is marked the only Astral-official
entry and `.git`/`__pycache__`/`*.pyc`/`.ruff_cache`/`.mypy_cache` are clearly optional
additions. Keep the practical set; correct the implied canonicity.

**Files**: `docs/containerization.md` (lines 39–40, Layer Caching section)
**Key changes**:
- Prose edit only — no code fence, no signatures. Distinguish "official baseline
  (`.venv`)" from "recommended additions".

**Verify**: `grep -n "\.venv" docs/containerization.md` shows `.venv` framed as the sole
official/Astral entry; `grep -niE "official|baseline|additional|recommended addition" docs/containerization.md`
returns the new attribution wording near the `.dockerignore` list.

---

## Phase 2: `--frozen` vs `--locked` note (Decision 3)

Add a one-line note in the Layer Caching section that `--frozen` is recommended for the
first workspace sync (skips the freshness check), while the examples keep `--locked`.

**Files**: `docs/containerization.md` (Layer Caching, ~lines 34–37)
**Key changes**:
- Single sentence added; existing `uv sync --locked …` examples unchanged.

**Verify**: `grep -n -- "--frozen" docs/containerization.md` returns the new note
mentioning the first workspace sync; existing `--locked` occurrences still present
(`grep -c -- "--locked" docs/containerization.md` ≥ 3).

---

## Phase 3: Compose filename canonicalization note (Decision 5)

Add a note that `compose.yaml` is the canonical Compose Specification filename and
`compose.yml` is also recognized. Do **not** mass-rename the existing `compose.yml`
captions (keep the diff small).

**Files**: `docs/containerization.md` (Compose File Structure, ~lines 258–263)
**Key changes**:
- Single sentence added near the Compose File Structure heading.

**Verify**: `grep -n "compose.yaml" docs/containerization.md` returns the canonical-name
note; `grep -c "compose.yml" docs/containerization.md` confirms existing captions are
**not** mass-renamed (count unchanged from baseline ≈ 2).

---

## Phase 4: Healthcheck/readiness details (Decision 6)

Add one terse sentence each, in the Healthchecks section, for: `start_interval` (Engine
25+), `service_completed_successfully` (init/migration containers), and exit-code
semantics (0=healthy, 1=unhealthy, 2=reserved).

**Files**: `docs/containerization.md` (Healthchecks ~lines 232–245; the
`service_completed_successfully` note may sit in Startup Ordering ~lines 281–291)
**Key changes**:
- Three short sentences; existing `HEALTHCHECK` and `depends_on` fences unchanged.

**Verify**: `grep -nE "start_interval|service_completed_successfully" docs/containerization.md`
returns both terms; `grep -nE "exit (code )?0|1=unhealthy|2.*reserved" docs/containerization.md`
returns the exit-code note.

---

## Phase 5: Quadlet scope-out note (Decision 7)

Note Quadlet `.container` units (Podman 4.4+) as a systemd alternative that is **not** a
Compose drop-in and is explicitly out of scope for this Compose-portability doc — recorded
as scoped-out, not silently omitted.

**Files**: `docs/containerization.md` (Compose Providers ~lines 147–159, or Running the
Stack ~lines 270–279)
**Key changes**:
- Single scoped-out sentence.

**Verify**: `grep -ni "quadlet" docs/containerization.md` returns one mention framed as
out-of-scope / not a Compose drop-in.

---

## Phase 6: Final reconciliation checklist (Desired End State 1–5)

No new content unless a gap is found. Confirm the doc satisfies every item in
`design.md` Desired End State and that nothing regressed.

**Files**: read-only checks across `docs/containerization.md`, `docs/overview.md`,
repo root.
**Key changes**: none expected; fix only if a check fails.

**Verify** (all must pass):
- Conventions hold: `sed -n '1p;3p' docs/containerization.md` → line 1 is
  `# modernpackage — Containerization`, line 3 is `[overview.md](overview.md)`.
- Hub row intact: `grep -n "containerization.md" docs/overview.md` returns the line-27
  table row.
- No artifacts added: `git -C . status --porcelain` shows only `docs/containerization.md`
  modified; `find . -path ./.venv -prune -o \( -name 'Containerfile' -o -name 'Dockerfile' -o -name 'compose.y*ml' -o -name '.dockerignore' \) -print` returns nothing.
- Fences balanced: count of ```` ``` ```` lines is even —
  `grep -c '^```' docs/containerization.md` returns an even number.
- Coverage: every Decision 3–7 grep from Phases 1–5 passes; `research.md` Q3–Q6 claims
  are present or scoped-out.
- No project regression: `just check` still passes (sanity; it does not lint docs).

---

## Testing Checkpoints

After each phase the following should be true (useful for resume after context reset):

- **P1 done**: `.venv` attributed as the only official `.dockerignore` entry; others
  marked optional additions.
- **P2 done**: `--frozen` first-sync note present; `--locked` examples untouched.
- **P3 done**: `compose.yaml`-canonical note present; `compose.yml` captions not
  mass-renamed.
- **P4 done**: `start_interval`, `service_completed_successfully`, and exit-code 0/1/2
  semantics each mentioned once.
- **P5 done**: Quadlet mentioned once as explicitly out-of-scope.
- **P6 done**: H1/back-link/overview-row intact; no container artifacts in repo; fences
  balanced; `git status` shows only `docs/containerization.md` changed; `just check`
  passes.

Each phase is independently valuable: if P4 fails, P1–P3 edits remain correct and
shippable.
