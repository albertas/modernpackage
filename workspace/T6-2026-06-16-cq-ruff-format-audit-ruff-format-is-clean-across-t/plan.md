# Plan

## Phase 1: Apply `ruff format` to the codebase

**Context.** `just check-format` runs `uv run ruff format --check modernpackage tests`.
It currently fails: `modernpackage/main.py` would be reformatted (the other 3
files are already clean). The required changes are purely mechanical:

- `parse_args()` — add a trailing comma after the final `add_argument` keyword
  argument (`type=check_alpha_numeric,`).
- The second `Popen(...)` call — expand the call so each argument sits on its
  own line, keeping the `# noqa: S603` / `# noqa: S607` comments attached to
  the correct lines.

**Implementation.**

1. Run `just format` (which runs `uv run ruff format modernpackage tests`) to
   apply the formatting. This rewrites `modernpackage/main.py` only.
   → verify: command exits 0 and reports `1 file reformatted`.

2. Manually confirm the `# noqa: S603` and `# noqa: S607` comments remain on
   the correct lines after reformatting, since `ruff format` moved them; the
   `S603` noqa belongs on the `Popen(` line and `S607` on the list-literal
   argument line.
   → verify: read the diff with `git diff modernpackage/main.py` and confirm
   only formatting changed and both noqa comments are still effective.

**Success criteria.**

- `just check-format` passes: `4 files already formatted`, exit code 0.
  → verify: run `just check-format`.
- `just check-lint` still passes (no new lint errors introduced by moved noqa
  comments).
  → verify: run `just check-lint`.
- The full `just check` suite passes.
  → verify: run `just check`.

**Note.** A pre-existing warning is emitted by ruff — `ANN101` in the
`pyproject.toml` ignore list has been removed upstream and has no effect. This
is unrelated to formatting and out of scope for this task; do not change it.
