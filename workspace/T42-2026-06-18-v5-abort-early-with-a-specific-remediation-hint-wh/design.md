# Design Discussion

## Current State

The scaffolding CLI already performs fail-fast preflight, but its remediation
hints are uneven — one precondition emits a generic, partly-wrong hint while the
others are specific. The machinery to "abort before any clone or filesystem
mutation" is already in place; the task is to close the hint-quality gap.

What exists today (`modernpackage/main.py`):

- A `PreflightCheck(label, run)` frozen dataclass registry, built per-call inside
  `_run_preflight_checks(target_path)` so the target-dir check can bind the path
  via closure (`main.py:484-491`, `561-579`).
- Four ordered checks: `package name valid` (a `lambda: None` no-op),
  `required tools on PATH (git, just, uv)`, `target directory available`,
  `template remote reachable` (`main.py:568-579`).
- The loop prints `Preflight checks:`, runs each verifier inside
  `try/except RuntimeError`, prints `[FAIL]` and re-raises on failure (so no
  later check runs), else prints `[ok]` (`main.py:580-587`).
- Checks run at `main.py:603`, strictly **before** the first mutating step,
  `Popen(['git', 'clone', ...])` at `main.py:605-610`. Guarantee is structural:
  the first failure propagates out of `init_new_package` before the clone.
- Per-precondition failure messages today:
  - Required tools: `f'required tool(s) not found on PATH: {missing} — install
    the missing tool(s) ... See https://github.com/casey/just#installation'`
    (`main.py:503-512`). **Generic**: always points at *just's* install page even
    when only `git` or `uv` is missing.
  - Target dir: `f'target directory already exists: {target_path} — choose a
    different package name or remove the existing directory'` (`main.py:515-522`).
    Specific. ✔
  - Template remote: friendly + raw two-part message, friendly text from
    `humanize_git_clone_error` (`main.py:525-558`). Specific. ✔
  - Package name: validated at argparse time by `validate_package_name`
    (`main.py:173-186`) → `ArgumentTypeError` → `SystemExit(2)`, never reaching
    the registry; the preflight slot is presentational only (`main.py:569`).
- Exit-status mapping: any preflight/clone/just-init `RuntimeError` → caught in
  `main` → exit `1` (`main.py:670-691`); name validation → exit `2`.

## Desired End State

Every precondition that can fail in preflight emits a **distinct, actionable**
remediation hint — including a per-tool install pointer when required tools are
missing — and the run still aborts before any clone/filesystem mutation.

Concretely:
- When `git` is missing the hint points at git's install docs; when `uv` is
  missing it points at uv's; when `just` is missing it points at just's. Multiple
  missing tools yield one hint line per missing tool.
- The other three preconditions keep their current specific behavior unchanged.
- All existing fail-fast guarantees (`Popen.call_count == 0` on preflight
  failure) remain.

Verify via:
- New unit tests on `_verify_required_tools` asserting the message contains the
  correct install URL for each individually-missing tool, and all three hints
  when all are missing (mirror `test_main.py:373-442`).
- Existing checklist/abort tests still pass unchanged
  (`test_main.py:584-709`, `1146-1229`).
- `just check` green.

## Patterns to Follow

- **Module-level mapping → friendly hint.** Model the per-tool hints on
  `_GIT_CLONE_ERROR_MESSAGES` (`main.py:19-52`) and its lookup helper
  `humanize_git_clone_error` (`main.py:68-74`): a module-level constant table
  plus a small pure helper. Use a `dict[str, str]` keyed by tool name (order is
  driven by `_REQUIRED_TOOLS`, `main.py:56`, not by the table).
- **Em-dash inline hint.** Keep the `... — <remediation>` suffix idiom used by
  required-tools, target-dir, and the validators (`main.py:508`, `520`,
  `177`, `203`, `211`).
- **Raise `RuntimeError` from verifiers; success is silent** (`main.py:503-558`).
  Do not change the raise/return contract.
- **Per-tool hint composition.** Build one hint fragment per missing tool so the
  message scales with `missing` rather than emitting a single catch-all URL.
- **Test seams.** Patch `modernpackage.main.shutil.which` with a `side_effect`
  returning `None` for the targeted tool; assert with
  `pytest.raises(RuntimeError, match=...)` and inspect `str(exc_info.value)` for
  multiple fragments (`test_main.py:373-423`).

Patterns to **NOT** follow / avoid:
- Do **not** promote the `package name valid` no-op into a real registry verifier
  that re-runs `validate_package_name`. Name is already enforced at parse time and
  aborts earlier (exit 2) than preflight; duplicating it would create two sources
  of truth and contradict "surgical changes" (CLAUDE.md §3) and "simplicity"
  (§2). Leave the presentational `[ok]` slot as-is.
- Do **not** introduce a friendly+raw two-part split for the tools message; that
  pattern fits opaque subprocess stderr (`main.py:547`, `557`), not a hint we
  author ourselves. A single inline message is the established shape here.

## Design Decisions

1. **Per-tool install hints via a module-level dict** — add
   `_TOOL_INSTALL_HINTS: dict[str, str]` mapping each of `git`, `just`, `uv` to
   its canonical install URL/instruction, near `_REQUIRED_TOOLS`
   (`main.py:56`). Chosen over inline conditionals because it matches the
   existing table-driven hint convention (`_GIT_CLONE_ERROR_MESSAGES`) and keeps
   `_verify_required_tools` readable.

2. **Message lists one hint per missing tool** — `_verify_required_tools`
   composes `f'required tool(s) not found on PATH: {", ".join(missing)}'` then
   appends, for each missing tool, a line like `'  - {tool}: {hint}'`. This makes
   the remediation specific to exactly what's absent rather than a single URL.

3. **Keep name validation at the parse layer** — the registry's
   `package name valid` slot stays a `lambda: None`. Rationale above; recorded
   here as an explicit judgment call since `task.md` lists "invalid name" among
   the preconditions. It *is* covered — just earlier in the pipeline, with its own
   specific `_explain_invalid_package_name` hints (`main.py:151-170`).

4. **No change to ordering, exit codes, or post-clone steps** — the clone,
   `just init`, and `just check` flow (`main.py:605-667`) is untouched. Only the
   text/structure of the required-tools failure changes.

5. **Hint URLs** — `git` → `https://git-scm.com/downloads`, `uv` →
   `https://docs.astral.sh/uv/getting-started/installation/`, `just` →
   `https://github.com/casey/just#installation` (preserving the existing just
   URL, `main.py:510`, `640`). Judgment call on the exact git/uv URLs; chosen as
   the official canonical install pages.

## What We're NOT Doing

- Not adding a package-name preflight verifier or moving name validation.
- Not changing check order, the checklist output format, or the
  `[ok]`/`[FAIL]` markers (`_format_check_line`, `main.py:497-500`).
- Not touching the template-remote probe, target-dir check, or
  `humanize_git_clone_error` table.
- Not altering exit-code mapping (`RuntimeError` → 1, `ArgumentTypeError` → 2).
- Not touching post-clone steps (`git clone`, `just init`, `just check`,
  `_write_package_metadata`).
- No new config flags, no configurability for hint text.

## Open Risks

- **URL accuracy/longevity.** The git/uv install URLs are authored, not derived;
  they could drift. Low impact (a stale link in an error string), and a single
  constant to update.
- **Message-shape coupling in tests.** Existing required-tools tests match on
  substrings like `'git'`, `'uv'` (`test_main.py:373-442`); switching to a
  multi-line message must keep those substrings present so current assertions
  don't regress. Verify the new format still satisfies them before adding the
  per-tool URL assertions.
- **Scope perception.** Because the abort-early machinery already exists, the
  net diff is small (one constant + one verifier body + tests). This is expected,
  not an oversight — the task "builds on the existing preflight sequence."
