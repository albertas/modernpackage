# modernpackage — Containerization

[overview.md](overview.md)

When scaffolded with the `--backend` flag, `modernpackage` generates a complete containerization 
setup for the FastAPI service. This document describes the generated `Containerfile`, `compose.yml`, 
and `.dockerignore` — all committed artifacts in the backend template. The containerization approach 
is Podman-primary (rootless safe) and Docker-compatible, with multi-stage builds, BuildKit layer 
caching, health checks targeting the readiness probe, and Docker Compose integration with async 
Alembic migrations.

## Image Authoring

### Installing uv

The recommended approach is to install `uv` via `COPY --from` rather than `pip install uv` to
avoid version drift. Copy both the `uv` binary and the `uvx` wrapper from the official Astral uv
image, pinning the uv version explicitly to prevent unexpected updates in rebuilds (per the
[Astral uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)).

### Base Image Selection

Use `python:3.x-slim` for size/compatibility balance. Alpine is discouraged (musl C library
causes wheel recompilation); distroless offers minimal attack surface but requires pre-compiled
deps. Align builder and runtime OS family (both glibc or both musl).

### Multi-Stage Builds

Separate dependency installation from runtime by using a builder stage that runs `uv sync` and
creates `.venv/`, then copy only the `.venv/` directory to the runtime stage. Use
`--no-editable` to prevent source code from being installed in the runtime venv.

### Layer Caching

Split `uv sync` into two phases: **Phase 1** bind-mounts `uv.lock`, `pyproject.toml`, and the
project's version source file (the `__init__.py` file defined in `pyproject.toml`'s
`[tool.hatch.version] path` key), runs `uv sync --locked --no-install-project`, and caches
until any bound file changes. When the project uses hatchling with a dynamic version,
the version-source file must be available during editable metadata generation; binding it to
Phase 1 allows dependency resolution to succeed without the full source tree. **Phase 2**
copies the full source and runs `uv sync --locked`. Use `--mount=type=cache,target=/root/.cache/uv`
with BuildKit to cache downloads/compilation across rebuilds. For the first workspace sync,
`--frozen` is recommended over `--locked`: it installs straight from the lockfile and skips the
freshness check (which can fail if a workspace member's manifest is missing); the examples below
use `--locked` to assert the lockfile is current.

`.dockerignore`: the official Astral example ships exactly one entry — `.venv`
(platform-specific, must be rebuilt in-image). Recommended additions for this project:
`.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache` (community conventions, not
part of the Astral baseline). Note: Version-source files (e.g., `modernpackage/__init__.py`)
and `README.md` are **not** excluded — they are deliberately available for bind-mounting during
Phase 1 dependency installation.

### Build Environment Variables

Set in the builder stage:

- `UV_COMPILE_BYTECODE=1`: pre-compile bytecode for faster startup.
- `UV_LINK_MODE=copy`: copy packages (not symlink) for portability when copying `.venv` to runtime.
- `UV_PYTHON_DOWNLOADS=0`: use the base image's Python, disable automatic downloads.

### venv Activation

Prepend the venv `bin` directory to `PATH` at runtime:

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```

This is the production standard and the only viable option for distroless images. Python scripts
and entry points are invoked directly without manual venv activation.

### Example Containerfile

The following annotated example illustrates a complete, modern build pipeline for a `uv`-managed
Python project using a Python 3.14 base image:

```dockerfile
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
# phase 1: deps only — cached until uv.lock / pyproject.toml / version-source change
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=modernpackage/__init__.py,target=modernpackage/__init__.py \
    --mount=type=bind,source=README.md,target=README.md \
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
```

**Note**: The phase 1 RUN command binds three files beyond the core lockfile and manifest:
- `modernpackage/__init__.py` — the dynamic-version source file (rewritten to `<module>/__init__.py`
  by `just init` during scaffolding). Hatchling reads this during editable metadata generation.
- `README.md` — listed in `pyproject.toml:readme`, read by hatchling for the long-description
  metadata field. Both files exist in the build context (the package root) and are available for
  bind-mounting before Phase 2's `COPY . /app`. This approach avoids dependency-layer cache
  invalidation while still building editable metadata correctly.

**Note**: Confirm a `python:3.14-slim` (and matching `ghcr.io/astral-sh/uv:python3.14-*`) tag
exists in the registry before using it; if unavailable, pin a digest or use the nearest
supported tag and treat 3.14 as a placeholder.

**Note**: This project resolves dependencies from a private GitLab uv index named `gitlab`
(`pyproject.toml`). A build that runs `uv sync` against it needs index credentials passed as a
build secret — never an `ARG`/`ENV` token. See [§ Security & Runtime](#security--runtime).

## Podman Usage & Docker Compatibility

### Rootless Containers

Rootless runs Podman and containers as unprivileged user via user namespaces. Requires
`/etc/subuid`/`/etc/subgid` ranges and `podman system migrate`. Provides stronger isolation and
is the recommended default.

UID-mapping modes (per [Red Hat rootless userns modes](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes)):

- **Default**: host UID → container root (UID 0).
- **`--userns=keep-id`**: preserve host UID in container (ideal for mounted-source dev).
- **`auto`/`nomap`**: stronger isolation, unmapped files appear as `nobody`.

SELinux volume labels: `:z` (shared), `:Z` (private), `:U` (chown to container UID, Podman 4.0+).

Default rootless network backend (pasta since Podman 5.0) needs no `net_admin`. Port binding
below 1024 requires lowering `net.ipv4.ip_unprivileged_port_start` on the host.

### Docker CLI Parity

Podman provides drop-in CLI compatibility with Docker via `alias docker=podman`. The `podman
build` command resolves `Containerfile` before `Dockerfile`, defaulting to OCI v1.0 output format.
To produce Docker-compatible manifests, use `--format docker` or set `BUILDAH_FORMAT=docker`
(per [docs.podman.io](https://docs.podman.io/en/stable/markdown/podman.1.html)).

Example commands demonstrating Docker compatibility:

```bash
alias docker=podman                       # drop-in CLI parity (official Podman guidance)
podman build -t modernpackage:dev .       # resolves Containerfile, then Dockerfile
podman run --userns=keep-id -v "$PWD/src:/app/src:Z" modernpackage:dev  # rootless dev mount
```

### Docker-API Socket

Tools that speak the Docker API can work with Podman by pointing at its socket:

```bash
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
loginctl enable-linger "$USER"            # persist socket across reboots
```

### Compose Providers

Podman offers three ways to run Compose files:

- **`podman compose`** — a thin wrapper that delegates to an external provider (prefers
  docker-compose if installed, otherwise falls back to podman-compose; override via
  `PODMAN_COMPOSE_PROVIDER`).
- **`podman-compose`** — a standalone Python implementation that translates Compose specs
  directly to `podman` CLI calls, with rootless-first design and support for `x-podman.*`
  extensions (per [Red Hat Podman vs Docker Compose](https://www.redhat.com/en/blog/podman-compose-docker-compose)).
- **`docker compose` over the Podman socket** — fuller Compose spec coverage when the Docker
  API socket is exposed (see Docker-API Socket above).

Quadlet `.container` units (Podman 4.4+) are a systemd-native alternative for running
containers, but they are not a Compose drop-in and are out of scope for this
Compose-portability reference.

### Keeping Config Docker-Compatible

To maintain compatibility across Docker and Podman tooling, follow these conventions:

- Name the build file `Containerfile` (Podman-preferred, though `Dockerfile` is also read).
- Output OCI v1.0 format by default; use `--format docker` when Docker manifests are required.
- Use the vendor-neutral Compose Specification (no `version:` key; it's deprecated since Compose V2).
- Isolate Podman-only knobs under `x-podman.*` keys in Compose files (they are ignored by Docker
  tooling).
- Use fully-qualified image names (e.g., `docker.io/library/python:3.14-slim`) to avoid ambiguity
  about which registry to use.

## Security & Runtime

### Non-Root User

Running containers as root increases the blast radius of container breakouts. Create an explicit
system user with a fixed UID/GID to reduce this risk (per [Docker building best
practices](https://docs.docker.com/build/building/best-practices/) and [OWASP Docker Security
Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)):

```dockerfile
# Non-root: explicit UID/GID, no home, no lastlog bloat
RUN groupadd --system --gid 1001 appgroup \
 && useradd --system --uid 1001 --gid appgroup --no-log-init --no-create-home appuser
COPY --chown=appuser:appgroup . /app
USER appuser                      # drop privileges before CMD
```

Use `--no-log-init` to avoid creating a sparse `/var/log/lastlog` file, and keep executables
root-owned while non-executable files (config, data) are owned by the app user.

When using rootless Podman, align volume permissions with the mapped UID: either use
`--userns=keep-id:uid=1001,gid=1001` or fix ownership via `podman unshare chown` before
running.

### Image Scanning

Scan for vulnerabilities after building:

- **Trivy** ([trivy.dev](https://trivy.dev/)): scans OS + language packages, detects secrets.
- **Grype** ([anchore/grype](https://github.com/anchore/grype)): scores by EPSS risk/CISA KEV.
- **Docker Scout** ([docs.docker.com/scout](https://docs.docker.com/scout/)): tracks changes
  across versions, policy support.

Integrate into CI/CD to block critical vulnerabilities.

### Secrets

**Important**: never pass secrets via `ARG` or `ENV` — they persist in layer history accessible
via `docker history` and `docker inspect`.

**Build-time secrets** — pass credentials needed during the build (e.g., GitLab private index
tokens) via `RUN --mount=type=secret` and `docker build --secret` (per [Docker build
secrets](https://docs.docker.com/build/building/secrets/)):

```dockerfile
# Build secret for the private GitLab uv index — never an ARG/ENV token
RUN --mount=type=secret,id=uv_index_token \
    UV_INDEX_GITLAB_PASSWORD="$(cat /run/secrets/uv_index_token)" \
    uv sync --locked --no-dev
# build with:  podman build --secret id=uv_index_token,src=./gitlab_token .
```

**Runtime secrets** — use Compose `secrets:` to mount configuration files read-only at
`/run/secrets/<name>` (per [Compose
secrets](https://docs.docker.com/compose/how-tos/use-secrets/)); applications can also read
`<VAR>_FILE` environment variables pointing to secret file paths.

For non-sensitive configuration, use `.env` files and `.env.example` (commit the example, ignore
the actual file).

### Healthchecks

`HEALTHCHECK` tells orchestrators if the container is ready (for the upcoming service backend).
Use stdlib probes (per [OneUptime best
practices](https://oneuptime.com/blog/post/2026-01-30-docker-health-check-best-practices/view)):

```dockerfile
# Stdlib healthcheck — no curl/wget needed
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health',timeout=4); sys.exit(0)"
```

`/health` returns 200 when ready, 503 when dependencies are down. `start-period` covers init
without marking failed probes unhealthy. `--start-interval` (Engine 25+) sets a faster probe
cadence during the start period. The probe command's exit code drives the state: `0` = healthy,
`1` = unhealthy, `2` = reserved (do not use).

### Volumes & Networking

**Volumes** persist data (e.g., database files); bind-mount source for live reload using `:ro`
(read-only) and `:Z` (SELinux private label).

**Networking** — services communicate by hostname via embedded DNS. For development, bind
ports to `127.0.0.1` only (OWASP, per [Compose
networking](https://docs.docker.com/compose/how-tos/networking/)).

## Local Multi-Service Stacks

### Compose File Structure

Compose files define multi-container apps using the vendor-neutral [Compose
Specification](https://compose-spec.github.io/compose-spec/spec.html). Top-level `services`
block is required; optional: `networks`, `volumes`, `secrets`. **Important**: omit `version:` —
it is deprecated since Compose V2.
The canonical Compose Specification filename is `compose.yaml`; `compose.yml` is also
recognized by Compose tooling (the examples in this document use `compose.yml`).

### Service Networking

Services communicate by name via embedded DNS (e.g., `db:5432` reaches Postgres). Use container
port for service-to-service communication, not the published host port.

### Running the Stack

```bash
docker compose up       # reference implementation
podman compose up       # wrapper (docker-compose if present, else podman-compose)
podman-compose up       # standalone Python implementation
```

For portability: omit `version:`, use core spec, isolate Podman-specific options under
`x-podman.*`, use `CMD-SHELL` for shell-syntax healthcheck tests.

### Startup Ordering

Use long-form `depends_on` with `condition: service_healthy` and a `healthcheck:` on the
dependency to wait for readiness (per [Compose startup
order](https://docs.docker.com/compose/how-tos/startup-order/)). For one-shot init/migration
containers, use `condition: service_completed_successfully` instead, which waits for the
dependency to run to completion (exit 0) rather than to become healthy.

```yaml
depends_on:
  db:
    condition: service_healthy
```

### Example: App + Postgres Stack

The following annotated Compose file demonstrates a complete multi-service stack with proper
startup ordering and health checks:

```yaml
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
```
