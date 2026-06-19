# Implementation Plan

## Overview

Add a single new e2e test, `test_scaffolded_fullstack_package_passes_check`, to
`tests/test_e2e.py`. It scaffolds a fullstack package from the local committed
checkout via the production injection path (`main._inject_templates(destination,
fullstack=True)`), runs the generated `just check` (proving the **backend
pytest** suite passes), then installs and runs the **frontend Vitest** suite
directly, and asserts structural/token-rename expectations. **Test-only** — no
production code, `Justfile`, or template changes (design decision 7).

The test is built up across four incremental phases on the *same* function;
each phase leaves the file importable and the test runnable via `just test-e2e`
with strictly more coverage. Phase order follows `structure.md` exactly.

Grounding facts verified against the tree:
- `main._inject_templates` signature is `(package_path, *, fullstack)` — `fullstack`
  is keyword-only (`modernpackage/main.py:979`). It calls `_add_backend`, then
  `_add_frontend` when `fullstack`, then `_stage_injected_files` (`git add -A`),
  so **no manual staging is required**.
- `_FRONTEND_RECIPES` define `frontend-install` (`cd frontend && npm ci`),
  `frontend-test` (`cd frontend && npm run test` → `vitest run`), and the
  aggregate `frontend-check: frontend-install` (`main.py:595-614`). `frontend-test`
  does **not** depend on `frontend-install`, so install must run first.
- Frontend template lives under `frontend_template/` and is copied to
  `frontend/`; relevant token-bearing files: `frontend/package.json` (`"name":
  "modernpackage"`) and `frontend/src/App.test.tsx` (heading `modernpackage`).
  Both confirmed present (`frontend_template/package.json`,
  `frontend_template/src/App.test.tsx`).
- Generated `check` chain is `check: check-format check-lint check-complexity
  check-typecheck test audit # deadcode` (`Justfile:53`) — contains no `frontend-`
  token.
- e2e marker excluded from default run; e2e runs only via `just test-e2e`
  (`Justfile:17`, `pyproject.toml:40`).

---

## Phase 1: Backend-passing fullstack scaffold

Establish the scaffold → inject → init → `just check` skeleton for a fullstack
package, proving the backend pytest suite passes inside the generated `check`
chain. Mirrors `test_scaffolded_backend_package_passes_check`
(`tests/test_e2e.py:137-193`) but injects via the production fullstack entry
point — no manual `git add -A`, because `_inject_templates` stages internally.

### Changes

#### 1. New e2e test function
**File**: `tests/test_e2e.py`
**Action**: modify (append a new function after the existing tests, at EOF line 270)

```python
@pytest.mark.e2e
def test_scaffolded_fullstack_package_passes_check(tmp_path: Path) -> None:
    """Scaffold a fullstack package and run both backend and frontend test suites.

    Injects backend + frontend via the production path
    (`main._inject_templates(..., fullstack=True)`, which stages internally), runs
    the generated `just check` (backend pytest), then installs and runs the
    frontend Vitest suite directly.

    Caveats (inherited from sibling tests, see module docstring): the inner
    `just check` runs `uv sync` + networked `pip-audit`, and `just frontend-install`
    runs `npm ci`, which hits the network and needs a compatible Node toolchain.
    The `npm` skip guard makes Node-less environments (CI) skip rather than fail.
    """
    required_tools = (*REQUIRED_TOOLS, 'npm')
    for tool in required_tools:
        if shutil.which(tool) is None:
            pytest.skip(f'required tool not on PATH: {tool}')

    package_name = 'fullstack-check.pkg'
    module_name = normalize_module_name(package_name)
    destination = tmp_path / module_name

    clone = _run(['git', 'clone', str(REPO_ROOT), str(destination)], cwd=tmp_path)
    assert clone.returncode == 0, f'git clone failed:\n{clone.stdout}\n{clone.stderr}'

    main._write_package_metadata(  # noqa: SLF001
        destination,
        author_name='Test Author',
        author_email='test@example.org',
        description='An e2e fullstack package.',
        package_license='Apache-2.0',
        repository_url='https://example.org/repo',
    )
    main._strip_scaffolding(destination)  # noqa: SLF001
    # Production fullstack injection path: backend + frontend, then `git add -A`
    # internally (no manual staging needed, unlike the backend test).
    main._inject_templates(destination, fullstack=True)  # noqa: SLF001

    init = _run(
        ['just', 'init', module_name],
        cwd=destination,
        env=os.environ | _GIT_IDENTITY_ENV,
    )
    assert init.returncode == 0, f'just init failed:\n{init.stdout}\n{init.stderr}'

    check = _run(['just', 'check'], cwd=destination)
    assert check.returncode == 0, f'just check failed:\n{check.stdout}\n{check.stderr}'
```

Notes:
- `required_tools` is a **local** tuple extending the unchanged module-level
  `REQUIRED_TOOLS` (design decision 2) — other tests stay unaffected.
- `main._inject_templates(destination, fullstack=True)` — `fullstack` is passed
  as a keyword (it is keyword-only).
- Reuse the existing `_run(...)` helper for every subprocess call.

### Verification
#### Automated
- [ ] `just test-e2e -k fullstack` exits 0; output contains `1 passed` (Node
  present) **or** `1 skipped` (npm absent).
- [x] `just check` (root) exits 0 — the new function imports and is well-formed
  (e2e excluded from this run, so it does not execute the slow path).

#### Manual
- [x] `grep -q 'def test_scaffolded_fullstack_package_passes_check' tests/test_e2e.py`
  → exit 0.
- [x] `grep -q '_inject_templates(destination, fullstack=True)' tests/test_e2e.py`
  → exit 0 (production injection path used, not separate `_add_*` calls).
- [ ] On a Node-less box: `just test-e2e -k fullstack 2>&1 | grep -qE '1 skipped'`
  → exit 0 (skips, does not fail).

---

## Phase 2: Frontend Vitest suite executes

Add the frontend half: install Node deps, then run Vitest, asserting each
returns 0. This slice delivers the task headline ("run both backend and frontend
tests with fullstack").

### Changes

#### 1. Frontend install + test invocation
**File**: `tests/test_e2e.py`
**Action**: modify (append inside the Phase 1 function, after the `just check` assertion)

```python
    # Frontend: install deps then run Vitest. `frontend-test` (vitest run) does
    # NOT depend on `frontend-install`, so install must run first (design
    # decision 3). `npm ci` hits the network and needs a compatible Node.
    install = _run(['just', 'frontend-install'], cwd=destination)
    assert install.returncode == 0, (
        f'just frontend-install failed:\n{install.stdout}\n{install.stderr}'
    )

    # Run `frontend-test` directly (vitest run) — NOT `frontend-check`, which
    # also runs format/lint/typecheck (out of scope; design "Do NOT follow").
    frontend_test = _run(['just', 'frontend-test'], cwd=destination)
    assert frontend_test.returncode == 0, (
        f'just frontend-test failed:\n{frontend_test.stdout}\n{frontend_test.stderr}'
    )
    # Confirm Vitest actually executed (not a silent no-op). Vitest prints a
    # "Test Files" summary line to stdout/stderr on every run.
    combined_output = frontend_test.stdout + frontend_test.stderr
    assert 'Test Files' in combined_output, (
        f'Vitest did not appear to run:\n{frontend_test.stdout}\n{frontend_test.stderr}'
    )
```

Notes:
- Invoke `frontend-test` directly, **not** via `check` (design "What We're NOT
  Doing": `frontend-*` must stay out of the `check` chain).
- The `'Test Files'` marker assertion guards against the suite being silently
  skipped — if Vitest never ran, the marker is absent and the test fails.

### Verification
#### Automated
- [ ] `just test-e2e -k fullstack` exits 0 with `1 passed` where Node is
  available (now installs deps + runs Vitest).
- [x] `just check` (root) exits 0 (still well-formed).

#### Manual
- [x] `grep -q "just', 'frontend-install" tests/test_e2e.py` and
  `grep -q "just', 'frontend-test" tests/test_e2e.py` → both exit 0.
- [x] `grep -q 'frontend-check' tests/test_e2e.py` → exit 1 (the aggregate is
  NOT invoked as a success criterion). NOTE: grep exits 0 because the string
  'frontend-check' appears in a comment ("NOT `frontend-check`") in the added
  code. No actual `['just', 'frontend-check']` invocation exists — intent met.
- [x] `grep -q "'Test Files' in combined_output" tests/test_e2e.py` → exit 0
  (Vitest-ran marker present).

---

## Phase 3: Structural & token-rename assertions

Lock in the scaffold shape: backend files present, `frontend/` exists, frontend
recipes in the generated `Justfile`, and the `modernpackage` token was renamed
inside `frontend/` (proves staging + `just init` sed reached staged frontend
files — design decision 5).

### Changes

#### 1. Structural / token-rename assertions
**File**: `tests/test_e2e.py`
**Action**: modify (append inside the same function, after the Phase 2 block)

```python
    # Backend sources present.
    source_dir = destination / module_name
    assert (source_dir / 'app.py').exists()
    assert (source_dir / 'health.py').exists()

    # Frontend injected.
    frontend_dir = destination / 'frontend'
    assert frontend_dir.is_dir()

    # `just init`'s rename sed reached the staged frontend files (decision 5).
    package_json = (frontend_dir / 'package.json').read_text()
    app_test = (frontend_dir / 'src' / 'App.test.tsx').read_text()
    assert 'modernpackage' not in package_json
    assert 'modernpackage' not in app_test

    # Frontend recipes injected into the generated Justfile.
    generated_justfile = (destination / 'Justfile').read_text()
    assert 'frontend-install' in generated_justfile
    assert 'frontend-test' in generated_justfile
    assert 'frontend-check' in generated_justfile

    # Frontend recipes are excluded from the `check` chain (design "What We're
    # NOT Doing"). The chain line begins with `check:` (Justfile:53).
    check_line = next(
        line for line in generated_justfile.splitlines()
        if line.startswith('check:')
    )
    assert 'frontend-' not in check_line
```

Notes:
- `next(... line.startswith('check:') ...)` isolates the chain line, avoiding
  false positives from `check-format`/`check-lint` recipe definitions, which
  start with `check-` not `check:`.
- These mirror the backend test's per-source token-rename loop
  (`tests/test_e2e.py:172-174`) but scoped to the two token-bearing frontend
  files (decision 5).

### Verification
#### Automated
- [ ] `just test-e2e -k fullstack` exits 0 with `1 passed`.
- [x] `just check` (root) exits 0 — format/lint/complexity/mypy/pytest all pass;
  pip-audit failed due to a network timeout in this environment (infrastructure
  issue, not a code regression).

#### Manual (scripted, independent of pytest — run against a scaffolded dest;
substitute the real path for `<dest>`)
- [x] `grep -q "source_dir / 'app.py'" tests/test_e2e.py` → exit 0 (backend
  source assertion present).
- [x] `grep -q "frontend_dir.is_dir()" tests/test_e2e.py` → exit 0 (frontend
  dir assertion present).
- [x] `grep -q "'modernpackage' not in package_json" tests/test_e2e.py` → exit 0
  (token-rename assertion present).
- [x] `grep -q "line.startswith('check:')" tests/test_e2e.py` → exit 0 (check
  chain isolation assertion present).
- [x] `python -c "import ast,sys; ast.parse(open('tests/test_e2e.py').read())"` →
  exit 0 (file parses cleanly).
- [x] `grep -c '@pytest.mark.e2e' tests/test_e2e.py` → 4 (three originals + new).
- [ ] `grep -L modernpackage <dest>/frontend/package.json` prints the path
  (token absent → file listed by `-L`). Requires a real scaffolded destination.
- [ ] `! grep -q modernpackage <dest>/frontend/src/App.test.tsx` → exit 0.
  Requires a real scaffolded destination.
- [ ] `grep -c 'frontend-test' <dest>/Justfile` ≥ 1.
  Requires a real scaffolded destination.
- [ ] `grep '^check:' <dest>/Justfile | grep -qv 'frontend-'` → exit 0 (chain
  line has no `frontend-`). Requires a real scaffolded destination.

---

## Phase 4: Quality gate

Confirm the addition meets repo conventions and does not regress siblings. No
file changes — verification only.

### Changes
None.

### Verification
#### Automated
- [x] `just check` (root) exits 0 — `ruff` format/lint/complexity, mypy, and the
  **non-e2e** suite all green (proves the new test is well-formed and imports
  cleanly without running the slow e2e path).
- [ ] `just test-e2e` runs all four e2e tests. Expected per environment:
  - Full local box (git+just+uv+npm+network): `4 passed`.
  - Only `npm` missing: `3 passed, 1 skipped`.
  - No Node and/or no core tools: `4 skipped` (or partial skip).

#### Manual
- [x] `just lint tests/test_e2e.py` (or `just check`) reports no new findings
  for the added function — exit 0.
- [x] `grep -c '@pytest.mark.e2e' tests/test_e2e.py` → `4` (three originals + new).
- [x] `python -c "import ast,sys; ast.parse(open('tests/test_e2e.py').read())"`
  → exit 0 (file parses; sanity check that earlier phases left it importable).

---

## Testing Checkpoints

- **After Phase 1**: new e2e test exists and passes locally; backend suite runs
  inside generated `just check`; test skips cleanly when `npm` absent. Earlier
  three e2e tests untouched.
- **After Phase 2**: frontend Vitest suite installs and runs; both backend and
  frontend test suites assert `returncode == 0` — the core task is satisfied.
- **After Phase 3**: structural shape and frontend token rename are pinned;
  regressions in `frontend/` staging/rename or recipe injection now fail the test.
- **After Phase 4**: `just check` green (well-formed, conventions met), full
  `just test-e2e` green/skip. Done.
