# Design Discussion

## Current State

`init_new_package` (`modernpackage/main.py:497-575`) runs two pre-flight checks
and then makes first network contact *by cloning*:

1. `_verify_required_tools()` — `git`/`just`/`uv` on PATH (`main.py:475-484`,
   constant `_REQUIRED_TOOLS` at `main.py:56`).
2. `_verify_target_directory_absent(new_package_path)` (`main.py:487-494`).
3. `git clone https://github.com/albertas/modernpackage <dir>` via `Popen` with
   all three streams `PIPE` (`main.py:513-518`); non-zero exit builds a `raw`
   message, runs it through `humanize_git_clone_error`, and raises `RuntimeError`
   (`main.py:519-526`).

So an unreachable remote (DNS failure, network down, missing/private repo) is
only discovered *during* the clone, and is classified post-hoc by string-matching
its stderr (`humanize_git_clone_error`, `main.py:59-65`; pattern table
`_GIT_CLONE_ERROR_MESSAGES`, `main.py:20-52`). There is **no dedicated
reachability pre-check** today (research "Open Areas", research.md:204-209).

The template URL is a **bare literal duplicated twice** — in the clone argv
(`main.py:514`) and as the metadata replacement target (`main.py:448`). There is
no shared constant, which deviates from the module's own convention of
module-level constants for tools/env/regex (`main.py:56,93-110,20-52`).

Two subprocess idioms coexist intentionally (research Q6, research.md:159-178):
`Popen`+`PIPE`+manual `returncode` for the scaffolding pipeline; and
`run(check=False, capture_output=True, text=True)` for the silent git-config
probe (`_git_config_default`, `main.py:222-232`).

## Desired End State

A pre-flight helper confirms the template remote is reachable *before* the clone
starts, failing fast with the same friendly + raw message style already used for
clone errors. Verify by:

- A new helper `_verify_template_remote_reachable()` raises `RuntimeError` (with a
  humanized message) when the remote cannot be reached, and returns `None`
  silently when it can.
- `init_new_package` calls it after the existing two pre-flight checks and before
  `Popen(['git', 'clone', ...])`.
- New unit tests: reachable → no raise + clone proceeds; unreachable (resolve
  host, repo-not-found, auth, timeout) → `RuntimeError` whose message contains
  both the friendly fragment and the raw exit/stderr fragment, and the clone
  `Popen` is **never** reached.
- `just check`, `just lint`, `just typecheck`, `just test` all green.

## Patterns to Follow

- **Pre-flight validator shape** (`_verify_required_tools` `main.py:475-484`,
  `_verify_target_directory_absent` `main.py:487-494`): `_verify_*` name, no
  return value, raise `RuntimeError` on failure. The new helper joins this family
  and is called alongside them at `main.py:510-511`.
- **`run`-as-probe idiom** (`_git_config_default`, `main.py:222-232`): invoke with
  `run(..., check=False, capture_output=True, text=True)`, inspect `returncode`,
  `text=True` so stderr is already `str`. Carry `# noqa: S603` on the call and
  `# noqa: S607` on the argv line (`main.py:222-223`).
- **Reuse `humanize_git_clone_error`** (`main.py:59-65`): `git ls-remote` emits the
  same "could not resolve host" / "repository ... not found" / "authentication
  failed" stderr that the pattern table (`main.py:20-52`) already classifies — no
  new patterns needed.
- **Message phrasing** (research Q6, research.md:179-190): "<problem> — <action>";
  friendly + raw joined as `f'{friendly}\n\n{raw}'` (`main.py:525`).
- **Module-level constants** for fixed values (`main.py:56`): URL and timeout
  become constants, matching `_REQUIRED_TOOLS`.
- **Test seam patterns** (research Q5, research.md:108-150): patch
  `modernpackage.main.run` returning `MagicMock(returncode=, stderr=)` (mirrors the
  git-config tests at `tests/test_main.py:586-606`); use
  `pytest.raises(RuntimeError, match=...)`.

Patterns to **avoid**: do **not** use `Popen` for the reachability probe. The
clone/init/check tests assert exactly 3 `Popen` calls
(`tests/test_main.py:288`) and index `call_args_list[0]` as the clone
(`tests/test_main.py:297`). A `Popen`-based probe would shift those indices and
break the count; the `run` idiom keeps the `Popen` pipeline untouched.

## Design Decisions

1. **Probe with `git ls-remote <url>`** — chosen over a raw socket/HTTP check or a
   Python `urllib` ping. `git` is already a required tool (`_REQUIRED_TOOLS`,
   `main.py:56`), `ls-remote` contacts the remote without cloning, and its stderr
   is already understood by `humanize_git_clone_error`. A non-git check would need
   its own error vocabulary and miss repo-missing/private cases.

2. **Use `run(check=False, capture_output=True, text=True)`, not `Popen`** — this
   is a pre-flight *probe*, and the `run` idiom is the module's existing probe
   style (`main.py:222-232`). It also keeps the `Popen` pipeline (and its
   call-count/index assertions) intact. Trade-off accepted: every
   `init_new_package` test must now also patch `modernpackage.main.run` (see Open
   Risks).

3. **Bound the probe with a timeout constant** — add
   `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (module-level, ~10s) and pass
   `timeout=` to `run`. A hung DNS/connect would otherwise defeat "fail fast".
   `subprocess.TimeoutExpired` is caught and mapped to the network/unreachable
   friendly message. A constant (not a parameter) avoids unrequested
   configurability (CLAUDE.md §2).

4. **Introduce `_TEMPLATE_REPOSITORY_URL` constant** — the new helper and the clone
   both need the URL, so DRY for the new code requires a single source. Use it in
   the helper and the clone argv (`main.py:514`). The metadata-replacement literal
   (`main.py:448`) is updated to reference it too, since it is now a named
   constant and this removes the duplication the new code touches; this is a small,
   in-scope tidy, not a refactor.

5. **Helper raises `RuntimeError` with friendly+raw, mirroring the clone block** —
   build `raw = f'template remote unreachable (git ls-remote exit code {rc}): {stderr}'`,
   `friendly = humanize_git_clone_error(stderr)`, raise
   `f'{friendly}\n\n{raw}'` when matched else `raw`. On `TimeoutExpired`, raise the
   network friendly message directly (no stderr to match).

6. **Call order: after tools + dir checks, before clone** (between `main.py:511`
   and `main.py:513`) — the probe needs `git` on PATH, so it must follow
   `_verify_required_tools`; it must precede the clone to fail fast.

## What We're NOT Doing

- No ret/ backoff or retry logic on the probe — one attempt, fail fast.
- No reachability check for `just`/`uv` registries or any non-template network.
- No new entries in `_GIT_CLONE_ERROR_MESSAGES` — existing patterns suffice.
- No change to `just init` / `just check` error handling or to the `Popen`
  pipeline mechanics.
- No CLI flag to skip or configure the check (timeout stays a constant).
- No broad URL-deduplication refactor beyond introducing the one constant the new
  code needs (decision 4).

## Open Risks

- **Test cascade from the new `run` call** (highest risk): every existing
  `init_new_package` test patches only `Popen`
  (`tests/test_main.py:284,292,307,...`) and would now execute a *real*
  `git ls-remote` network call. All such tests must add
  `patch('modernpackage.main.run')` returning `returncode=0`. The `test_e2e.py`
  flow does not call `init_new_package` (research.md:152-154), so it is unaffected
  — but confirm no e2e path performs a live `ls-remote`.
- **Probe stderr wording vs. clone stderr**: `git ls-remote` phrasing may differ
  slightly from `git clone` (e.g. "remote: Repository not found"). The existing
  patterns (`main.py:30-33`) look robust, but verify each simulated case matches.
- **`text=True` vs. `.decode()`**: the clone block decodes bytes manually
  (`main.py:520`); the `run` probe uses `text=True` so stderr is already `str` —
  ensure the helper does not double-decode.
- **Timeout value**: 10s is a guess; too low risks false negatives on slow links,
  too high weakens "fail fast". Tune if it surfaces in practice.
