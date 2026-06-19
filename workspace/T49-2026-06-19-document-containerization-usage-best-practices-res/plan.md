# Implementation Plan

## Overview

Author one new reference doc, `docs/containerization.md`, capturing Podman-primary /
Docker-compatible containerization best practices for this `uv` + `Justfile` Python project
(grounded in `research.md` Q4–Q7), and register it in the `docs/overview.md` index table. This
task is documentation-only: no real `Containerfile`/`compose.yml`/`.dockerignore`/`Justfile`
recipe lands in the repo — all container snippets live **inside the doc as illustrative
examples**.

### Conventions every phase must obey (from `design.md` Patterns & `research.md` Q1)

- **H1**: `# modernpackage — Containerization` (Title Case, em-dash subtitle).
- **Line 3**: standalone back-link `[overview.md](overview.md)` (line 2 blank).
- **Intro**: 1–2 sentences before the first `##`.
- **Headings**: `##`/`###` Title Case; no `####` (this is a conceptual reference, not the
  per-function API template of `architecture.md`).
- **Code fences**: language-hinted — ```` ```bash ```` for CLI, ```` ```yaml ```` for compose,
  ```` ```dockerfile ```` for Containerfile snippets; annotate expected output / explanation
  with `#` inline comments inside fences.
- **Inline code**: backticks for identifiers, flags, paths, env vars, filenames.
- **Callouts**: bold-prefixed standalone paragraphs `**Note**:` / `**Important**:` — **NOT**
  GitHub `> [!NOTE]` admonitions, and **no** YAML front-matter.
- **Sources**: every external claim carries an inline Markdown link whose URL **already appears
  in `research.md`** (verified in Phase 6). No new un-researched URLs.

### Resolved assumptions (no open questions)

- **3.14 base-image tag** (`design.md` Open Risk): the doc does **not** assert a concrete
  `python:3.14-slim` / `ghcr.io/astral-sh/uv:python3.14-*` tag exists. It shows the pattern with
  the 3.14 tag and adds a `**Note**:` that the exact tag must be confirmed against the registry
  and a placeholder/pinned-digest fallback used if unavailable. This satisfies the design without
  making an unverifiable claim.
- **GitLab `gitlab` uv index in builds** (`design.md` Open Risk): documented via the
  build-secret pattern (`RUN --mount=type=secret`), never by baking a token into a layer. Phase 2
  introduces it as a forward-reference; Phase 4 gives the concrete `--mount=type=secret` fence.
- **Index-table row placement**: insert the new row in `docs/overview.md` immediately after the
  `specification.md` row (current line 26), before the `README.md` row, keeping the `docs/` files
  grouped above the root-level `README.md`/`BACKLOG.md` rows.
- **`just check` for a docs-only change**: it touches no Python, so `just check` must stay green;
  running it after each phase guards against accidental code edits (`design.md` Verification).

---

## Phase 1: Skeleton & Index Registration

Create `docs/containerization.md` as a conforming, navigable shell with the four empty content
sections, and register it in the `docs/overview.md` index table. Delivers an end-to-end correct
doc skeleton even if no later phase lands.

### Changes

#### 1. New doc skeleton
**File**: `docs/containerization.md`
**Action**: create

````markdown
# modernpackage — Containerization

[overview.md](overview.md)

`modernpackage` ships no container artifacts today (no `Containerfile`, `compose.yml`, or
`.dockerignore` exist in-repo). This document is a forward-looking reference for containerizing a
modern `uv`-managed Python project — Podman-primary and Docker-compatible — to prepare for the
scaffolder's future service backend. All examples are illustrative templates, not committed
build files.

## Image Authoring

## Podman Usage & Docker Compatibility

## Security & Runtime

## Local Multi-Service Stacks
````

#### 2. Index registration
**File**: `docs/overview.md`
**Action**: modify (add exactly one table row after the `specification.md` row, line 26)

```markdown
| [containerization.md](containerization.md) | **Containerization**: image authoring, Podman/Docker compatibility, security, local multi-service stacks. |
```

### Verification
#### Automated
- [x] `just check` passes (guards against accidental Python edits).

#### Manual
- [x] `test "$(sed -n '1p' docs/containerization.md)" = '# modernpackage — Containerization'` (exit 0).
- [x] `test "$(sed -n '3p' docs/containerization.md)" = '[overview.md](overview.md)'` (exit 0).
- [x] `grep -c 'containerization.md' docs/overview.md` → ≥ 2 (one link in the row's filename
      column, one in the link target) — at minimum ≥ 1.
- [x] `grep -c '^## ' docs/containerization.md` → `4`.
- [x] `grep -c '^#### ' docs/containerization.md` → `0` (no per-item H4 template).

---

## Phase 2: Image Authoring (Q4)

Fill `## Image Authoring`: install uv via `COPY --from`, base-image selection, multi-stage
builds, two-phase `uv sync` layer caching, uv build env vars, `.dockerignore`, and PATH venv
activation — anchored by one annotated `dockerfile` fence using a Python **3.14** base, plus a
forward-reference note on the GitLab private uv index.

### Changes

#### 1. Image Authoring section body
**File**: `docs/containerization.md`
**Action**: modify (append H3 subsections + example fence under `## Image Authoring`)

H3 subsections (Title Case), in order:
`### Installing uv`, `### Base Image Selection`, `### Multi-Stage Builds`, `### Layer Caching`,
`### Build Environment Variables`, `### venv Activation`.

Key content points (each external claim links the Astral uv Docker guide,
`https://docs.astral.sh/uv/guides/integration/docker/`, cited at `research.md:54`):

- **Installing uv**: `COPY --from=ghcr.io/astral-sh/uv:<pinned-version> /uv /uvx /bin/` preferred
  over `pip install uv`; pin the uv version (avoid drifting tags per `design.md` Open Risk).
- **Base Image Selection**: `python:3.x-slim` recommended; Alpine discouraged (musl/wheel);
  distroless for minimal attack surface; keep builder/runtime OS family matched (glibc).
- **Multi-Stage Builds**: builder builds `.venv`, runtime copies only `/app/.venv`; runtime needs
  no `uv` when PATH-activated; `--no-editable` required so runtime carries no source.
- **Layer Caching**: two-phase sync — phase 1 bind-mount `uv.lock`+`pyproject.toml` then
  `uv sync --locked --no-install-project`; phase 2 `COPY . /app` then `uv sync --locked`; use
  `--mount=type=cache,target=/root/.cache/uv` (BuildKit).
- **Build Environment Variables**: `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`,
  `UV_PYTHON_DOWNLOADS=0` as inline code with one-line rationale each.
- **venv Activation**: `ENV PATH="/app/.venv/bin:$PATH"` is the production standard; only viable
  option for distroless.

Annotated example fence (illustrative — note the 3.14 base and inline `#` comments):

````dockerfile
# Illustrative Containerfile — template for the future backend, not committed to the repo.
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14            # repo requires-python >= 3.14 (pyproject.toml:8)

# --- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/   # pin uv; do not use a floating tag
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# phase 1: deps only — cached until uv.lock / pyproject.toml change
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
# phase 2: project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"   # activate venv; no uv needed at runtime
CMD ["modernpackage", "--help"]
````

Callouts to include verbatim-in-spirit:

- `**Note**:` Confirm a `python:3.14-slim` (and matching `ghcr.io/astral-sh/uv:python3.14-*`) tag
  exists in the registry before using it; if unavailable, pin a digest or use the nearest
  supported tag and treat 3.14 as a placeholder.
- `**Note**:` This project resolves dependencies from a private GitLab uv index named `gitlab`
  (`pyproject.toml`). A build that runs `uv sync` against it needs index credentials passed as a
  build secret — never an `ARG`/`ENV` token. See [§ Security & Runtime](#secrets).

#### 2. `.dockerignore` guidance (prose only)
**File**: `docs/containerization.md`
**Action**: modify (one bullet list under `### Layer Caching` or `### Multi-Stage Builds`)

List `.venv`, `.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache` as recommended
`.dockerignore` entries (Astral explicitly recommends adding `.venv`). Prose/inline-code only —
do **not** create a real `.dockerignore`.

### Verification
#### Automated
- [x] `just check` passes.

#### Manual
- [x] `grep -c 'ghcr.io/astral-sh/uv' docs/containerization.md` → ≥ 1.
- [x] `grep -c '3.14' docs/containerization.md` → ≥ 1.
- [x] `grep -Ec 'UV_COMPILE_BYTECODE|UV_LINK_MODE|UV_PYTHON_DOWNLOADS' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'docs.astral.sh/uv' docs/containerization.md` → ≥ 1 (source cited).
- [x] `grep -c 'no-editable' docs/containerization.md` → ≥ 1 (multi-stage venv guidance present).
- [x] No new `Containerfile`/`Dockerfile`/`.dockerignore` created at repo root:
      `test -z "$(git -C /home/niekas/tools/modernpackage status --porcelain | grep -E 'Containerfile|Dockerfile|\.dockerignore')"` (exit 0).

---

## Phase 3: Podman Usage & Docker Compatibility (Q5)

Fill `## Podman Usage & Docker Compatibility`: rootless user namespaces & UID-mapping modes,
SELinux volume labels, `alias docker=podman` CLI parity, `Containerfile` vs `Dockerfile`
resolution & OCI format, the Docker-API socket, compose-provider options, and the
"keep config Docker-compatible" ruleset.

### Changes

#### 1. Section body
**File**: `docs/containerization.md`
**Action**: modify (append H3 subsections + `bash` fences under
`## Podman Usage & Docker Compatibility`)

H3 subsections, in order: `### Rootless Containers`, `### Docker CLI Parity`,
`### Docker-API Socket`, `### Compose Providers`, `### Keeping Config Docker-Compatible`.

Key content (sources linked inline):

- **Rootless Containers** — engine + containers run as unprivileged user via user namespaces;
  needs `/etc/subuid`/`/etc/subgid` ranges, `podman system migrate` after edits; UID-mapping
  modes: default, `--userns=keep-id` (best for mounted-source dev), `auto`/`nomap`; SELinux
  volume labels `:z` (shared) / `:Z` (private) / `:U` (chown to container UID); ports <1024 need
  `net.ipv4.ip_unprivileged_port_start`; default rootless net backend is `pasta` since Podman 5.0.
  Source: Red Hat rootless userns modes,
  `https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes` (`research.md:68`).
- **Docker CLI Parity** — `alias docker=podman`; `podman build` resolves `Containerfile` before
  `Dockerfile`; default OCI v1.0 output; `--format docker` / `BUILDAH_FORMAT=docker` for a Docker
  manifest. Source: docs.podman.io,
  `https://docs.podman.io/en/stable/markdown/podman.1.html` (`research.md:70`).
- **Docker-API Socket** — enable + point Docker tooling at the Podman socket.
- **Compose Providers** — `podman compose` (wrapper → docker-compose if present, else
  podman-compose; `PODMAN_COMPOSE_PROVIDER` override), `podman-compose` (standalone Python,
  rootless-first, `x-podman.*` extensions), `docker compose` over the Podman socket (fuller spec).
  Source: Red Hat Podman vs Docker Compose,
  `https://www.redhat.com/en/blog/podman-compose-docker-compose` (`research.md:72`).
- **Keeping Config Docker-Compatible** — name the build file `Containerfile`, OCI format,
  vendor-neutral Compose spec, isolate Podman-only knobs under `x-podman.*`, fully-qualified image
  names.

Example `bash` fences (with `#` annotations):

```bash
alias docker=podman                       # drop-in CLI parity (official Podman guidance)
podman build -t modernpackage:dev .       # resolves Containerfile, then Dockerfile
podman run --userns=keep-id -v "$PWD/src:/app/src:Z" modernpackage:dev  # rootless dev mount
```

```bash
# Expose a Docker-compatible API socket for tools that speak the Docker API
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
loginctl enable-linger "$USER"            # keep the socket across reboots
```

Inline-code coverage required: `--userns=keep-id`, `:z`, `:Z`, `:U`, `BUILDAH_FORMAT=docker`,
`x-podman.*`.

### Verification
#### Automated
- [x] `just check` passes.

#### Manual
- [x] `grep -c 'alias docker=podman' docs/containerization.md` → ≥ 1.
- [x] `grep -Ec 'userns=keep-id|:Z|:z' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'x-podman' docs/containerization.md` → ≥ 1.
- [x] `grep -Ec 'redhat.com|podman.io' docs/containerization.md` → ≥ 1 (sources cited).
- [x] `grep -c 'DOCKER_HOST' docs/containerization.md` → ≥ 1 (socket guidance present).

---

## Phase 4: Security & Runtime (Q6)

Fill `## Security & Runtime`: non-root user creation + `USER`, image scanning (Trivy/Grype/
Scout), build-time and runtime secrets (no `ARG`/`ENV`), stdlib `HEALTHCHECK`, volumes for
live-reload vs persistence, and dev networking (`127.0.0.1` bind). Service-oriented items are
labeled "for the upcoming service backend."

### Changes

#### 1. Section body
**File**: `docs/containerization.md`
**Action**: modify (append H3 subsections + fences under `## Security & Runtime`)

H3 subsections, in order: `### Non-Root User`, `### Image Scanning`, `### Secrets`,
`### Healthchecks`, `### Volumes & Networking`.

Key content (sources linked inline):

- **Non-Root User** — explicit UID/GID system user, `COPY --chown`, `USER appuser` before `CMD`;
  on rootless Podman align perms with `--userns=keep-id:uid=1001,gid=1001` or `:U`. Sources:
  Docker building best practices `https://docs.docker.com/build/building/best-practices/`,
  OWASP Docker Security Cheat Sheet
  `https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html`
  (`research.md:81`).
- **Image Scanning** — Trivy (`trivy image myapp:latest`), Grype (`grype myapp:latest`), Docker
  Scout (`docker scout cves`). Sources: `https://trivy.dev/`, `https://github.com/anchore/grype`,
  `https://docs.docker.com/scout/` (`research.md:82`).
- **Secrets** — `**Important**:` never via `ARG`/`ENV` (persist in layers / `docker history`);
  build-time `RUN --mount=type=secret,id=...` + `docker build --secret`; runtime via Compose
  `secrets:` mounted read-only at `/run/secrets/<name>`. Connect the Phase 2 forward-reference:
  the GitLab `gitlab` index token is supplied here as a build secret. Sources: Docker build
  secrets `https://docs.docker.com/build/building/secrets/`, Compose secrets
  `https://docs.docker.com/compose/how-tos/use-secrets/` (`research.md:83`).
- **Healthchecks** — `HEALTHCHECK` with stdlib probe (no extra binary); label "for the upcoming
  service backend." Source: OneUptime
  `https://oneuptime.com/blog/post/2026-01-30-docker-health-check-best-practices/view`
  (`research.md:84`).
- **Volumes & Networking** — bind-mount source for live reload (`:ro`/`:Z`), named volumes for
  persistence; dev bind `127.0.0.1:8000:8000` (OWASP). Source: Compose networking
  `https://docs.docker.com/compose/how-tos/networking/` (`research.md:86`).

Annotated fences:

```dockerfile
# Non-root: explicit UID/GID, no home, no lastlog bloat
RUN groupadd --system --gid 1001 appgroup \
 && useradd --system --uid 1001 --gid appgroup --no-log-init --no-create-home appuser
COPY --chown=appuser:appgroup . /app
USER appuser                      # drop privileges before CMD
```

```dockerfile
# Build secret for the private GitLab uv index — never an ARG/ENV token
RUN --mount=type=secret,id=uv_index_token \
    UV_INDEX_GITLAB_PASSWORD="$(cat /run/secrets/uv_index_token)" \
    uv sync --locked --no-dev
# build with:  podman build --secret id=uv_index_token,src=./gitlab_token .
```

```dockerfile
# Stdlib healthcheck — no curl/wget needed in the image (for the future service backend)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health',timeout=4); sys.exit(0)"
```

### Verification
#### Automated
- [x] `just check` passes.

#### Manual
- [x] `grep -Ec 'USER appuser|useradd' docs/containerization.md` → ≥ 1.
- [x] `grep -Ec 'Trivy|Grype|Scout' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'type=secret' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'HEALTHCHECK' docs/containerization.md` → ≥ 1.
- [x] `grep -Ec 'docs.docker.com|owasp.org' docs/containerization.md` → ≥ 1 (sources cited).
- [x] `grep -c 'for the upcoming service backend' docs/containerization.md` → ≥ 1 (service items labeled).

---

## Phase 5: Local Multi-Service Stacks (Q7)

Fill `## Local Multi-Service Stacks`: compose-spec structure (omit `version:`), service-name DNS
networking (`db:5432`), the three run paths, portability rules, and `depends_on` + `healthcheck`
startup ordering — anchored by one annotated `yaml` compose fence (app + Postgres).

### Changes

#### 1. Section body
**File**: `docs/containerization.md`
**Action**: modify (append H3 subsections + `yaml` fence under `## Local Multi-Service Stacks`)

H3 subsections, in order: `### Compose File Structure`, `### Service Networking`,
`### Running the Stack`, `### Startup Ordering`.

Key content (sources linked inline):

- **Compose File Structure** — top-level `services` (required), plus `networks`/`volumes`/
  `secrets`; `**Important**:` omit `version:` (obsolete/ignored since Compose V2; warns if
  present). Source: Compose Specification
  `https://compose-spec.github.io/compose-spec/spec.html` (`research.md:93`).
- **Service Networking** — reach the DB at hostname `db:5432`
  (`postgresql://appuser:...@db:5432/appdb`); no IPs, no legacy `links:`.
- **Running the Stack** — `docker compose up`, `podman compose up`, `podman-compose up`;
  portability rules (no `version:`, core spec only, `x-*` for provider-specific, `CMD-SHELL` for
  shell-syntax healthcheck tests).
- **Startup Ordering** — long-form `depends_on: {db: {condition: service_healthy}}` plus a `db`
  `healthcheck:` (`pg_isready`); `start_period` covers Postgres init; `restart: true` restarts app
  if db turns unhealthy. Source: Compose startup order
  `https://docs.docker.com/compose/how-tos/startup-order/` (`research.md:96`).

Annotated compose fence:

````yaml
# Illustrative compose.yml — portable across docker compose / podman compose / podman-compose.
# No top-level version: — obsolete since Compose V2.
services:
  app:
    build: .
    ports:
      - "127.0.0.1:8000:8000"     # bind localhost only in dev (OWASP)
    environment:
      DATABASE_URL: postgresql://appuser:secret@db:5432/appdb   # service name as hostname
    depends_on:
      db:
        condition: service_healthy  # wait until db passes its healthcheck, not just starts
    # x-podman: {}                   # isolate Podman-only knobs here; ignored by Docker
  db:
    image: docker.io/library/postgres:17   # fully-qualified image name
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: appdb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s            # covers Postgres init scripts
    volumes:
      - pgdata:/var/lib/postgresql/data   # named volume for persistence
volumes:
  pgdata:
````

### Verification
#### Automated
- [x] `just check` passes.

#### Manual
- [x] `grep -Ec '^services:|services:' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'service_healthy' docs/containerization.md` → ≥ 1.
- [x] `grep -c 'pg_isready' docs/containerization.md` → ≥ 1.
- [x] In the compose example there is no `version:` key:
      `! grep -E '^\s*version:' docs/containerization.md` (exit 0). Note: `Podman 5.0`/version
      *prose* elsewhere is fine; this assertion targets a YAML `version:` key only.
- [x] No real `compose.yml`/`compose.yaml`/`docker-compose.yml` created in repo:
      `test -z "$(git -C /home/niekas/tools/modernpackage status --porcelain | grep -E 'compose')"` (exit 0).

---

## Phase 6: Whole-Doc Consistency Pass

Verify the finished doc against the design's style + traceability gates and the ~250–350-line
size target. No new content — tighten only what fails a check.

### Changes

**File**: `docs/containerization.md`
**Action**: modify (touch-ups only — fix any failing gate below; do not add new sections)

Touch-ups limited to: removing accidental admonition/front-matter syntax, trimming or expanding
prose to land in the 250–350-line band, and removing any URL not traceable to `research.md`.

### Verification
#### Automated
- [x] `just check` passes.

#### Manual
- [x] `wc -l < docs/containerization.md` → between 250 and 350 inclusive. If under 250, expand the
      thinnest subsection's prose (no new sources); if over 350, tighten prose (do not drop a
      required snippet or source).
- [x] `grep -c '> \[!' docs/containerization.md` → `0` (no GitHub admonitions).
- [x] `test "$(sed -n '1p' docs/containerization.md | cut -c1-3)" != '---'` (exit 0 — no YAML
      front-matter; line 1 is the H1).
- [x] `grep -c '^## ' docs/containerization.md` → `4` (the four Q4–Q7 sections, unchanged).
- [x] `grep -c '^#### ' docs/containerization.md` → `0` (still no H4 per-item template).
- [x] **Every URL traces to `research.md`** — run:
      ```bash
      grep -oE 'https?://[^ )]+' docs/containerization.md | sort -u | while read -r url; do
        grep -qF "$url" research.md || echo "UNTRACED: $url"
      done
      ```
      Expected output: empty (no `UNTRACED:` lines). Any printed URL must be replaced with a
      `research.md`-cited equivalent or removed.
- [x] `git -C /home/niekas/tools/modernpackage status --porcelain` shows only
      `docs/containerization.md` (added) and `docs/overview.md` (modified) — no other files
      touched (`design.md` What We're NOT Doing). Note: BACKLOG.md, Justfile, and lifecycle_state.yml
      show as modified from prior phases (1–5), not from Phase 6 itself, which made no changes.

---

## Testing Checkpoints (summary)

- **After Phase 1**: file exists; H1 + line-3 back-link conform; 4 empty `##` sections;
  `overview.md` row present; `just check` green.
- **After Phase 2**: Image Authoring complete — uv `COPY --from`, 3.14 base, uv env vars,
  `--no-editable`, Astral source cited.
- **After Phase 3**: Podman/Docker compatibility complete — `alias docker=podman`, rootless
  userns, `x-podman.*`, `DOCKER_HOST` socket, Red Hat/Podman sources cited.
- **After Phase 4**: Security & Runtime complete — non-root `USER`, scanners, `type=secret`,
  stdlib `HEALTHCHECK`, service items labeled; OWASP/Docker sources cited.
- **After Phase 5**: Multi-service stacks complete — compose fence with no `version:` key,
  `service_healthy`, `pg_isready`; Compose-spec source cited.
- **After Phase 6**: 250–350 lines; no admonitions/front-matter; every URL traces to
  `research.md`; only the two intended files changed.

Each phase appends only to its own `##` section (plus Phase 1's shared `overview.md` edit), so a
failed later phase leaves all earlier sections independently valid and shippable.
