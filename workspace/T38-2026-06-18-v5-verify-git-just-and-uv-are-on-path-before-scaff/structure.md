# Structure Outline

## Approach

Insert a `shutil.which`-based preflight check at the top of `init_new_package`
(before the first `git clone` `Popen`, `main.py:483`) that verifies `git`,
`just`, and `uv` resolve on `PATH`. Missing tools raise a single `RuntimeError`
naming all of them, funneled through `main`'s existing `except RuntimeError`
(`main.py:565`). No `main`, CLI, or message-table changes. The work is one
feature; it splits into two thin vertical slices so the first delivers a working
fail-fast check and the second upgrades the message quality — each fully tested.

---

## Phase 1: Preflight check that fails fast before any subprocess

Adds the production PATH check end-to-end: import, constant, helper, call site,
and unit tests. After this phase, a missing tool aborts scaffolding *before* any
`Popen` runs and before the clone directory is created — the core requirement.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `import shutil` — added to the stdlib import block (`main.py:3-6`).
- `_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')` — new module-level
  private constant (mirrors `test_e2e.py:28`).
- `_verify_required_tools() -> None` — new module-private helper. Iterates
  `_REQUIRED_TOOLS`, collects every tool where `shutil.which(tool) is None`, and
  raises `RuntimeError` naming the missing tool(s) if the collected list is
  non-empty; returns `None` when all present.
- `init_new_package(...)`: insert `_verify_required_tools()` as the first
  statement after `new_package_path = ...` and **before** the `git clone`
  `Popen` (`main.py:483`).

**Verify**: `just check` passes. Plus new unit tests in `tests/test_main.py`,
each patching the seam `modernpackage.main.shutil.which`:
- For each tool in `('git', 'just', 'uv')`: `which` returns `None` only for that
  tool → `pytest.raises(RuntimeError, match=<tool>)`, **and** assert
  `popen_mock.call_count == 0` (patch `modernpackage.main.Popen`) so no
  subprocess launches and no directory is created.
- All-present happy path: existing `Popen`-mocked tests at
  `test_main.py:281-310` still pass unchanged (`which` returns a truthy path).
- Run: `cd /home/niekas/tools/modernpackage && just test` → exit 0; confirm the
  new test names appear in pytest output (`just test -k verify_required_tools`
  selects them and reports `passed`).

---

## Phase 2: Report all missing tools with actionable install pointers

Upgrades the Phase 1 message from "names the missing tool(s)" to the project's
em-dash + install-pointer wording, listing *all* absent tools in one message so
the user fixes everything in one pass (Design Decision 4).

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_verify_required_tools()` message body: format the collected missing list
  using the established style (short phrase + em-dash + remedy), e.g.
  `"required tool(s) not found on PATH: git, uv — install the missing tool(s)
  before scaffolding. See https://github.com/casey/just#installation"`. No
  signature change from Phase 1.

**Verify**: `just check` passes. Plus new/extended unit tests:
- Multiple-missing test: `which` returns `None` for two tools (e.g. `git` and
  `uv`) → `pytest.raises(RuntimeError)` whose `str(exc_info.value)` contains
  **both** `'git'` and `'uv'` in the single message (assert via substring
  checks, mirroring `test_main.py:512-515`).
- Single-missing tests from Phase 1 still pass against the refined wording
  (`match=` patterns target the tool name, which the new message still
  contains).
- Run: `cd /home/niekas/tools/modernpackage && just test` → exit 0.

---

## Testing Checkpoints

After **Phase 1**, the following must be true (resume-safe state):
- `modernpackage/main.py` imports `shutil`, defines `_REQUIRED_TOOLS` and
  `_verify_required_tools`, and calls the helper first in `init_new_package`.
- `just test -k verify_required_tools` reports the per-tool fail-fast tests as
  `passed`; `popen_mock.call_count == 0` holds in each.
- Existing happy-path and `FileNotFoundError`-defense tests
  (`test_main.py:281-310, 325-340`) remain green — the `just init`
  `FileNotFoundError` handler (`main.py:515-520`) is untouched.

After **Phase 2**:
- A run with two missing tools produces one `RuntimeError` naming both, in the
  em-dash + install-pointer style.
- `just check` (format, lint, complexity ≤ 10, typecheck, test, audit) passes
  with no new `# noqa` (the helper launches no subprocess).
- No changes to `main`, `parse_args`, `_GIT_CLONE_ERROR_MESSAGES`, or the three
  existing subprocess call sites.

**Note on slicing**: the design is one small feature, so the slices are thin.
Phase 1 is independently valuable on its own (a correct fail-fast check that
names the offending tool); Phase 2 only improves message quality. If Phase 2 is
dropped, Phase 1 still satisfies the task's literal requirement ("naming the
missing tool"). No part of this design requires a horizontal-only layer.
