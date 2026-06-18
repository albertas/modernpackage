# Design Discussion

## Current State

- Scaffolding is driven by `init_new_package(package_name)` (`modernpackage/main.py:83`),
  a two-step flow: (1) `git clone https://github.com/albertas/modernpackage <dest>`
  with a **hardcoded GitHub URL** (`main.py:87-92`), then (2) `just init <name>` run
  inside the clone (`main.py:103-108`). Failures raise `RuntimeError`.
- The `init` recipe (`Justfile:59-73`) rewrites `modernpackage` → `<name>` across
  tracked files (`git grep`/`sed`), resets the version to `0.0.1`, renames the package
  dir, wipes `.git`/`.venv`, and re-inits a fresh git repo with one commit. It depends on
  a populated `.git` (uses `git grep`).
- The quality gate is `check: check-format check-lint check-complexity check-typecheck
  test audit` (`Justfile:52`). Each sub-recipe first runs `sync` (`Justfile:9-11`:
  `uv pip sync requirements-dev.txt` + `uv pip install -e .[test]`). `audit` and `sync`
  both need network (`Justfile:40-41`; gitlab index at `pyproject.toml:97-99`).
- The `e2e` marker is **registered but unused**: declared at `pyproject.toml:41-43`;
  the default run excludes it via `addopts = "... -m 'not e2e'"` (`pyproject.toml:40`);
  `just test-e2e` runs `uv run pytest -m e2e` (`Justfile:16-17`), where the trailing
  `-m e2e` overrides the `addopts` selector. No e2e test exists yet — `tests/` holds only
  `__init__.py` and `test_main.py`, and there is no `conftest.py`.
- Existing tests fully **mock** subprocess via `patch('modernpackage.main.Popen')`
  (`tests/test_main.py:49,57,68,81`); no test uses `tmp_path`, `monkeypatch`, or touches
  the real filesystem/network.

## Desired End State

A single `e2e`-marked test that scaffolds a package **from the local working tree**,
runs `just check` inside the generated package, and asserts the gate is green.

Verify correct when:
- `just test-e2e` runs the new test and it passes against the current repo checkout.
- `just test` (and plain `pytest`) still **exclude** it — confirmed by it not appearing in
  the default run and the 95% coverage gate being unaffected (e2e is excluded from coverage
  via `-m 'not e2e'`, `pyproject.toml:40`).
- A deliberately-introduced template defect (e.g. a lint error in `modernpackage/`) makes
  the e2e test fail — proving it actually gates the template.

## Patterns to Follow

- **Subprocess at the boundary**: per Code Best Practices, use
  `subprocess.run(..., check=False, capture_output=True, text=True)`, inspect `returncode`,
  and surface `stderr` in the assertion message rather than raising. (Note: production
  `main.py` uses `Popen`; the e2e test is a boundary harness, so `subprocess.run` is the
  cleaner fit — do NOT copy the `Popen`+`communicate` ceremony from `main.py:87-116`.)
- **Filesystem isolation**: use the built-in `tmp_path` fixture (CLAUDE.md / Code Best
  Practices §Testing). This is a *new* pattern for this suite — none of `tests/` uses it
  yet — but it is the project-endorsed fixture, so introduce it here.
- **Test shape**: top-level `def test_*`, plain `assert`, behavior-describing name; tests
  ignore `S101`/`D` (`pyproject.toml:75-76`), matching `tests/test_main.py`.
- **Marker usage**: decorate with `@pytest.mark.e2e` using the marker already registered at
  `pyproject.toml:41-43`. No new registration needed.

## Design Decisions

1. **Scaffold from the local checkout, not the hardcoded GitHub URL** — The stated goal is
   confidence that *this template* (the local tree under test) produces a green project. If
   the test reused `init_new_package` (`main.py:83`) it would clone GitHub and validate the
   *published* tree, so a regression in the local checkout would not fail the test — useless
   as a pre-merge gate. The test instead replicates the two-step flow against the local repo
   root: `git clone <repo_root> <dest>` then `just init <name>`. This needs no production
   change (the URL is inline, not a constant; refactoring it would be scope creep).
2. **Replicate the flow rather than call `init_new_package`** — Consequence of (1). The
   production function is already covered by unit tests in `test_main.py`; the e2e value is
   verifying the template is green, which the replicated local-clone path delivers without a
   GitHub round-trip. Document this as an intentional deviation in the test.
3. **New file `tests/test_e2e.py`** — Keep the slow, real-IO e2e test separate from the
   fast mocked unit tests in `test_main.py`. Single test file, no `conftest.py` (none
   exists today).
4. **Assert on `just check` exit code** — Run `subprocess.run(['just', 'check'],
   cwd=<dest>, ...)`, assert `returncode == 0`, embedding stdout/stderr in the failure
   message for debuggability. This exercises the entire gate (format, lint, complexity,
   typecheck, test, audit) in one shot, matching the task.
5. **Skip gracefully when required tooling is absent** — Guard with `shutil.which` for
   `git`, `just`, and `uv`; `pytest.skip(...)` if any is missing. e2e environments may lack
   them, and a skip is more honest than a confusing failure. (Assumption: skipping is
   acceptable here; the test still runs in CI where the toolchain is installed —
   `.gitlab-ci.yml:13-22` installs `rust-just`.)
6. **Use `git clone <repo_root>` (a real clone), not a file copy** — `just init` requires a
   populated `.git` (`git grep`, `Justfile:61-65`). A clone of the local repo provides
   tracked files plus `.git` exactly as the GitHub clone would, so `init` runs unmodified.
   Clone the repo root resolved relative to the test file, not `Path.cwd()`.
7. **No explicit subprocess timeout (for now)** — Keep the first version simple; flag long
   runtime as a risk below rather than guessing a bound that may be too tight on slow CI.

## What We're NOT Doing

- Not refactoring `main.py` to make the clone URL injectable/configurable.
- Not modifying `init_new_package`, the `init` recipe, or any production code.
- Not adding the e2e test to `just check` or the default `just test` run — it stays e2e-only.
- Not stubbing/mocking network, git, or `just`; this is a genuinely end-to-end test.
- Not adding a `conftest.py` or shared fixtures beyond the built-in `tmp_path`.
- Not testing the GitHub-hosted template or `init_new_package`'s error-humanization (already
  unit-tested at `test_main.py:56-84`).
- Not asserting on intermediate scaffolding artifacts (renamed files, version reset); the
  single `just check` green/red signal is the contract.

## Open Risks

- **Runtime & network**: the inner `just check` runs a full `uv sync` (network), `pytest`,
  and a networked `pip-audit` (`Justfile:40-41`). The test may take minutes and is
  network-dependent; an offline runner will fail at `sync`/`audit`. Acceptable for an
  e2e test, but worth a comment in the test.
- **No recursion, but confirm**: the generated package contains this same `tests/` tree, so
  its `just check` will re-discover the e2e test. The inner `test` step runs `-m 'not e2e'`
  (`Justfile:13-14`, `pyproject.toml:40`), so it is excluded and there is no infinite
  scaffolding recursion — but this must hold; verify during implementation.
- **Local uncommitted changes**: `git clone <repo_root>` copies only **committed** state.
  Uncommitted edits to the template won't be tested. Note this in the test docstring; CI
  (which tests committed refs) is unaffected.
- **`just init` git identity**: the recipe runs `git commit` (`Justfile:72`); on a machine
  with no configured `user.email`/`user.name`, the commit (and thus `init`) fails. May need
  to set a throwaway identity via env or `-c` in the clone/init invocation — investigate in
  implementation.
- **Introducing `tmp_path`** is a new pattern for this suite; ensure it reads cleanly so it
  becomes a good template for future e2e tests.
