# Changelog

## 0.0.12
- T70: During package instantiation the CLI runs `just check` on the freshly scaffolded package. Add a step that runs the package's `just compile` (uv lock) and `just sync` (uv sync) targets first, so the lockfile is regenerated and dependencies are synced before `just check` runs. This avoids check failures caused by a stale lockfile after the package is renamed/modified during scaffolding.
- T71: When the scaffolder instantiates a new package, the operational/process artifacts — the `errors`, `issues`, and `workspace` directories plus the `lifecycle_state.yml` and `metrics.yml` files — must not be carried into the generated package. Extend the end-to-end test that inspects a freshly scaffolded package so it asserts these directories and files are absent, since they are currently still observed in newly created packages.
