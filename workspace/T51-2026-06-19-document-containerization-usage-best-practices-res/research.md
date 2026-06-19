# Research Findings

Repository: `modernpackage` — a self-replicating CLI scaffolder for modern uv-managed Python
packages. Q1–Q2 answered from the repo; Q3–Q6 answered from external 2026 sources (cited inline).

---

## Q1: How are `docs/` pages structured/cross-referenced, and do container artifacts already exist?

### Findings — docs structure & conventions
- `docs/` holds 9 markdown files: `overview.md`, `architecture.md`, `specification.md`,
  `invocation.md`, `data_flows.md`, `backlog_formats.md`, `persona.md`, `vision.md`,
  `containerization.md` (`docs/` listing).
- **Index/hub page**: `docs/overview.md:1` titled `# modernpackage — Documentation Index`. It
  carries a "Documentation Files" table (`docs/overview.md:21-29`) mapping each file → bold
  purpose summary, e.g. `containerization.md` row at `docs/overview.md:27`.
- **Back-link convention**: every non-index page opens with a bare link back to the hub on line 3,
  e.g. `docs/backlog_formats.md:3` `[overview.md](overview.md)` and `docs/containerization.md:3`
  `[overview.md](overview.md)`. Links are relative filenames (same dir); README/BACKLOG use `../`.
- **Heading style**: single `#` H1 of form `# modernpackage — <Topic>`; `##` for major sections,
  `###` for subsections (see `docs/containerization.md` H2/H3 nesting).
- **Tables**: GitHub pipe tables used for enumerations (`docs/overview.md:21`,
  `docs/backlog_formats.md:13-17` progress-marker table).
- **Tone**: declarative, present-tense, descriptive ("`modernpackage` is a standalone
  package…", `docs/overview.md:7`). Bold lead-ins on bullet lists (`docs/overview.md:12-17`).
- **Code-block style**: fenced blocks with language tags — `markdown`
  (`docs/backlog_formats.md:39`), `dockerfile`, `bash`, `yaml`, `toml` (throughout
  `docs/containerization.md`). Inline code in backticks for filenames/commands.

### Findings — container artifacts
- **No build artifacts exist**: no `Containerfile`, `Dockerfile`, `compose.yml`,
  `docker-compose.yml`, or `.dockerignore` anywhere outside `.venv`/`workspace` (find sweep
  returned nothing).
- **A containerization document already exists**: `docs/containerization.md` (13 KB, modified
  2026-06-19) is a complete forward-looking reference. It explicitly states the repo "ships no
  container artifacts today" (`docs/containerization.md:5-9`) and that all examples are
  "illustrative templates, not committed build files." It already covers image authoring, Podman
  compatibility, security, and multi-service stacks (matching Q3–Q6 scope).
- **CI present, not container-based for the app**: `.gitlab-ci.yml` uses `image: python:latest`
  + `pip install uv` + `uv tool install rust-just` + `just check`. `.github/` also exists.

---

## Q2: Toolchain/configuration a container build must accommodate

### Findings
- **Python version**: `requires-python = ">= 3.14"` (`pyproject.toml:8`); mypy
  `python_version = "3.14"` (`pyproject.toml:83`); classifiers list 3.14 only
  (`pyproject.toml:15`). A base image must supply Python ≥ 3.14.
- **Dependency management via uv**: `uv.lock` present (177 KB). Runtime `dependencies = []`
  (`pyproject.toml:18`) — the package has no third-party runtime deps. Dev tooling under
  `[dependency-groups] dev` (`pyproject.toml:27-37`): `ruff, mypy, pip-audit, deadcode, pytest,
  pytest-cov, pytest-xdist, vupi>=0.0.7`.
- **Build backend**: hatchling (`pyproject.toml:45-47`); dynamic version read from
  `modernpackage/__init__.py` (`pyproject.toml:53-54`); build includes `**/*.py`, excludes
  `tests/**` (`pyproject.toml:49-51`).
- **Entry points / scripts**: `modernpackage` and `mp` → `modernpackage.main:main`
  (`pyproject.toml:23-25`). These become the container's runnable commands.
- **Private/authenticated package index** (`pyproject.toml:97-99`):
  ```toml
  [[tool.uv.index]]
  name = "gitlab"
  url = "https://gitlab.com/api/v4/projects/niekas%2Fpackages/packages/pypi/simple"
  ```
  Index name is `gitlab` → uv credential env vars would be `UV_INDEX_GITLAB_USERNAME` /
  `UV_INDEX_GITLAB_PASSWORD` (GitLab token username is literally `__token__`). No
  `authenticate = "always"` is set. `vupi` (the only non-PyPI-obvious dep) is resolved via this
  index. A build running `uv sync` against it needs index credentials.
- **Justfile recipes** (all gated on `sync:` → `uv sync`, `Justfile:8-9`): `lifecycle`, `vision`,
  `sync`, `compile` (`uv lock`), `test` (`uv run pytest -n nproc-1`), `test-e2e`, `format`,
  `lint`, `typecheck`, `check-format/-lint/-complexity/-typecheck`, `audit` (`pip-audit
  --skip-editable`), `fix-lint`, `fix`, `check` (aggregate gate, `Justfile:53`), `publish`
  (`uv build` + `uv publish`), `init`, `lock` (`uv lock --upgrade`). A dev/CI container needs
  `uv` and `just` on PATH (matches `.gitlab-ci.yml` `before_script`).
- `just check` chains: check-format, check-lint, check-complexity, check-typecheck, test, audit
  (`Justfile:53`). Coverage gate 95% (`pyproject.toml:40`); e2e excluded by default
  (`-m 'not e2e'`, `pyproject.toml:40`).

---

## Q3: Authoring container images for a uv-managed Python project (2026 external)

### Findings (source: docs.astral.sh/uv "Using uv in Docker", astral-sh/uv-docker-example)
- **Installing/pinning uv**: recommended method is distroless binary copy, NOT `pip install uv`:
  `COPY --from=ghcr.io/astral-sh/uv:0.x.y /uv /uvx /bin/`. Pin levels: mutable `:latest` (not for
  prod) → semver tag (recommended) → `@sha256:` digest (max reproducibility). Astral also ships
  derived `FROM` images (e.g. `ghcr.io/astral-sh/uv:python3.12-trixie-slim`).
- **Multi-stage**: builder stage (uv-derived image) runs `uv sync` into `/app/.venv`; final
  runtime stage is clean `python:3.x-slim` with **no uv present**; only `/app` copied via
  `COPY --from=builder`. Runtime CMD invokes the venv binary directly (uv absent).
- **Layer caching — two-sync pattern**:
  1. `RUN --mount=type=cache,target=/root/.cache/uv --mount=type=bind,source=uv.lock,... \
     --mount=type=bind,source=pyproject.toml,... uv sync --locked --no-install-project` —
     installs only deps; cached until lock/manifest change.
  2. `COPY . /app` then `uv sync --locked` — installs the project (fast).
  Cache mount on every `RUN uv`; bind mounts avoid copying manifests into the layer.
- **`--frozen` vs `--locked`**: `--locked` asserts lockfile is current (fails if a member manifest
  is missing); `--frozen` skips the freshness check — docs recommend `--frozen` for the first
  workspace sync. `--no-install-workspace` is the workspace variant of `--no-install-project`.
- **`.dockerignore`**: official example contains exactly one entry — `.venv` (platform-specific,
  must be rebuilt in-image). Community guides add `.git`, `__pycache__`, `*.pyc` (not official).
- **Build-time env vars** (builder stage): `UV_COMPILE_BYTECODE=1` (precompile `.pyc`),
  `UV_LINK_MODE=copy` (required with cache mounts — hardlink fails across filesystems),
  `UV_PYTHON_DOWNLOADS=0` (use base-image Python), `UV_NO_DEV=1`/`--no-dev` (exclude dev group).
  `UV_FROZEN` and `UV_PROJECT_ENVIRONMENT` (point venv at e.g. `/usr/local` to skip activation)
  are available alternatives.
- **venv activation at runtime**: primary method is `ENV PATH="/app/.venv/bin:$PATH"` — required
  in multistage (uv absent). Single-stage dev images may use `uv run …` instead.
- **Note**: `docs/containerization.md:66-93` already encodes this exact pipeline (pinned
  `ghcr.io/astral-sh/uv:0.5`, two-phase sync, cache+bind mounts, `--no-editable`, PATH activation)
  with a 3.14-tag-availability caveat at `docs/containerization.md:95-97`.

---

## Q4: Running with Podman while staying Docker-compatible (2026 external)

### Findings (source: docs.podman.io, Red Hat blogs)
- **Rootless UID mapping**: host UID (e.g. 1000) → container UID 0; container UIDs 1–65535 drawn
  from `/etc/subuid`/`/etc/subgid` ranges (≥65536 recommended; apply with `podman system
  migrate`). Files written to volumes appear on host as `start_uid + container_uid - 1`, often a
  high subordinate UID shown as `nobody` — expected user-namespace behavior (differs from Docker).
- **`--userns=keep-id`**: maps the running user's UID:GID 1:1 into the container so bind-mounted
  host files keep ownership; `keep-id:uid=N,gid=N` overrides; settable via `containers.conf`
  `[containers] userns="keep-id"`. Modes: default / keep-id / auto / nomap. `podman unshare chown`
  fixes volume ownership inside the namespace.
- **SELinux volume labels**: `:z` = shared label (multiple containers); `:Z` = private/unshared
  (single container); `:U` = chown to mapped UID (separate from SELinux). Do NOT relabel system
  dirs; relabel walks every inode (slow on large trees); use `--security-opt label=disable` for
  paths that must not be relabeled.
- **Docker CLI/manifest parity**: `alias docker=podman` is official guidance; `podman-docker`
  package installs a `/usr/bin/docker` shim. `podman build` defaults to OCI v1.0; use
  `--format docker` (or `BUILDAH_FORMAT=docker`) for Docker v2s2 manifests (drops annotations).
- **Docker-API socket**: `systemctl --user enable --now podman.socket` exposes a Docker v1.40
  compat REST API at `$XDG_RUNTIME_DIR/podman/podman.sock`
  (`/run/user/$UID/podman/podman.sock`). Point Docker-aware tools via
  `export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`; `loginctl enable-linger $USER`
  persists it. Do not expose over TCP without mTLS.
- **Compose providers**: `podman compose` is a thin dispatcher that prefers `docker-compose`
  (reference impl) then falls back to `podman-compose`; override via `PODMAN_COMPOSE_PROVIDER`
  env or `containers.conf` `[engine] compose_providers`. `podman-compose` (standalone Python)
  translates YAML directly to `podman` CLI — no socket needed, rootless-first, but lags the spec.
- **Containerfile vs Dockerfile**: identical syntax; `podman build` resolves `Containerfile`
  first, then `Dockerfile`; extensioned names need explicit `-f`. Buildah ignores the
  `# syntax=` BuildKit directive.
- **Note**: `docs/containerization.md:103-170` already documents keep-id, `:z/:Z/:U`,
  `--format docker`, the socket/`DOCKER_HOST`, the three compose paths, and `x-podman.*`
  isolation.

---

## Q5: Container security best practices (2026 external)

### Findings (source: Docker/Podman docs, uv auth docs, Trivy/Grype docs)
- **Non-root user**: absent `USER`, container runs as UID 0 (CIS Docker 4.1 / OWASP Rule #2
  require a non-root user). Create a system user, `COPY --chown`, then `USER 1001:1001` (specify
  by UID/GID; do privileged setup before the switch). Rootless engine (Podman default) and a
  non-root in-container user are distinct, complementary layers.
- **Build-time secrets**: never `ARG`/`ENV` — values persist in `docker history`/image metadata
  (Docker `SecretsUsedInArgOrEnv` check). Use BuildKit `RUN --mount=type=secret,id=…` (tmpfs at
  `/run/secrets/<id>`, never layered/cached). Podman `podman build` supports identical syntax via
  `--secret=id=…,src=…|env=…`; secrets excluded from `commit`/`export`.
- **Private index credentials for uv**: env-var convention `UV_INDEX_<NAME>_USERNAME` /
  `UV_INDEX_<NAME>_PASSWORD` where `<NAME>` is the uppercased index name (here `gitlab` →
  `UV_INDEX_GITLAB_*`); GitLab username is `__token__`. Three documented patterns: (A) secret
  mount exposing the password env var; (B) secret mount of a full authenticated
  `UV_EXTRA_INDEX_URL`; (C) `~/.netrc` mounted as a secret (`NETRC=` override). uv issue #11740
  (still open) notes ARG/ENV is "not recommended" and an official Docker-build guide is pending.
- **Vulnerability scanning**: Trivy (scans OS + lang packages, natively reads `uv.lock`,
  `--ignore-unfixed`, SARIF/SBOM output, `aquasecurity/trivy-action`); Grype + Syft (SBOM-driven,
  `--fail-on high`); Docker Scout (`docker scout cves`, policy incl. non-root). Python layer:
  `pip-audit` (OSV/PyPI advisories — already a dev dep + `just audit`) and the new preview
  `uv audit` (announced 2026-06-08). Documented cadence: scan every PR with
  `--exit-code 1 --severity CRITICAL,HIGH --ignore-unfixed` + nightly rescans; slim/alpine bases
  cut OS CVEs vs full Debian.
- **Note**: `docs/containerization.md:172-254` already documents non-root `useradd --no-log-init`,
  Trivy/Grype/Scout, the `--mount=type=secret` GitLab-token pattern (`UV_INDEX_GITLAB_PASSWORD`),
  Compose `secrets:`/`<VAR>_FILE`, and `.env`/`.env.example`.

---

## Q6: Healthchecks/readiness and portable Compose stacks (2026 external)

### Findings (source: compose-spec.io, docs.docker.com)
- **HEALTHCHECK instruction**: `HEALTHCHECK [OPTIONS] CMD <cmd>` or `HEALTHCHECK NONE`. Options:
  `--interval` (30s), `--timeout` (30s), `--start-period` (0s; failures don't count),
  `--start-interval` (5s, Engine 25+), `--retries` (3). Exit 0=healthy, 1=unhealthy, 2=reserved.
  States: starting → healthy/unhealthy. Probe `127.0.0.1`, keep lightweight, timeout < interval,
  use exec/JSON form for distroless (no `/bin/sh`). Docker does NOT auto-restart unhealthy
  containers without a restart policy.
- **Liveness vs readiness**: Docker has ONE `HEALTHCHECK` combining both; Kubernetes splits into
  liveness/readiness/startup probes and ignores `HEALTHCHECK`. In Compose the single healthcheck
  gates `depends_on: condition: service_healthy` (readiness role).
- **Compose Specification**: top-level `version:` is obsolete (Compose v2.27+ warns and ignores
  it). Spec maintained at compose-spec.io / github.com/compose-spec/compose-spec; canonical
  filename `compose.yaml`. Top-level keys: `services` (required), `networks`, `volumes`,
  `configs`, `secrets`.
- **Networking**: Compose auto-creates one user-defined bridge network
  `<project>_default`; services reach each other by service name via embedded DNS (`db:5432`).
  DNS works only on user-defined networks, not the legacy `docker0` bridge. `expose` = document
  inter-service ports (not published to host); `ports` = publish host↔container (`"127.0.0.1:8001:8001"`
  for loopback-only).
- **Startup ordering**: `depends_on` waits only for "running", not readiness. Long form
  `condition:` supports `service_started`, `service_healthy` (needs a `healthcheck:` on the dep),
  `service_completed_successfully` (init/migration containers). Extra fields `restart: true`
  (2.17+), `required: false` (2.20+).
- **Podman + Compose**: `podman compose` dispatches to `docker-compose` (fullest spec coverage)
  or `podman-compose`. Known gap: `podman-compose`'s `condition: service_healthy` has open bugs
  (issues #866/#1119/#1183); it historically creates pods not bridge networks (declare named
  networks explicitly). Quadlet (`.container` units, Podman 4.4+) is the systemd alternative but
  not a Compose drop-in.
- **Note**: `docs/containerization.md:233-328` already documents the stdlib `HEALTHCHECK`,
  version-less Compose, service-name DNS, long-form `depends_on: service_healthy`, named volumes,
  `CMD-SHELL`, and a full app+Postgres example.

---

## Cross-Cutting Observations
- **A complete `docs/containerization.md` already exists** (modified today, 2026-06-19) and its
  content closely matches every external best-practice area in Q3–Q6, while correctly stating no
  container artifacts are committed. Any new work overlaps an existing document rather than a
  blank slate.
- **uv + just are the toolchain spine**: every Justfile recipe runs through `uv sync`/`uv run`;
  CI installs uv then `just check`. A container mirroring CI needs both binaries on PATH.
- **The Python 3.14 floor is the main build risk**: external uv/Docker examples pin 3.12; a 3.14
  base/`ghcr.io/astral-sh/uv:python3.14-*` tag must be verified (already flagged at
  `docs/containerization.md:95-97`).
- **Private GitLab index is the one auth touchpoint** for any `uv sync` in a build; index name
  `gitlab` fixes the credential env-var names to `UV_INDEX_GITLAB_USERNAME/PASSWORD`.
- **Doc conventions to match**: `# modernpackage — <Topic>` H1, line-3 `[overview.md](overview.md)`
  back-link, pipe tables, language-tagged fences, present-tense descriptive tone, and an entry in
  the `docs/overview.md` table (already present at line 27).

## Open Areas
- uv's official Docker-build guidance for private-index auth is still pending upstream (issue
  #11740 open); current patterns are community-documented, not Astral-official.
- `ghcr.io/astral-sh/uv:python3.14-*` and `python:3.14-slim` tag availability is unverified from
  the registry (noted, not confirmed, in the existing doc).
- `vupi>=0.0.7` resolution source (PyPI vs the `gitlab` index) was not traced in `uv.lock`.
