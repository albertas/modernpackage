# Structure Outline

## Approach

The fail-fast preflight machinery already exists; the only gap is the
required-tools hint, which always points at *just's* install page regardless of
which tool is missing. Add a module-level `_TOOL_INSTALL_HINTS` table (modeled on
`_GIT_CLONE_ERROR_MESSAGES`) mapping each required tool to its canonical install
URL, then rewrite `_verify_required_tools` to emit one hint line per missing
tool. Nothing else (ordering, exit codes, other verifiers, post-clone steps)
changes.

This task is naturally **one vertical slice** — a single verifier crossing only
the CLI/preflight layer (no DB/API/UI exist here). It is split below into a
foundation phase (behavior + table) and a hardening phase (per-tool URL coverage
+ regression guard) so each has its own checkpoint and Phase 1 stands alone if
Phase 2 is deferred.

---

## Phase 1: Per-tool install hints in `_verify_required_tools`

Add the install-hint table and rewrite the verifier so the failure message lists
one remediation line per missing tool, while preserving the existing substrings
(`git`, `uv`, etc.) so current tests don't regress. End-to-end: missing-tool
preflight still raises `RuntimeError`, still aborts before any `Popen` clone, and
the abort message now names the right install page for each absent tool.

**Files**: `modernpackage/main.py`

**Key changes**:
- `_TOOL_INSTALL_HINTS: dict[str, str]` — new module-level constant near
  `_REQUIRED_TOOLS` (`main.py:56`):
  - `'git'` → `https://git-scm.com/downloads`
  - `'uv'`  → `https://docs.astral.sh/uv/getting-started/installation/`
  - `'just'`→ `https://github.com/casey/just#installation`
- `_verify_required_tools() -> None` — modified (`main.py:503-512`). Same
  signature and raise/return contract (silent on success, `RuntimeError` on
  failure). New body composes:
  - header: `f'required tool(s) not found on PATH: {", ".join(missing)}'`
  - one fragment per missing tool, em-dash/indent idiom:
    `'\n  - {tool}: {_TOOL_INSTALL_HINTS[tool]}'`
  - iteration order driven by `_REQUIRED_TOOLS`, not the dict.

**Verify**:
- `just check` passes (format + lint + typecheck + existing tests green).
- Existing required-tools tests still pass unchanged:
  `python -m pytest tests/test_main.py -k "required_tools" -q` exits 0
  (covers `test_main.py:373-442` substring matches on `git`/`uv`).
- Manual/scripted assertion that the message is per-tool — run:
  `python -c "import unittest.mock as m, modernpackage.main as M; \
  p=m.patch.object(M.shutil,'which',side_effect=lambda t: None if t=='uv' else '/x'); \
  p.start();\
  import pytest;\
  \
  exec('try:\n M._verify_required_tools()\nexcept RuntimeError as e:\n s=str(e)\n assert \"docs.astral.sh/uv\" in s, s\n assert \"git-scm.com\" not in s, s\n print(\"OK\")')"`
  prints `OK` (uv hint present, git hint absent when only uv is missing).

---

## Phase 2: Per-tool URL test coverage + multi-missing regression guard

Add unit tests asserting the correct install URL appears for each
individually-missing tool and that all three hints appear when all are missing —
mirroring the existing `_verify_required_tools` test shape — and confirm the
abort-before-mutation guarantee still holds.

**Files**: `tests/test_main.py`

**Key changes** (new `def test_*` functions, plain `assert`, near
`test_main.py:373-442`):
- `test_verify_required_tools_hint_points_at_git_install_docs` — patch
  `modernpackage.main.shutil.which` with `side_effect` returning `None` only for
  `git`; assert `str(exc_info.value)` contains `git-scm.com/downloads` and does
  **not** contain the uv/just URLs.
- `test_verify_required_tools_hint_points_at_uv_install_docs` — same for `uv` →
  `docs.astral.sh/uv`.
- `test_verify_required_tools_hint_points_at_just_install_docs` — same for `just`
  → `github.com/casey/just#installation`.
- `test_verify_required_tools_lists_all_install_hints_when_all_missing` —
  `which` returns `None` for everything; assert all three URLs present in one
  message (one line per tool).

Each uses `pytest.raises(RuntimeError, match=...)` plus
`str(exc_info.value)` fragment inspection (`test_main.py:373-423` pattern).

**Verify**:
- `just check` passes.
- `python -m pytest tests/test_main.py -k "required_tools or hint" -q` exits 0
  with the four new tests collected and passing.
- Abort-early guard intact:
  `python -m pytest tests/test_main.py -k "aborts or call_count or reports_all_missing" -q`
  exits 0 (confirms `popen_mock.call_count == 0` paths and checklist abort tests
  at `test_main.py:584-709`, `1146-1229` are unaffected).

---

## Testing Checkpoints

- **After Phase 1**: `just check` green; `_verify_required_tools` raises a
  `RuntimeError` whose message contains the *specific* install URL for each
  missing tool (and omits URLs for present tools); legacy `git`/`uv` substring
  assertions still pass; no clone/`Popen` is reached on failure. The feature is
  functionally complete at this point even if Phase 2 is skipped.
- **After Phase 2**: Four new per-tool/all-missing unit tests pass; full
  `python -m pytest tests/test_main.py -q` exits 0; exit-code mapping
  (`RuntimeError` → 1) and checklist `[ok]`/`[FAIL]` output are unchanged.

## Notes / Out of Scope (per design)

- No package-name preflight verifier; name validation stays at the argparse layer
  (`validate_package_name`, exit code 2). The `package name valid` registry slot
  remains `lambda: None`.
- No friendly+raw two-part split for the tools message — single inline message.
- No changes to check ordering, exit codes, target-dir/remote verifiers,
  `humanize_git_clone_error`, or any post-clone step.
