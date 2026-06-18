# Design Discussion

## Current State

`modernpackage` scaffolds a new package by shelling out to three external
executables, in order, with no up-front check that any of them exist:

1. **`git clone`** — `main.py:483-488`. This is the *first* subprocess **and the
   first filesystem change** (the clone creates `new_package_path`). It has **no**
   `FileNotFoundError` handler, so a missing `git` raises an **uncaught**
   `FileNotFoundError` — `main` only catches `RuntimeError` (`main.py:565`).
2. **`just init <module>`** — `main.py:508-514`, run *after*
   `_write_package_metadata` has already mutated the cloned `pyproject.toml`
   (`main.py:498-505`). A missing `just` here *is* handled: the `try/except
   FileNotFoundError` at `main.py:515-520` raises a friendly `RuntimeError`.
3. **`just check`** — `main.py:528-534`. No `FileNotFoundError` handler. This is
   the only path that reaches **`uv`**, **ruff**, **mypy**, **pytest**,
   **pip-audit** — all invoked transitively by the cloned `Justfile` recipes
   (`Justfile:8-46`). A missing `uv` therefore surfaces only as a non-zero
   `just check` exit (`main.py:540-545`), *after* a clone + init have completed.

So today the failure modes for missing tools are inconsistent and *late*: a
missing `git` crashes uncaught after nothing useful has happened; a missing `uv`
is misreported as a generic check failure after a full clone/init. The required
tool set is already named — but only in test code:
`REQUIRED_TOOLS = ('git', 'just', 'uv')` in `test_e2e.py:28`, with a
`shutil.which`-based skip loop at `test_e2e.py:55-57`. Production `main.py` has
**no `shutil` import and no PATH check** (research Q6).

## Desired End State

Before any subprocess is launched and before any filesystem change, the
scaffolding flow verifies that `git`, `just`, and `uv` are all resolvable on
`PATH`. If one or more are missing, it fails immediately with a clear,
actionable `RuntimeError` naming the missing tool(s), routed through `main`'s
existing `except RuntimeError` handler (`main.py:565-567`) to a stderr message
and exit code 1. No clone directory is created when a tool is missing.

**Verification:**
- New unit tests in `tests/test_main.py` patch `shutil.which` (on the
  `modernpackage.main` seam) to return `None` for each tool and assert
  `pytest.raises(RuntimeError, match=...)` naming that tool, and assert
  `Popen.call_count == 0` (no subprocess launched, no directory created).
- A test with all tools present confirms scaffolding proceeds unchanged
  (existing `Popen`-mocked happy-path tests at `test_main.py:281-310` still pass).
- `just check` passes (format, lint, complexity, typecheck, test, audit).

## Patterns to Follow

- **Two-tier error philosophy** (research Q4, `CLAUDE.md` "raise loudly on
  invariants, degrade at boundaries"): a missing required tool is a hard
  scaffolding invariant failure → `raise RuntimeError`, funneled through `main`'s
  single `except RuntimeError` (`main.py:565`). This matches the existing
  `just`-missing handler (`main.py:515-520`) and the git-clone/just-init raises
  (`main.py:496,526`).
- **Message wording** (research Q4): short phrase + em-dash + actionable
  remedy, e.g. the existing
  `"'just' command not found — install it to initialize the package. See
  https://github.com/casey/just#installation"` (`main.py:516-519`). Reuse this
  exact shape; include an install pointer per tool.
- **`shutil.which` as the presence check**: already the project's chosen
  mechanism in `test_e2e.py:55-57`. Reuse it in production; keep the required
  tuple identical to `test_e2e.py:28` so the two never drift.
- **Module-private constant naming** (`CODE_BEST_PRACTICES`): a module-level
  tuple `_REQUIRED_TOOLS`, mirroring how `_GIT_CLONE_ERROR_MESSAGES`
  (`main.py:19`) is defined inline at module scope.
- **Test seam patching** (research Q5): patch on the defining module object,
  e.g. `patch('modernpackage.main.shutil.which', ...)` or
  `patch.object(main, 'shutil')` — mirroring `patch('modernpackage.main.Popen')`
  (`test_main.py:281`) and `patch('modernpackage.main.run')` (`test_main.py:518`).
  No shared fixture; each test builds its own mocks.
- **`# noqa` discipline**: subprocess calls carry `S603/S607` markers
  (`main.py:483,508,529`); the new check uses no subprocess, so no new noqa.

**Patterns NOT to follow / pitfalls:**
- Do **not** rely on reactive `FileNotFoundError` handling as the primary
  mechanism — it is partial and late (it never catches `uv`, research Q6). The
  preflight check supersedes it; leave the existing `just init` handler in place
  as defense-in-depth (surgical-change rule, `CLAUDE.md` §3).
- Do **not** humanize via the `_GIT_CLONE_ERROR_MESSAGES` regex table — that is
  scoped to git-clone *stderr*, not tool presence.

## Design Decisions

1. **Check location: top of `init_new_package`, before the `git clone`
   `Popen` (`main.py:483`)** — Placing it inside `init_new_package` (rather than
   in `main`) guarantees the fail-fast invariant for *every* caller, including
   tests that invoke `init_new_package` directly (`test_main.py`), and keeps it
   strictly before the first filesystem change. `main` already wraps the call in
   `try/except RuntimeError`, so no `main` change is needed.

2. **Mechanism: `shutil.which` over each tool** — Already the project's
   established presence check (`test_e2e.py:55-57`). Add `import shutil` to
   `main.py:1-11`. A small private helper, e.g. `_verify_required_tools()`,
   keeps `init_new_package` readable and independently testable.

3. **Required set: `('git', 'just', 'uv')` as module-level `_REQUIRED_TOOLS`** —
   Matches `task.md` exactly and `test_e2e.py:28`. `uv` is included even though
   `main.py` never invokes it directly, because `just check` reaches it
   transitively (research Q2); checking it up front converts a confusing late
   `just check` failure into a clear preflight message.

4. **Report ALL missing tools in one message, not just the first** — Collect
   every absent tool and raise a single `RuntimeError` listing them, so the user
   installs everything in one pass rather than rerunning to discover the next
   gap. `task.md` says "naming the missing tool"; naming all missing tools
   satisfies and exceeds that. Wording follows the em-dash + install-pointer
   style (Decision per research Q4).

5. **Raise `RuntimeError`, not a custom exception** — Consistent with every
   existing hard-failure path in this module (`main.py:496,520,526`) and the
   single `except RuntimeError` funnel (`main.py:565`). `CODE_BEST_PRACTICES`
   mentions custom exceptions like `PhaseError`, but none exist in `main.py`;
   introducing one here would be speculative (`CLAUDE.md` §2).

6. **Keep the existing `just init` `FileNotFoundError` handler** — Do not remove
   `main.py:515-520`. It is harmless defense-in-depth and removing it is an
   unrelated change (`CLAUDE.md` §3, surgical changes).

## What We're NOT Doing

- **Not** checking the transitive tools (`ruff`, `mypy`, `pytest`, `pip-audit`,
  `sed`, `nproc`, etc., research Q2). They are `uv`/shell concerns; the task
  scope is exactly `git`, `just`, `uv`.
- **Not** verifying tool *versions* or that the executables actually work — only
  presence on `PATH`, as `task.md` specifies.
- **Not** changing `main`, `parse_args`, the git-clone humanization table, or any
  message wording for the existing three subprocess calls.
- **Not** adding a CLI flag to skip the check, a config option, or any
  configurability that was not requested (`CLAUDE.md` §2).
- **Not** refactoring `init_new_package`'s structure beyond inserting the check
  and (optionally) extracting one small helper.

## Open Risks

- **Test seam for `shutil.which`**: tests must patch the same path the helper
  calls. If the helper does `shutil.which(...)`, patch `modernpackage.main.shutil`
  or `...main.shutil.which`; using `from shutil import which` would change the
  seam. Decision: `import shutil` + `shutil.which(...)` to keep one obvious seam.
- **E2E interaction**: `test_e2e.py` skips when a tool is absent
  (`test_e2e.py:55-57`), so the new production check never fires there under
  normal CI; the behavior is covered by the new mocked unit tests instead. Low
  risk, noted for the planner.
- **Message specificity vs. brevity**: per-tool install URLs (git, just, uv)
  lengthen the message; if a single combined line reads cleanly, prefer naming
  the tools with one generic "install the missing tool(s)" remedy plus the `just`
  URL already in use. Final wording is a small judgment call for implementation.
