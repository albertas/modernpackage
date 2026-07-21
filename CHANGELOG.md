# Changelog

## 0.0.12
- T70: During package instantiation the CLI runs `just check` on the freshly scaffolded package. Add a step that runs the package's `just compile` (uv lock) and `just sync` (uv sync) targets first, so the lockfile is regenerated and dependencies are synced before `just check` runs. This avoids check failures caused by a stale lockfile after the package is renamed/modified during scaffolding.
