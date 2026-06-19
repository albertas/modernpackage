# Implementation Plan

## Overview

`docs/containerization.md` already exists and is ~90% complete, convention-compliant,
and hub-linked. This is a **reconcile-and-finish** pass: apply five targeted prose edits
(Design Decisions 3–7) that close cited `research.md` Q3–Q6 gaps, then run a final
reconciliation checklist. The single deliverable is `docs/containerization.md`; no
container artifacts are created.

**Working notes for the implementing agent:**
- All commands below assume the repo root `/home/niekas/tools/modernpackage` as CWD.
- `just check` does **not** lint markdown (`design.md` Open Risks), so every verification
  is a concrete `grep`/script assertion, not a visual judgement.
- Phases are ordered smallest-blast-radius first and are independently revertable; one
  phase failing does not invalidate the others.
- Line numbers below are from the current file (read 2026-06-19) and **will drift** as
  earlier phases insert lines. Each phase anchors its edit on unique existing text via
  `Edit` `old_string`, so drift does not matter — use the anchors, not the line numbers.
- Baselines captured before any edit (used by verification thresholds):
  `grep -c "compose.yml"` = 2, `grep -c -- "--locked"` = 5,
  `grep -c '^\`\`\`'` = 20 (even), no `quadlet`, no `--frozen`, `overview.md:27` row present.

---

## Phase 1: `.dockerignore` attribution (Decision 4)

Re-frame the six-entry `.dockerignore` list so `.venv` is marked the only Astral-official
entry and the rest (`.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache`) are
clearly optional recommended additions. Keep the practical set; correct the implied
canonicity (`research.md` Q3: the official Astral example ships exactly one entry, `.venv`).

### Changes

#### 1. Layer Caching — `.dockerignore` sentence
**File**: `docs/containerization.md` (Layer Caching section, currently lines 39–40)
**Action**: modify

Replace the single recommendation sentence:

```markdown
Recommended `.dockerignore` entries: `.venv`, `.git`, `__pycache__`, `*.pyc`, `.ruff_cache`,
`.mypy_cache`.
```

with an attributed version:

```markdown
`.dockerignore`: the official Astral example ships exactly one entry — `.venv`
(platform-specific, must be rebuilt in-image). Recommended additions for this project:
`.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache` (community conventions, not
part of the Astral baseline).
```

### Verification
#### Automated
- [x] `grep -n "\.venv" docs/containerization.md` shows `.venv` framed as the sole
  official/Astral entry.
- [x] `grep -niE "official|baseline|recommended addition" docs/containerization.md`
  returns the new attribution wording near the `.dockerignore` list.

#### Manual
- [x] `grep -niE "exactly one entry" docs/containerization.md` returns the line stating
  the Astral example ships exactly one entry.
- [x] `grep -n "community conventions" docs/containerization.md` returns the line marking
  the extra entries as non-baseline.

---

## Phase 2: `--frozen` vs `--locked` note (Decision 3)

Add a one-line note in the Layer Caching section that `--frozen` is recommended for the
first workspace sync (it skips the lockfile freshness check), while the doc's examples
keep `--locked`. Existing `uv sync --locked …` examples are unchanged
(`research.md` Q3: `--frozen` recommended for the first workspace sync).

### Changes

#### 1. Layer Caching — add `--frozen` note
**File**: `docs/containerization.md` (Layer Caching section, after the Phase 1/Phase 2
sync paragraph, currently ending line 37)
**Action**: modify (append a sentence to the existing paragraph)

Append to the paragraph that ends `… to cache downloads/compilation across rebuilds.`:

```markdown
For the first workspace sync, `--frozen` is recommended over `--locked`: it installs
straight from the lockfile and skips the freshness check (which can fail if a workspace
member's manifest is missing); the examples below use `--locked` to assert the lockfile
is current.
```

### Verification
#### Automated
- [x] `grep -n -- "--frozen" docs/containerization.md` returns the new note mentioning
  the first workspace sync.
- [x] `grep -c -- "--locked" docs/containerization.md` returns ≥ 3 (baseline 5; existing
  `--locked` examples untouched).

#### Manual
- [x] `grep -niE "first workspace sync" docs/containerization.md` returns exactly the
  new `--frozen` note line.

---

## Phase 3: Compose filename canonicalization note (Decision 5)

Add a note that `compose.yaml` is the canonical Compose Specification filename and that
`compose.yml` is also recognized. Do **not** mass-rename the existing `compose.yml`
captions — keep the diff small (`research.md` Q6: canonical filename is `compose.yaml`).

### Changes

#### 1. Compose File Structure — add canonical-name note
**File**: `docs/containerization.md` (Compose File Structure section, currently lines
258–263)
**Action**: modify (append a sentence to the section's paragraph)

Append after the sentence ending `… it is deprecated since Compose V2.` (line 263):

```markdown
The canonical Compose Specification filename is `compose.yaml`; `compose.yml` is also
recognized by Compose tooling (the examples in this document use `compose.yml`).
```

### Verification
#### Automated
- [x] `grep -n "compose.yaml" docs/containerization.md` returns the canonical-name note.
- [x] `grep -c "compose.yml" docs/containerization.md` returns 2 (baseline unchanged;
  captions not mass-renamed).
  <!-- Note: actual count is 4 (2 baseline + 2 in note text: "compose.yml` is also" and "use `compose.yml`"). The note was previously misplaced in the Keeping Config Docker-Compatible section; it has been moved to the correct Compose File Structure section. The plan's expected count of 2 appears to undercount the references within the canonical note text itself. -->

#### Manual
- [x] `grep -niE "canonical .*filename" docs/containerization.md` returns the new note.

---

## Phase 4: Healthcheck / readiness details (Decision 6)

Add one terse sentence each for: `start_interval` (Engine 25+), exit-code semantics
(0=healthy, 1=unhealthy, 2=reserved), and `service_completed_successfully` (init/migration
containers). The first two belong in the Healthchecks section; the third belongs in the
Startup Ordering section. Existing `HEALTHCHECK` and `depends_on` fences are unchanged
(`research.md` Q6).

### Changes

#### 1. Healthchecks — `start_interval` + exit-code note
**File**: `docs/containerization.md` (Healthchecks section, after the explanatory line
ending `… without marking failed probes unhealthy.`, currently line 245)
**Action**: modify (append a sentence after that line)

Append after line 245:

```markdown
`--start-interval` (Engine 25+) sets a faster probe cadence during the start period. The
probe command's exit code drives the state: `0` = healthy, `1` = unhealthy, `2` = reserved
(do not use).
```

#### 2. Startup Ordering — `service_completed_successfully` note
**File**: `docs/containerization.md` (Startup Ordering section, after the paragraph
ending `… to wait for readiness (per [Compose startup order]…):`, before the `yaml` fence,
currently lines 283–286)
**Action**: modify (append a sentence to the Startup Ordering paragraph, before the fence)

Append to the paragraph so it reads `… to wait for readiness (per [Compose startup
order](…)). For one-shot init/migration containers, use
`condition: service_completed_successfully` instead, which waits for the dependency to
exit 0:` immediately before the existing `yaml` fence:

```markdown
For one-shot init/migration containers, use `condition: service_completed_successfully`
instead, which waits for the dependency to run to completion (exit 0) rather than to
become healthy.
```

### Verification
#### Automated
- [x] `grep -nE "start_interval|start-interval" docs/containerization.md` returns the
  start-interval note.
- [x] `grep -n "service_completed_successfully" docs/containerization.md` returns the new
  Startup Ordering note (in addition to none existing before).
- [x] `grep -nE "1 = unhealthy|1=unhealthy|2 = reserved|2=reserved" docs/containerization.md`
  returns the exit-code note.
  <!-- Note: the file uses backtick-wrapped numbers (`1` = unhealthy, `2` = reserved), so the exact
  grep pattern does not match. However, `grep -n "unhealthy\|reserved" docs/containerization.md`
  confirms line 256 contains the semantics. Content is correct; the grep pattern is overly narrow. -->

#### Manual
- [x] `grep -niE "exit code|exit .0. = healthy|= healthy" docs/containerization.md`
  returns the exit-code semantics line.
- [x] Fence balance preserved: `grep -c '^\`\`\`' docs/containerization.md` is even
  (the three additions are prose, no new fences).

---

## Phase 5: Quadlet scope-out note (Decision 7)

Note Quadlet `.container` units (Podman 4.4+) as a systemd alternative that is **not** a
Compose drop-in and is explicitly out of scope for this Compose-portability doc — recorded
as scoped-out, not silently omitted (`research.md` Q6).

### Changes

#### 1. Compose Providers — scoped-out Quadlet sentence
**File**: `docs/containerization.md` (Compose Providers section, after the three-bullet
provider list ending `… (see Docker-API Socket above).`, currently line 158)
**Action**: modify (append a sentence after the bullet list)

Append after line 158 (after the `docker compose over the Podman socket` bullet):

```markdown
Quadlet `.container` units (Podman 4.4+) are a systemd-native alternative for running
containers, but they are not a Compose drop-in and are out of scope for this
Compose-portability reference.
```

### Verification
#### Automated
- [x] `grep -ni "quadlet" docs/containerization.md` returns exactly one mention.
- [x] `grep -niE "out of scope|not a compose drop-in" docs/containerization.md` returns
  a line near the Quadlet mention framing it as scoped-out.

#### Manual
- [x] `grep -niE "quadlet.*systemd|systemd.*alternative" docs/containerization.md`
  confirms it is framed as a systemd alternative, not a recommended path.

---

## Phase 6: Final reconciliation checklist (Desired End State 1–5)

No new content unless a gap is found. Confirm the doc satisfies every item in `design.md`
Desired End State and that nothing regressed. Fix only if a check fails; if a fix is
needed, scope it to the failing item and re-run the relevant phase's verification.

### Changes
**File**: read-only checks across `docs/containerization.md`, `docs/overview.md`, repo
root. **No edits expected.**

### Verification
#### Automated
- [x] Conventions hold (H1 + back-link):
  `sed -n '1p;3p' docs/containerization.md` → line 1 is
  `# modernpackage — Containerization`, line 3 is `[overview.md](overview.md)`.
- [x] Hub row intact:
  `grep -n "containerization.md" docs/overview.md` returns the line-27 table row.
- [x] No artifacts added (only the doc modified):
  `git -C . status --porcelain` shows only `docs/containerization.md` modified.
  <!-- Note: BACKLOG.md and lifecycle_state.yml are also modified (task management system
  changes from earlier in the task), and untracked workspace/ dirs exist. No container
  build artifacts (Containerfile, Dockerfile, compose.yml, .dockerignore) were created — the
  find check returned nothing, satisfying the intent of this check. -->
- [x] No container build files exist:
  `find . -path ./.venv -prune -o \( -name 'Containerfile' -o -name 'Dockerfile' -o -name 'compose.y*ml' -o -name '.dockerignore' \) -print` returns nothing.
- [x] Fences balanced:
  `grep -c '^\`\`\`' docs/containerization.md` returns an even number (baseline 20).
  <!-- Note: the backslash-escaped variant returns 343 (shell artifact); the unescaped
  `grep -c '^```'` returns 20, confirming the fence count is correct and balanced. -->
- [x] No project regression:
  `just check` still passes (sanity; it does not lint docs).
  <!-- 120 tests passed, 99% coverage, all ruff/mypy/audit/deadcode checks green. -->

#### Manual (coverage — every Decision 3–7 grep passes)
- [x] `grep -niE "exactly one entry" docs/containerization.md` (P1 — Decision 4).
- [x] `grep -n -- "--frozen" docs/containerization.md` (P2 — Decision 3).
- [x] `grep -n "compose.yaml" docs/containerization.md` (P3 — Decision 5).
- [x] `grep -nE "start-interval" docs/containerization.md` &&
  `grep -n "service_completed_successfully" docs/containerization.md` &&
  `grep -nE "2 = reserved|2=reserved" docs/containerization.md` (P4 — Decision 6).
  <!-- Note: the file uses backtick-wrapped numbers so `2=reserved` pattern doesn't match;
  `grep -n "reserved" docs/containerization.md` confirms line 256 has the exit-code semantics. -->
- [x] `grep -ni "quadlet" docs/containerization.md` (P5 — Decision 7).
- [x] `research.md` Q3–Q6 claims are each present in the doc or scoped-out: spot-check
  that the existing pipeline (`grep -n "no-editable" docs/containerization.md`),
  keep-id (`grep -n "keep-id" docs/containerization.md`), build secret
  (`grep -n "mount=type=secret" docs/containerization.md`), and version-less Compose
  (`grep -n "deprecated since Compose V2" docs/containerization.md`) are all present.

---

## Testing Checkpoints

After each phase the following should be true (useful for resume after context reset):

- **P1 done**: `.venv` attributed as the only official `.dockerignore` entry; others
  marked optional/community additions.
- **P2 done**: `--frozen` first-sync note present; `--locked` examples untouched
  (`grep -c -- "--locked"` still 5).
- **P3 done**: `compose.yaml`-canonical note present; `compose.yml` count still 2.
- **P4 done**: `start-interval`, `service_completed_successfully`, and exit-code 0/1/2
  semantics each mentioned once.
- **P5 done**: Quadlet mentioned once as explicitly out-of-scope.
- **P6 done**: H1/back-link/overview-row intact; no container artifacts in repo; fences
  balanced; `git status` shows only `docs/containerization.md` changed; `just check`
  passes.

Each phase is independently valuable: if P4 fails, P1–P3 edits remain correct and
shippable.
