# Design Discussion

## Current State

The deliverable described in `task.md` — an e2e test that scaffolds a package
from the template and asserts the result passes `just check` — **already exists**
in the repository as `tests/test_e2e.py:50-74`
(`test_scaffolded_package_passes_check`). Verified against the working tree, not
only research.

What the existing test already does:
- Skips when `git`/`just`/`uv` are not on PATH (`test_e2e.py:52-54`,
  `REQUIRED_TOOLS` at `test_e2e.py:25`).
- Clones the **local committed checkout** `REPO_ROOT` into `tmp_path/scaffoldcheck`
  (`test_e2e.py:24,59-60`) — intentionally *not* the GitHub URL that production
  `init_new_package` uses (`main.py:87-92`).
- Runs `just init scaffoldcheck` with an injected git author/committer identity
  (`_GIT_IDENTITY_ENV`, `test_e2e.py:27-32,62-67`) because `just init`'s
  `git commit` requires one (`Justfile:72`).
- Asserts the renamed `scaffoldcheck/__init__.py` exists and is pinned to `0.0.1`
  (`test_e2e.py:69-71`).
- Runs `just check` and asserts exit code 0 (`test_e2e.py:73-74`).
- Wraps every subprocess in `_run`, which uses
  `subprocess.run(..., check=False, capture_output=True, text=True)`
  (`test_e2e.py:35-47`) — matching the graceful-boundary convention.

Supporting infrastructure is also already in place:
- The `e2e` marker is defined (`pyproject.toml:41-43`) and excluded from the
  default run via `addopts = "... -m 'not e2e'"` (`pyproject.toml:40`).
- `just test-e2e` selects the marker explicitly (`Justfile:16-17`); the trailing
  `-m e2e` overrides the `-m 'not e2e'` in `addopts` (last `-m` wins).
- `just check` runs `check-format check-lint check-complexity check-typecheck
  test audit` (`Justfile:52`); its inner `test` step inherits `-m 'not e2e'`, so
  the e2e test does **not** recurse into itself (`Justfile:13-14`,
  `pyproject.toml:40`).

The one genuine gap versus the task's stated goal ("guarantee, via a real
subprocess/filesystem run"): **no CI job runs the e2e test.** Both CIs invoke
only `just check` (`.gitlab-ci.yml:19-23`,
`.github/workflows/check-modernpackage-on-python314.yml:6-35`), which excludes
`e2e`. So the guarantee is opt-in (`just test-e2e`) and never enforced
automatically.

## Desired End State

An e2e test that scaffolds the local template and asserts `just check` passes,
**confirmed to actually pass** when run, with the codebase conventions intact.

Verification:
- `just test-e2e` runs `test_scaffolded_package_passes_check` to green on a
  networked machine with `git`/`just`/`uv` and Python 3.14 available.
- `just check` (default, `-m 'not e2e'`) stays green and ≥95% coverage
  (`pyproject.toml:40`) — i.e. the e2e file does not regress the default suite.
- `just lint` / `just typecheck` pass on `tests/test_e2e.py`.

Because the literal artifact exists, the realistic scope of this task is
**verify-and-harden**, not greenfield authoring. See Design Decisions.

## Patterns to Follow

- **Subprocess boundary**: `_run` with `check=False, capture_output=True,
  text=True` and assertions that surface `stdout`/`stderr` on failure
  (`test_e2e.py:35-47,60,67,74`). Mirror this for any new subprocess call.
- **Tool-availability skip**: loop `REQUIRED_TOOLS` + `shutil.which` + `pytest.skip`
  (`test_e2e.py:52-54`). Keep e2e tests self-skipping, never hard-failing on a
  bare environment.
- **Git identity injection**: `os.environ | _GIT_IDENTITY_ENV` (`test_e2e.py:65`)
  to satisfy `just init`'s commit (`Justfile:72`).
- **Marker discipline**: any real-subprocess test gets `@pytest.mark.e2e`
  (`test_e2e.py:50`); the marker is the only mechanism that keeps it out of the
  default/CI run (`pyproject.toml:40`).
- **Module-private helpers** prefixed `_` (`_run`, `_GIT_IDENTITY_ENV`) and full
  words in identifiers, per the code-style guide.
- **Document intentional deviations** in the module docstring (`test_e2e.py:7-14`).

Patterns to NOT follow / watch for:
- Do **not** mirror the production GitHub clone in `init_new_package`
  (`main.py:87-92`) for the test — cloning the local checkout is the deliberate,
  documented choice (`test_e2e.py:7-12`) so local template regressions fail.
- Do **not** rely on ambient `~/.gitconfig` for identity (production does;
  `main.py` path) — tests must inject it for hermeticity.

## Design Decisions

1. **Treat the existing `tests/test_e2e.py` as the deliverable, do not rewrite**:
   per CLAUDE.md "Surgical Changes" — the file already satisfies the task
   verbatim. Rewriting would be churn with no behavioral gain.
2. **Scope = verify-and-harden, not author**: the implementation step is to run
   `just test-e2e` and confirm green; only touch the file if verification
   surfaces a real defect. Assumption recorded: the task author may not have
   known the test already existed (this is the "-v2" workspace).
3. **Keep clone-from-local-checkout over `init_new_package`**: it is the
   documented, correct choice (`test_e2e.py:7-12`); switching to the GitHub flow
   would make the test depend on remote state and stop catching local
   regressions.
4. **Do NOT wire e2e into default CI `just check`**: it would add minutes and a
   hard network/`pip-audit` dependency to every push (`Justfile:40-41,52`;
   `test_e2e.py:13-14`), and contradicts the deliberate `-m 'not e2e'` default
   (`pyproject.toml:40`). The opt-in `just test-e2e` is the intended entry point.
   Flagged as an Open Risk rather than silently closed.
5. **Keep assertions minimal and outcome-focused**: existence + `0.0.1` pin +
   `just check` exit 0 (`test_e2e.py:69-74`). Do not add assertions on git
   history, file counts, or sed internals — those belong to the mocked unit tests
   in `test_main.py` and would couple the e2e test to `just init` internals.
6. **No new fixtures / `conftest.py`**: builtin `tmp_path` suffices
   (`test_e2e.py:51`); there is no second consumer to justify shared setup.

## What We're NOT Doing

- Not rewriting or restructuring `test_scaffolded_package_passes_check`.
- Not changing scaffolding logic: `modernpackage/main.py` or the `init` /
  `check` recipes (`Justfile:52,59-73`).
- Not adding a CI job to run `just test-e2e` (`.gitlab-ci.yml`, `.github/`).
- Not changing the `e2e` marker definition or the default `-m 'not e2e'`
  exclusion (`pyproject.toml:40-43`).
- Not adding a second e2e variant that exercises the GitHub-clone production path.
- Not asserting on `just init` internals (rename/sed/git steps) beyond the
  existing `__init__.py` checks.

## Open Risks

- **The guarantee is opt-in only.** No CI invokes `just test-e2e`, so a template
  regression that breaks `just check` is caught only when someone runs it
  manually. If the task's "guarantee" is meant to be automated, a follow-up to
  add a (possibly nightly/manual) CI job is required — out of current scope but
  the single most material gap.
- **Environment fragility.** The inner `just check` runs `uv sync` (PyPI + GitLab
  index, `pyproject.toml:97-99`) and networked `pip-audit` (`Justfile:40-41`);
  offline runners fail at sync (`test_e2e.py:13-14`). Verification must happen on
  a networked Python-3.14 machine (`pyproject.toml:8`).
- **`pip-audit` drift.** A newly published advisory against a transitive dep
  could fail `just check` (and thus this test) with no code change — a latent
  flake source inherent to auditing live data.
- **Verification may reveal the test is already-failing** for environment reasons
  (e.g. Python 3.14 unavailable locally), in which case the honest outcome is
  "test exists and is correct; cannot run here" rather than code changes.
