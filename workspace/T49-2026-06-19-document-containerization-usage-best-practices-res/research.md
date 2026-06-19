# Research Findings

Two-part scope: (1) the repo's existing `docs/` conventions + tooling surface (answered from the repo); (2) current external best practices for OCI containerization with Podman/Docker-compatible config for `uv`-managed Python apps (answered from authoritative web sources). No `Containerfile`/`Dockerfile`/`compose` file exists in the repo today (`Glob` for `Containerfile Dockerfile docker-compose* compose*` → none).

---

## Q1: How are `docs/` files organized and formatted, and how do reference docs present guidance?

### Findings
- **Doc set** (`docs/`): `overview.md` (index), `specification.md`, `architecture.md` (1442 lines), `invocation.md` (606), `data_flows.md`, `backlog_formats.md`, `vision.md`, `persona.md`. Plus root `README.md` (user-facing) and `BACKLOG.md`.
- **H1 convention**: single H1 per doc, Title Case with em-dash subtitle `# modernpackage — <Subtitle>` (`docs/architecture.md:1`, `invocation.md:1`, `specification.md:1`, `overview.md:1`). Exceptions without the prefix/subtitle: `data_flows.md:1` (`# Data Flows`), `backlog_formats.md:1` (`# BACKLOG.md Format`), `README.md:1` (`# modernpackage`).
- **Intro paragraph**: `specification.md:1-3`, `overview.md:1-3`, `vision.md:1-4`, `backlog_formats.md:1-5` open with a 1–2 sentence intro before first H2. `architecture.md`, `invocation.md`, `persona.md`, `data_flows.md` jump from H1 to a bare back-link.
- **Back-link nav line**: five docs place a standalone `[overview.md](overview.md)` on line 3 (`architecture.md:3`, `invocation.md:3`, `backlog_formats.md:3`, `persona.md:3`, `data_flows.md:3`). `overview`, `specification`, `vision` lack it.
- **H2/H3/H4**: H2 Title Case (`invocation.md:5` `## Entry Points`). H4 used in `architecture.md` for per-function/per-constant entries with full signature in backticks as heading text (`architecture.md:304` `#### \`_verify_required_tools() -> None\``).
- **Code blocks**: language hints `bash` (CLI/shell), `python` (source snippets, architecture.md), `ini` (`pyproject.toml` excerpts, `architecture.md:1156,1334`), one `markdown` (`backlog_formats.md:39`). Bare ``` fences for terminal output (`invocation.md:39,67,83`) and ASCII diagrams (`specification.md:21-39`, `architecture.md:7-19`). Comments inside `bash` blocks annotate expected output with `#` (`README.md:8-35`, `invocation.md:435-523`).
- **Inline code**: backticks for identifiers, flags, paths, function names, env vars, TOML keys, type annotations — pervasive.
- **Tables** (only in `overview.md`, `backlog_formats.md`, `invocation.md`, `architecture.md`): docs index 2-col `File|Purpose` (`overview.md:21-28`); progress markers `Marker|Meaning` (`backlog_formats.md:13-17`); metadata defaults 5-col (`invocation.md:413-419`); git error patterns 2-col (`architecture.md:1100-1106`). Cells often use `**bold term**: description` lead-in.
- **Cross-references**: relative links (`overview.md:23` `[invocation.md](invocation.md)`, `:27` `[README.md](../README.md)`); anchor links with `§` notation in `overview.md:72,80` (`[specification.md § Known gaps & divergences](specification.md#known-gaps--divergences)`). `specification.md` cites code inline as parenthetical `` (`file:line`) `` not links (`specification.md:8,43,84,114`).
- **Reference-doc guidance style**:
  - `specification.md` — flat `##` sections + bullet lists, each item `**Term** (\`file:line\`): description` (`specification.md:14-17`).
  - `architecture.md` — rigid per-function template: H4 typed signature → `**Purpose**` → `**Parameters**`/`**Returns**`/`**Algorithm**` (numbered) → `**Error message**` (fenced) → `**Design rationale**` (bullets) → `Examples:` (`architecture.md:304-337`). Constants get H4 + `python` block + prose (`architecture.md:39-46`).
  - `invocation.md` — scenario-driven: `bash` invocation → prose → `**Output (stdout):**`/`**Output (stderr):**`/`**Exit code:**` labels → plain output fence (`invocation.md:214-233`).
- **Callouts**: no YAML front-matter, no GitHub `> [!NOTE]` admonitions. Bold inline callouts are the pattern: `**Important**:`, `**Note**:` as standalone bold-prefixed paragraphs (`invocation.md:87,132,257,383,580`; `README.md:248`). One `✅` checkmark (`architecture.md:1182`). `vision.md` uses stable `V<num> — …` H2 identifiers never renumbered (`vision.md:6,18,…`).

---

## Q2: How does the project define/run build, run, test workflows (Justfile, pyproject, uv)?

### Findings
- **Justfile** drives everything via `uv`. Recipes (`Justfile:1-78`): `lifecycle`, `vision`, `sync` (`uv sync`), `compile` (`uv lock`), `test *args` (`uv run pytest -n "$(nproc --ignore=1)"`), `test-e2e` (`uv run pytest -m e2e --no-cov`), `format`/`lint`/`typecheck` (ruff/ruff/mypy), `check-format`/`check-lint`/`check-complexity` (`--select C901`)/`check-typecheck`, `audit` (`uv run pip-audit --skip-editable`), `fix-lint`, `fix` (= `format fix-lint`), `check` (= check-format check-lint check-complexity check-typecheck test audit), `publish` (`rm -fr dist/*; uv build; uv publish`), `init`, `lock` (`uv lock --upgrade`).
- Most recipes declare `sync` as a prerequisite (e.g. `Justfile:14,20,23`), so the locked env is installed via `uv sync` before each task. `deadcode` recipe is commented out (`Justfile:44-45`).
- **pyproject.toml** is the single config hub (`pyproject.toml`): `requires-python = ">= 3.14"` (`:8`); no runtime `dependencies` (`:18`); console scripts `modernpackage`/`mp` → `modernpackage.main:main` (`:23-25`); `[dependency-groups].dev` = ruff, mypy, pip-audit, deadcode, pytest, pytest-cov, pytest-xdist, `vupi>=0.0.7` (`:27-37`).
- **pytest** (`:39-43`): `addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0 -m 'not e2e'"`; `e2e` marker for real external calls.
- **build-system** hatchling (`:45-54`); dynamic version from `modernpackage/__init__.py` (`:53-54`); build includes `**/*.py`, excludes `tests/**`.
- **ruff** (`:56-79`): line-length 88, single quotes, `select=["ALL"]` with a few ignores, mccabe `max-complexity = 8`, tests ignore `S101`+`D`.
- **mypy** (`:81-89`): strict, `python_version = "3.14"`.
- **uv private index** (`:97-99`): GitLab PyPI index named `gitlab`.
- **Invocation flow** documented in `overview.md:30-51`: developers run `just check` (primary gate), `just fix`, `just lock`, `just test`, etc. `uv.lock` is the single source of truth installed via `uv sync`.

---

## Q3: How is CI/CD configured (GitLab + GitHub)?

### Findings
- **GitLab** (`.gitlab-ci.yml`): base image `python:latest` (`:1`); `RUFF_CACHE_DIR` set inside project for caching (`:5-6`); `cache.paths: [.cache/pip]` (`:9-11`); `before_script` (`:13-17`): `pip install uv`, `uv tool install rust-just`, `export PATH="$HOME/.local/bin:$PATH"`, `just sync`; single `test` job runs `just check` (`:19-22`).
- **GitHub Actions** (`.github/workflows/check-modernpackage-on-python314.yml`): triggers on push/PR to `main` (`:6-10`); `permissions: contents: read` (`:12-13`); `runs-on: ubuntu-latest` (`:18`); steps: `actions/checkout@v3`, `actions/setup-python@v3` with `python-version: "3.14"` (`:21-25`); install step `pip install uv` + `uv tool install rust-just` + append `$HOME/.local/bin` to `$GITHUB_PATH` + `just sync` (`:26-31`); run step `just check` (`:32-34`).
- Both pipelines converge on the same gate: install uv → install just → `just sync` → `just check`. Only the GitHub workflow pins Python 3.14; GitLab uses `python:latest`.

---

## Q4: Current best practices for authoring container images for `uv`-managed Python apps

### Findings (external — sources cited inline)
- **Install uv**: `COPY --from=ghcr.io/astral-sh/uv:<pinned-version> /uv /uvx /bin/` is unanimously preferred over `pip install uv`. Astral ships distroless (binary-only, for `COPY --from`) and derived images (`ghcr.io/astral-sh/uv:python3.13-trixie-slim`, `-alpine`) usable as builder base. Source: [Astral uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/).
- **Base image (runtime)**: `python:3.x-slim(-trixie)` most recommended; Alpine discouraged for Python (musl/wheel issues — Hynek). Distroless (`gcr.io/distroless/cc`, includes glibc for C-extensions) for minimal attack surface (~23 MB vs ~75 MB slim — Josh Kasuboski, Mar 2025). Keep builder and runtime OS family/version matched to avoid glibc mismatch.
- **Multi-stage**: builder stage builds the `.venv`, runtime stage copies only `/app/.venv`; excludes build toolchain → smaller, more secure image. Runtime needs no `uv` if PATH-activated.
- **Layer caching (two-phase sync)**: phase 1 bind-mount `uv.lock`+`pyproject.toml`, `uv sync --locked --no-install-project` (deps only, cached until lockfile changes); phase 2 `COPY . /app` then `uv sync --locked` (project). Use `--mount=type=cache,target=/root/.cache/uv` (persists wheel cache across builds; needs BuildKit). Source: Astral docs.
- **Env vars**: `UV_COMPILE_BYTECODE=1` (precompile `.pyc`, faster startup), `UV_LINK_MODE=copy` (required with cache mounts — cache & workdir on different filesystems), `UV_PYTHON_DOWNLOADS=0`/`never` (use system Python).
- **Small/reproducible**: `--locked` (single project; asserts lock current) vs `--frozen` (skips check / workspaces); `--no-dev` (exclude dev group); `--no-editable` (self-contained venv — **required** for multi-stage so runtime needs no source). `.dockerignore` should include `.venv`, `.git`, `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache` (Astral explicitly: add `.venv` to `.dockerignore`).
- **venv activation**: `ENV PATH="/app/.venv/bin:$PATH"` is the production standard (no per-command overhead, no `uv` at runtime); `CMD ["uv", "run", "app"]` requires `uv` present and is dev-oriented. PATH activation is the only viable option for distroless.
- **Repo applicability note**: this project is a CLI with `requires-python >= 3.14` and a GitLab private uv index (`pyproject.toml:8,97-99`); a Containerfile would need uv configured with that index and a 3.14 base.

---

## Q5: Best practices for Podman specifically, kept Docker-compatible

### Findings (external)
- **Rootless**: container engine + containers run as unprivileged user via user namespaces; needs `/etc/subuid`+`/etc/subgid` ranges, `podman system migrate` after edits; storage in `~/.local/share/containers/`. UID-mapping modes (Red Hat blog): default (host UID→container root), `--userns=keep-id` (host UID preserved — best for mounted-source dev), `auto`/`nomap` (stronger isolation, files appear `nobody`). Source: [Red Hat — rootless userns modes](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes).
- **Gotchas**: ports <1024 need `net.ipv4.ip_unprivileged_port_start` sysctl; SELinux volume labels `:z` (shared) / `:Z` (private, single container); `:U` to chown volume to container UID. Default rootless network backend is **pasta** since Podman 5.0.
- **Docker CLI parity**: official docs literally say `alias docker=podman`. `podman build` (via Buildah) finds `Containerfile` first then `Dockerfile`; `podman buildx build` is an alias; default output OCI v1.0 (`--format docker` / `BUILDAH_FORMAT=docker` for Docker manifest). Source: [docs.podman.io](https://docs.podman.io/en/stable/markdown/podman.1.html).
- **Docker-API socket**: `systemctl --user enable --now podman.socket` exposes `$XDG_RUNTIME_DIR/podman/podman.sock`; point tools via `export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`; `loginctl enable-linger $USER` for reboot persistence.
- **Compose options**: `podman compose` is a thin wrapper delegating to an external provider (docker-compose preferred if installed, else podman-compose; override via `PODMAN_COMPOSE_PROVIDER`). `podman-compose` (Python) translates compose → `podman` CLI directly, no socket, rootless-first, subset of features, supports `x-podman.*` extensions. `docker compose` over the Podman socket = fuller spec coverage. Source: [Red Hat — Podman vs Docker Compose](https://www.redhat.com/en/blog/podman-compose-docker-compose).
- **Pods & Quadlets**: a pod shares net/IPC namespaces (containers talk over `localhost`). Quadlets = systemd unit files (`.container`/`.pod`/`.volume`/`.network`/`.build`/`.kube`) auto-generated into `.service` units (Podman 4.4+); replace deprecated `podman generate systemd`; rootless files in `~/.config/containers/systemd/`. Recommended over Compose for production/server deployment. Source: [podman-systemd.unit(5)](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html).
- **Keeping config Docker-compatible**: name build file `Containerfile` (Podman-preferred; modern Docker 23.0+ also accepts) or `Dockerfile` (universal); use OCI format (default both); stick to vendor-neutral Compose spec, isolate Podman-only options under ignored `x-podman.*`; fully-qualified image names (`docker.io/library/...`); set `unqualified-search-registries = ["docker.io"]` in `registries.conf`.

---

## Q6: Container security, runtime config, and local-dev ergonomics for a Python service

### Findings (external)
- **Non-root user**: `groupadd --system --gid 1001 appgroup && useradd --system --uid 1001 --gid appgroup --no-log-init --no-create-home appuser`, `COPY --chown=appuser:appgroup`, then `USER appuser` before `CMD`. Use explicit UID/GID (reproducibility), `--no-log-init` (avoid sparse `/var/log/lastlog`); keep executables root-owned. Sources: [Docker building best practices](https://docs.docker.com/build/building/best-practices/), [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html). On rootless Podman, align mounted-volume perms with `--userns=keep-id:uid=1001,gid=1001`, `podman unshare chown`, or `:U`.
- **Image scanning**: Trivy (vuln OS+language pkgs, secrets default; misconfig/license opt-in; SBOM CycloneDX/SPDX) `trivy image myapp:latest`; Grype (vuln-only, EPSS+CISA-KEV risk scoring, pairs with Syft) `grype myapp:latest`; Docker Scout (`docker scout cves`, `compare`, policy/VEX). Sources: [trivy.dev](https://trivy.dev/docs/latest/guide/target/container_image/), [anchore/grype](https://github.com/anchore/grype), [Docker Scout](https://docs.docker.com/scout/explore/analysis/).
- **Secrets**: never via `ARG`/`ENV` (persist in layers / `docker history`). Build-time: `RUN --mount=type=secret,id=...` + `docker build --secret`. Runtime: Compose `secrets:` element → mounted read-only at `/run/secrets/<name>`; app reads `*_FILE` path. `.env` for non-sensitive config only — gitignore `.env`, commit `.env.example`. Sources: [Docker build secrets](https://docs.docker.com/build/building/secrets/), [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).
- **Healthcheck**: `HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ...`; for Python with no extra binary use stdlib: `python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health',timeout=4); sys.exit(0)"`. `/health` endpoint should be lightweight, 200 ready / 503 on dependency down. Source: [OneUptime HEALTHCHECK](https://oneuptime.com/blog/post/2026-01-30-docker-health-check-best-practices/view).
- **Volumes**: bind-mount source for live reload (`type: bind, source: ./src, target: /app/src`, `:ro` if read-only); named volumes for persistent data (DB dirs). On SELinux/Podman append `:Z` (private) / `:z` (shared); never `:Z` on system dirs; `:z`/`:Z` only with short `-v` syntax. Source: [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
- **Networking**: publish ports, prefer `127.0.0.1:8000:8000` in dev (OWASP); on Compose user-defined networks the embedded DNS (`127.0.0.11`) resolves service names — use service name as hostname, never hard-code IPs; service-to-service uses the container port, not the published host port. Source: [Compose networking](https://docs.docker.com/compose/how-tos/networking/).

---

## Q7: Orchestrating multi-service local stacks (app + DB) portable across Podman & Docker

### Findings (external)
- **Compose-spec structure**: top-level `services` (required), `networks`, `volumes`, `secrets`. **Omit `version:`** — obsolete/ignored since Compose V2 (warns if present). Start file at `services:`. Source: [Compose Specification](https://compose-spec.github.io/compose-spec/spec.html).
- **Service-name networking**: on a shared user-defined network the app reaches the DB at hostname `db:5432` (`postgresql://appuser:...@db:5432/appdb`); no IPs, no legacy `links:`.
- **Running**: `docker compose up` (reference impl); `podman compose up` (wrapper → docker-compose if present else podman-compose); `podman-compose up` (standalone Python, direct podman calls). Portability rules: no `version:`; core spec only; isolate provider-specific options under ignored `x-*`/`x-podman:` keys; avoid `links:`/pre-V2 `extends:`; use `CMD-SHELL` for shell-syntax healthcheck tests, `CMD` array form otherwise.
- **Ordering — app waits for DB**: `depends_on` alone only waits for container start; use long-form `depends_on: {db: {condition: service_healthy}}` plus a `healthcheck:` on `db` (e.g. `test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]`, `interval/timeout/retries/start_period`). `start_period` (e.g. 30s) covers Postgres init scripts; `restart: true` (Compose V2.17+) restarts app if db turns unhealthy. Sources: [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/), Compose Specification.

---

## Cross-Cutting Observations
- **Tooling is uv+just centric end-to-end**: `pyproject.toml` is the only config hub; `Justfile` delegates to `uv run`; both CI systems do `pip install uv → uv tool install rust-just → just sync → just check`. Any container documentation added would mirror this (uv-driven build, `just`-invoked recipes).
- **Doc additions should follow observed conventions**: `# modernpackage — <Subtitle>` H1, line-3 `[overview.md](overview.md)` back-link, `**Term**:` bullet lead-ins, `bash`/`ini` fenced blocks with `#` output comments, 2-col purpose tables, `**Note**/**Important**` bold callouts (no admonition syntax), and the doc would be registered in the `overview.md:21-28` index table.
- **Podman/Docker compatibility theme** recurs across Q5–Q7: name the file `Containerfile`, OCI format, vendor-neutral Compose spec, `x-podman.*` for Podman-only knobs, `:Z`/`--userns=keep-id` for rootless SELinux/permission ergonomics.

## Open Areas
- No container artifacts exist in-repo (no `Containerfile`, `Dockerfile`, `compose.yml`, `.dockerignore`), so there is no existing in-repo containerization pattern to document — Q4–Q7 are answered entirely from external best-practice sources.
- The project's GitLab private uv index (`pyproject.toml:97-99`) and `requires-python >= 3.14` (`:8`) are repo-specific constraints any container guidance must accommodate; external sources use 3.12/3.13 examples and public PyPI, so version/index specifics are not externally prescribed.
- Whether the project intends app-style (long-running service) or CLI-style images is not determinable from the repo; the package is a CLI scaffolder (`overview.md:7`), so service-oriented practices (healthchecks, app+DB compose) are externally documented but not obviously applicable to this codebase's own runtime.
