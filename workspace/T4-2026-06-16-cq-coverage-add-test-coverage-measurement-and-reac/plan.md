# Plan

## Context (current state)

- Package source lives in `modernpackage/main.py` (62 lines) plus
  `modernpackage/__init__.py` (`__version__`).
- One test exists: `tests/test_main.py::test_show_version`.
- Coverage tooling is already wired: `pytest-cov` is a test dependency and
  `pyproject.toml` has `[tool.pytest.ini_options]`:
  `addopts = "--cov=. --no-cov-on-fail --cov-fail-under=50.0"`.
- Current measured coverage (`coverage report`): `modernpackage/main.py` 58%,
  TOTAL 69%. The `--cov=.` scope also counts the `tests/` package, inflating the
  number; the meaningful target is the `modernpackage` package.
- Uncovered code in `main.py`: the non-alphanumeric branch of
  `check_alpha_numeric`, all of `parse_args`, all of `init_new_package`, and the
  `elif parsed_args.package_name` branch of `main` (plus the no-argument path).

## Phase 1: Configure coverage measurement and reach >= 95%

### 1. Scope coverage to the package and enforce the threshold

In `pyproject.toml` `[tool.pytest.ini_options]`, change `addopts` so coverage is
measured against the package only and fails below 95%:

```toml
addopts = "--cov=modernpackage --no-cov-on-fail --cov-fail-under=95.0"
```

Rationale: `--cov=modernpackage` removes the `tests/` package from the
denominator so the percentage reflects real source coverage; raising
`--cov-fail-under` to `95.0` makes the suite enforce the task's threshold
automatically. Keep `--no-cov-on-fail` as-is.

(Optional, only if it reads cleanly alongside the existing Justfile style: a
dedicated `coverage` recipe is not required because `just test` already invokes
pytest with the `--cov` addopts. Do not add one unless it provides clear value.)

### 2. Add tests covering the remaining lines in `main.py`

Add focused tests to `tests/test_main.py` (follow the existing `unittest.mock`
patching style already used there — patch on `modernpackage.main`). Tests must be
deterministic and must not perform real subprocess/network calls:

- `check_alpha_numeric`: one test asserting a valid alphanumeric value is
  returned unchanged, and one asserting `ArgumentTypeError` is raised for a value
  containing non-alphanumeric characters (use `pytest.raises`).
- `parse_args`: test by patching `sys.argv` (or `modernpackage.main` argv access)
  to exercise the parser and assert the returned `Namespace` fields.
- `init_new_package`: patch `modernpackage.main.Popen` (and `Path.cwd` if needed)
  and assert it is invoked for the `git clone` and `make init` steps without
  spawning real processes.
- `main`: add a test for the `elif parsed_args.package_name` branch (patch
  `init_new_package` / `parse_args`, assert it is called with the package name),
  and a test for the path where neither `version` nor `package_name` is set
  (asserts nothing is printed / no init is called).

### 3. Verify

- [x] Run `just test` (or `just check`). Verify:
  - [x] The suite passes. (8 tests, 0.22s)
  - [x] Reported coverage for `modernpackage` is `>= 95%` and the
    `--cov-fail-under=95.0` gate does not fail. (100% coverage reached)
- [x] Run `just check-format`, `just check-lint`, `just check-typecheck` on the
  changed/added files to confirm the new tests satisfy the project's style and
  typing gates (note `tests/*` already ignores `S101`/`D` per
  `per-file-ignores`).
  - Note: `just check-format` fails on pre-existing formatting issues in
    `modernpackage/main.py` (missing trailing comma and unwrapped long line).
    These are not introduced by this phase. The test file `tests/test_main.py`
    passes all three checks cleanly.

### Success criteria

- `pyproject.toml` measures coverage against `modernpackage` and enforces
  `--cov-fail-under=95.0`.
- `just test` passes with package coverage `>= 95%`.
- New tests are deterministic and use mocks (no real `git`/`make`/network calls).
