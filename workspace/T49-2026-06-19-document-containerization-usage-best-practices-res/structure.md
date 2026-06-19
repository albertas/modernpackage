# Structure Outline

## Approach

Author one new reference doc, `docs/containerization.md`, capturing Podman-primary /
Docker-compatible containerization best practices for a `uv` + `Justfile` Python project,
grounded in `research.md` Q4–Q7. The doc is sliced into a foundation phase (skeleton +
`overview.md` index registration) followed by four content phases mirroring the research's
Q4→Q7 split. Each phase appends one or more self-contained `##` sections to the same file,
so each is independently valuable: if a later phase is dropped, the doc still opens, links,
and registers correctly. "Vertical" here means each phase crosses the doc-structure layer
(headings/nav), the content layer (prose + annotated example fences), and the integration
layer (index table / cross-references), and is verifiable unattended via `grep`, link
inspection, and `just check`.

**Note**: This task adds no Python. It adds illustrative `Containerfile`/`compose` snippets
*inside the doc only* — no real `Containerfile`/`compose.yml`/`Justfile` recipes land in the
repo (design "What We're NOT Doing"). `just check` is run after every phase purely to guard
against accidental code edits.

---

## Phase 1: Skeleton & Index Registration

Create `docs/containerization.md` with the conforming H1, line-3 back-link, intro paragraph,
and empty `##` section headers for the four content areas; register the doc in the
`overview.md` index table. Delivers a navigable, correctly-styled doc shell end-to-end.

**Files**: `docs/containerization.md` (new), `docs/overview.md` (one table row)
**Key changes**:
- Line 1: `# modernpackage — Containerization` (Title Case, em-dash subtitle per
  `research.md:11`)
- Line 3: `[overview.md](overview.md)` standalone back-link (`research.md:13`)
- 1–2 sentence intro before first H2, stating no containerization exists in-repo today and
  this is forward-looking reference for the future backend (design Desired End State 2)
- Empty H2 headers: `## Image Authoring`, `## Podman Usage & Docker Compatibility`,
  `## Security & Runtime`, `## Local Multi-Service Stacks` (design Decision 7)
- `overview.md:21-28` table gains one row:
  `| [containerization.md](containerization.md) | **Containerization**: image authoring,
  Podman/Docker compatibility, security, local multi-service stacks. |`

**Verify**: `just check` passes.
`head -3 docs/containerization.md` line 1 matches `^# modernpackage — ` and line 3 equals
`[overview.md](overview.md)`.
`grep -c 'containerization.md' docs/overview.md` returns ≥ 1.
`grep -c '^## ' docs/containerization.md` returns 4.

---

## Phase 2: Image Authoring (Q4)

Fill `## Image Authoring`: uv install via `COPY --from=ghcr.io/astral-sh/uv:<pinned>`,
slim/distroless base choice, multi-stage builder→runtime, two-phase `uv sync` layer caching,
build env vars, `.dockerignore`, and PATH venv activation — with an annotated example
`Containerfile` fence using a Python **3.14** base and a note on the GitLab private index
(design Decision 4).

**Files**: `docs/containerization.md`
**Key changes**:
- H3 subsections (Title Case): `### Installing uv`, `### Base Image Selection`,
  `### Multi-Stage Builds`, `### Layer Caching`, `### Build Environment Variables`,
  `### venv Activation`
- One language-hinted ```` ```bash ```` / Containerfile fence with `#` inline comments
  (`research.md:15`); env vars `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`,
  `UV_PYTHON_DOWNLOADS=0` shown as inline code
- `**Note**:` callout on 3.14 base-tag availability + placeholder-tag fallback (design Open
  Risk); `**Note**:` on GitLab `gitlab` uv index needing a build secret (forward-ref to
  Phase 4)
- Every external claim carries a `research.md`-cited source URL inline (design Decision 9):
  Astral uv Docker guide (`research.md:54`)

**Verify**: `just check` passes.
`grep -c 'ghcr.io/astral-sh/uv' docs/containerization.md` ≥ 1.
`grep -c '3.14' docs/containerization.md` ≥ 1.
`grep -Ec 'UV_COMPILE_BYTECODE|UV_LINK_MODE|UV_PYTHON_DOWNLOADS' docs/containerization.md` ≥ 1.
`grep -c 'docs.astral.sh/uv' docs/containerization.md` ≥ 1 (source cited).

---

## Phase 3: Podman Usage & Docker Compatibility (Q5)

Fill `## Podman Usage & Docker Compatibility`: rootless user namespaces, UID-mapping modes,
SELinux `:z`/`:Z`, `alias docker=podman` CLI parity, `Containerfile` vs `Dockerfile`
resolution, OCI format, the Docker-API socket, compose-provider options, and the
"keep config Docker-compatible" ruleset (file name, OCI, vendor-neutral spec, `x-podman.*`).

**Files**: `docs/containerization.md`
**Key changes**:
- H3 subsections: `### Rootless Containers`, `### Docker CLI Parity`,
  `### Docker-API Socket`, `### Compose Providers`, `### Keeping Config Docker-Compatible`
- `bash` fences for `podman build`, `systemctl --user enable --now podman.socket`,
  `export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`
- `--userns=keep-id`, `:z`/`:Z`/`:U`, `BUILDAH_FORMAT=docker`, `x-podman.*` as inline code
- Sources cited inline: Red Hat rootless userns modes (`research.md:68`), docs.podman.io
  (`research.md:70`), Red Hat Podman vs Docker Compose (`research.md:72`)

**Verify**: `just check` passes.
`grep -c 'alias docker=podman' docs/containerization.md` ≥ 1.
`grep -Ec 'userns=keep-id|:Z|:z' docs/containerization.md` ≥ 1.
`grep -c 'x-podman' docs/containerization.md` ≥ 1.
`grep -Ec 'redhat.com|podman.io' docs/containerization.md` ≥ 1 (sources cited).

---

## Phase 4: Security & Runtime (Q6)

Fill `## Security & Runtime`: non-root user creation + `USER`, image scanning
(Trivy/Grype/Scout), build-time and runtime secrets (no `ARG`/`ENV`), stdlib `HEALTHCHECK`,
volumes for live-reload vs persistence, and dev networking (`127.0.0.1` bind). Labels
service-oriented items "for the upcoming service backend" (design Decision 5).

**Files**: `docs/containerization.md`
**Key changes**:
- H3 subsections: `### Non-Root User`, `### Image Scanning`, `### Secrets`,
  `### Healthchecks`, `### Volumes & Networking`
- Annotated fences: `useradd --system ... appuser` + `USER appuser`;
  `RUN --mount=type=secret,id=...`; stdlib `HEALTHCHECK ... python -c "import urllib..."`
- `**Important**:` callout that secrets never go in `ARG`/`ENV` (persist in layers)
- Sources cited inline: OWASP Docker Security Cheat Sheet (`research.md:81`), Docker build
  secrets / Compose secrets (`research.md:83`), OneUptime healthcheck (`research.md:84`)

**Verify**: `just check` passes.
`grep -Ec 'USER appuser|useradd' docs/containerization.md` ≥ 1.
`grep -Ec 'Trivy|Grype|Scout' docs/containerization.md` ≥ 1.
`grep -c 'type=secret' docs/containerization.md` ≥ 1.
`grep -c 'HEALTHCHECK' docs/containerization.md` ≥ 1.

---

## Phase 5: Local Multi-Service Stacks (Q7)

Fill `## Local Multi-Service Stacks`: compose-spec structure (omit `version:`),
service-name DNS networking (`db:5432`), the three run paths (`docker compose` /
`podman compose` / `podman-compose`), portability rules, and `depends_on` +
`healthcheck` startup ordering — with an annotated example `compose.yml` (app + Postgres).

**Files**: `docs/containerization.md`
**Key changes**:
- H3 subsections: `### Compose File Structure`, `### Service Networking`,
  `### Running the Stack`, `### Startup Ordering`
- One annotated ```` ```yaml ```` compose fence: top-level `services:` (no `version:`),
  `depends_on: {db: {condition: service_healthy}}`, `pg_isready` healthcheck
- `**Important**:` callout to omit `version:` (obsolete since Compose V2)
- Sources cited inline: Compose Specification (`research.md:93`), Compose startup order
  (`research.md:96`)

**Verify**: `just check` passes.
`grep -Ec '^services:|services:' docs/containerization.md` ≥ 1 and
`grep -c 'version:' docs/containerization.md` == 0 (must be omitted).
`grep -c 'service_healthy' docs/containerization.md` ≥ 1.
`grep -c 'pg_isready' docs/containerization.md` ≥ 1.

---

## Phase 6: Whole-Doc Consistency Pass

Verify the finished doc against the design's style + traceability gates and the
~250–350-line size target (design Decision 8). No new content; tighten only what fails a
check.

**Files**: `docs/containerization.md` (touch-ups only)
**Verify**: `just check` passes.
`wc -l docs/containerization.md` is between 250 and 350.
`grep -c '> \[!' docs/containerization.md` == 0 (no GitHub admonitions; design Patterns).
`head -1 docs/containerization.md | grep -c '^---'` == 0 (no YAML front-matter).
Extract every `http(s)://` URL in the doc and confirm each also appears in `research.md`
(`grep -oE 'https?://[^ )]+' docs/containerization.md` — each must be `grep`-findable in
`research.md`; no un-researched claims, design Decision 9).
`grep -c '^## ' docs/containerization.md` == 4 (the four Q4–Q7 sections, unchanged).

---

## Testing Checkpoints

- **After Phase 1**: file exists; H1 + line-3 back-link conform; 4 empty `##` sections;
  `overview.md` index row present; `just check` green.
- **After Phase 2**: Image Authoring complete — uv `COPY --from`, 3.14 base, uv env vars,
  Astral source cited.
- **After Phase 3**: Podman/Docker compatibility complete — `alias docker=podman`, rootless
  userns, `x-podman.*`, Red Hat/Podman sources cited.
- **After Phase 4**: Security & Runtime complete — non-root `USER`, scanners, `type=secret`,
  `HEALTHCHECK`; OWASP/Docker sources cited.
- **After Phase 5**: Multi-service stacks complete — compose fence with no `version:`,
  `service_healthy`, `pg_isready`; Compose-spec source cited.
- **After Phase 6**: 250–350 lines; no admonitions/front-matter; every URL traces to
  `research.md`; doc reads as a peer of `specification.md`.

Each phase only appends to its own `##` section (plus Phase 1's shared edits), so a failed
later phase leaves all earlier sections independently valid and shippable.
