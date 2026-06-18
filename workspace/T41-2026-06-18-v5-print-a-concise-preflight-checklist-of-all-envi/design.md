# Design Discussion

## Current State

The preflight phase lives in `modernpackage/main.py` and is **silent on success**.
`init_new_package` runs three verifiers in order, all before any `Popen`
(`main.py:555-557`):

1. `_verify_required_tools()` (`main.py:484-493`) — `shutil.which` over
   `_REQUIRED_TOOLS = ('git', 'just', 'uv')` (`main.py:56`).
2. `_verify_target_directory_absent(new_package_path)` (`main.py:496-503`) —
   raises if `target_path.exists()`.
3. `_verify_template_remote_reachable()` (`main.py:506-539`) — bounded
   `git ls-remote` probe (`_REMOTE_REACHABILITY_TIMEOUT_SECONDS = 10`,
   `main.py:65`).

Each returns `None` on success and raises `RuntimeError` on failure
(`main.py:493, 503, 529, 539`); the error is caught in `main()` and printed to
stderr (`main.py:641-643`). Name/email/URL validation runs earlier, at argparse
time, via `validate_package_name` (`main.py:173-186`, wired at `main.py:351`)
and raises `ArgumentTypeError` → `SystemExit(2)`.

There is **no checklist emitter today** (research "Open Areas",
`research.md:178-183`): checks run imperatively, the user sees nothing unless a
check fails. Output is plain builtin `print` with `# noqa: T201`, no
Rich/Click/colorama, no ANSI styling, stdlib-only imports
(`research.md:57-76`; runtime `dependencies = []`, `pyproject.toml:18`).

## Desired End State

Before scaffolding starts, the CLI prints a concise, one-line-per-check
checklist to **stdout** showing every preflight check and its outcome, e.g.:

```
Preflight checks:
  [ok]   package name valid
  [ok]   required tools on PATH (git, just, uv)
  [ok]   target directory available
  [FAIL] template remote reachable
```

On the happy path all checks show `[ok]` and scaffolding proceeds unchanged. On
failure the failing check is marked `[FAIL]`, the existing `RuntimeError`
remediation message still propagates to stderr via `main()`, and `Popen` is
never reached (existing abort-before-`Popen` contract, `research.md:113-114`).

**Verification:** (a) new unit test asserts the checklist text/order is printed
on a clean run; (b) new test asserts a failing check prints `[FAIL]` for that
line and the prior checks as `[ok]`; (c) existing tests still pass — in
particular `popen_mock.call_count == 0` on preflight failure
(`test_main.py:385, 400, 415, 442, 637, 1087`) and the `pytest.raises(RuntimeError,
match=...)` assertions (`test_main.py:135-137` patterns).

## Patterns to Follow

- **Raise-on-failure preflight idiom** (`main.py:493, 503, 539`): keep the
  individual verifiers raising `RuntimeError`. The orchestrator wraps them; it
  does not change their contract.
- **`print(...)  # noqa: T201` to stdout for informational/success output**
  (`main.py:614, 629`; `research.md:62-64`). The checklist is informational →
  stdout. Keep the `# noqa: T201` marker on every new `print`.
- **No styling / ASCII only** (`research.md:69-70`): no ANSI, no third-party
  formatter. Use plain bracket markers, not color.
- **`@dataclass(frozen=True)` for plain data records** (Code Best Practices;
  e.g. `_GIT_CLONE_ERROR_MESSAGES` tuple table, `main.py:20-52`). Model the
  check registry as immutable data.
- **Module-private `_`-prefixed symbols, tested by direct import**
  (`research.md:103-106, 173-174`): new helpers are `_`-prefixed and imported
  straight from `modernpackage.main` in tests.
- **`_NAME_RE`-style constant suffixes and `_REQUIRED_TOOLS`-style tuples**
  (`main.py:56`): reference existing constants for labels, do not re-spell tool
  names.

Patterns NOT to follow / avoid:
- Do **not** introduce a logging module, Rich, or any new dependency
  (`research.md:71-74`) — keep stdlib-only.
- Do **not** convert the verifiers to return booleans/results objects; that
  would ripple through every call site and test. Keep them raising.
- Do **not** print the checklist to stderr — failure *remediation* goes to
  stderr (unchanged), but the checklist itself is stdout.

## Design Decisions

1. **Orchestrator wraps existing verifiers; verifiers unchanged** — add
   `_run_preflight_checks(target_path)` that iterates an ordered registry,
   prints each line, and lets the first `RuntimeError` propagate after marking
   that line `[FAIL]`. Minimal, surgical (CLAUDE.md §3); preserves every
   verifier contract and existing test seam.

2. **Check registry as a `frozen=True` dataclass list, built per-call** —
   `PreflightCheck(label: str, run: Callable[[], None])`. The list is assembled
   inside `_run_preflight_checks` so `_verify_target_directory_absent` can be
   bound to `target_path` via a closure. Avoids a module-global that can't see
   the runtime path.

3. **Abort on first failure (no "run all then report")** — matches the task's
   "sets up the follow-up work of aborting early" framing (`task.md:7-8`) and
   the current order-dependent behavior. Checks after the failure show nothing
   (they did not run); the printed lines reflect exactly what ran.

4. **ASCII status markers `[ok]` / `[FAIL]`** — terminal-safe, dependency-free,
   honors the no-styling convention (`research.md:69-70`). Right-padded so
   labels align. Chosen over Unicode ✓/✗ to avoid encoding surprises in CI logs.

5. **Surface name validation as a display-only passed line** — `validate_package_name`
   runs at argparse time (`main.py:351`); any invalid name exits with code 2
   long before `init_new_package`. So by the time the checklist prints, the name
   is guaranteed valid. We list it as `[ok] package name valid` for "at a glance"
   completeness (`task.md:5`) without re-invoking the validator (its
   `ArgumentTypeError` would not fit the `RuntimeError` flow).

6. **Checklist prints from inside `init_new_package`, replacing the three direct
   calls** (`main.py:555-557`) — single call site `_run_preflight_checks(new_package_path)`.
   Header line `Preflight checks:` then one indented line per check.

## What We're NOT Doing

- Not adding new remediation text or changing any existing `RuntimeError`
  message — that is explicitly the *follow-up* work (`task.md:7-8`).
- Not making the checklist quiet/verbose-configurable, no `--quiet` flag, no
  env toggle (no flexibility that wasn't asked, CLAUDE.md §2).
- Not collecting/aggregating all failures before reporting; not converting
  verifiers to non-raising.
- Not re-running argparse validators or touching `parse_args`.
- Not adding color, spinners, or progress animation.
- Not changing exit codes, stream choices for failures, or the `just check`
  end-of-run messaging (`main.py:613-621`).

## Open Risks

- **Existing print-assertion tests**: tests that inspect
  `print_mock.call_args_list` for exact success messages (`test_main.py:489, 572,
  597`) may now see extra checklist lines ahead of them. Mitigation: those tests
  filter to specific messages; verify each still locates its target and update
  index-based assertions if any exist.
- **Label drift vs. constants**: the `required tools` label embeds
  `(git, just, uv)`. Derive it from `_REQUIRED_TOOLS` (`main.py:56`) rather than
  hardcoding, so the checklist stays truthful if the tuple changes.
- **`[FAIL]` line vs. raised message ordering**: the `[FAIL]` line goes to
  stdout, the remediation to stderr — interleaving in a combined terminal is
  fine, but tests using `capsys` must read `.out` and `.err` separately
  (`research.md:133-134`).
- **Name-validation line honesty (Decision 5)**: showing `[ok]` for a check we
  do not re-run is a small fiction; acceptable because the precondition is
  provably already satisfied. Documented here so a reviewer is not surprised.
```

