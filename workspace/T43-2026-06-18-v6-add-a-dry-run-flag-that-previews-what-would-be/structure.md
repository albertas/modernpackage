# Structure Outline

## Approach

Add a `--dry-run` boolean flag (modeled on `--version`) that, after the existing
read-only preflight, short-circuits `init_new_package` **before the first
mutation** (`git clone`, `main.py:617`): it prints a static, high-level plan to
stdout and returns 0 without cloning, rewriting metadata, or invoking any
scaffolding subprocess. Two vertical slices: (1) wire the flag end-to-end so the
abort path works, (2) enrich the printed plan to full fidelity.

---

## Phase 1: Wire `--dry-run` end-to-end (flag → abort path)

Adds the flag, threads it through every layer, and makes a dry-run run preflight
then exit 0 emitting a minimal plan — crucially performing **zero** clone/init/check
subprocesses. This is the load-bearing safety guarantee; the plan text can be
minimal here.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `parse_args`: add `--dry-run`, `action='store_true', default=False`
  (alongside `--version`, `main.py:350-356`). Maps to `arguments.dry_run`.
- `init_new_package(package_name, *, ..., dry_run: bool = False) -> int` — new
  keyword-only, defaulted param appended to the existing signature
  (`main.py:602-610`).
- `main`: pass `dry_run=parsed_args.dry_run` into `init_new_package`
  (`main.py:691-698`).
- Branch inside `init_new_package` *after* `_run_preflight_checks(...)`
  (`main.py:615`) and *before* the clone (`main.py:617`):
  `if dry_run: _print_dry_run_plan(...); return 0`. (Phase 1 may inline a
  one-line plan; Phase 2 replaces the body.)

**Verify**: `just test` passes. Add a unit test mirroring the abort assertion at
`test_main.py:385`: patch `modernpackage.main.Popen` + `modernpackage.main.run`
(seam at `test_main.py:286-294`), invoke `init_new_package('foo', dry_run=True)`,
assert return value `== 0` and `popen_mock.call_count == 0` (no clone/init/check).
Add a `parse_args` test patching `sys.argv` to `['modernpackage', 'foo', '--dry-run']`
(pattern `test_main.py:108-118`) asserting `arguments.dry_run is True` and that it
defaults `False` without the flag. Add a `main`-threading test patching
`ArgumentParser` + `init_new_package` (pattern `test_main.py:502-525`) asserting
`dry_run=True` reaches the call.

---

## Phase 2: Full preview plan content

Replaces the minimal plan with a complete, stable preview describing what a real
run would do, reported from the already-resolved metadata. Builds on Phase 1's
wiring; if it fails, Phase 1 still delivers a working, safe dry-run.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `_DRY_RUN_HEADER: str = 'Dry run — no changes will be made:'` — new module
  constant alongside `_PREFLIGHT_HEADER` (`main.py:504`).
- `_format_dry_run_plan(module_name: str, target_path: Path, *, author_name, author_email, description, package_license, repository_url) -> str`
  — new private helper returning the multi-line plan string; reuses the
  two-space-indent aesthetic of `_format_check_line` (`main.py:507-510`).
- `_print_dry_run_plan(...) -> None` — prints the formatted plan to stdout via
  `print(...)  # noqa: T201` (output convention, `main.py:592, 672`).
- Plan reports, at the level the code actually knows (design Decision 3):
  - target directory (`new_package_path`) and the template URL it would clone
    (`_TEMPLATE_REPOSITORY_URL`);
  - the `pyproject.toml` metadata substitutions for each non-`None` field
    (`_write_package_metadata` literals, research §Q3); `None` fields reported as
    "keeps template default";
  - the well-known `just init` outcomes: rename `modernpackage/ → <module>/` and
    version reset to `0.0.1`.

**Verify**: `just test` passes. Add a unit test for `_format_dry_run_plan` asserting
the returned string contains the target path, template URL, each supplied metadata
value, "keeps template default" for omitted fields, and the
`modernpackage/ → foo/` + `0.0.1` lines. Add a `capsys`-based test on
`init_new_package('foo', dry_run=True, author_name='Ada')` asserting the captured
stdout contains the header and the resolved author value (own test, not the exact-
stdout assertions at `test_main.py:641-665`, to avoid brittle coupling).

---

## Testing Checkpoints

- **After Phase 1**: `modernpackage foo --dry-run` returns 0 and performs no
  clone/init/check (`popen_mock.call_count == 0`); `parse_args` exposes
  `dry_run`; `main` threads it. Preflight still runs (failures still return 1 via
  the existing `RuntimeError` path in `main`, `main.py:699-701`). `just check`
  green. The safety guarantee (no mutation) holds independently of plan content.
- **After Phase 2**: stdout shows a complete, stable plan — target dir, template
  URL, per-field metadata substitutions (with `None` → template default), and the
  rename + version-reset outcomes — covered by its own dedicated test. `just check`
  green.

**Note / inherited risk** (design Open Risks): dry-run still issues the
`git ls-remote` network probe via preflight (`main.py:546-552`). This is by design
(Decision 2) — it surfaces a genuinely unreachable remote — but means a fully
unattended/offline live invocation returns 1, not 0. The primary verification gates
are therefore the unit tests with `run`/`Popen` patched, not a live network probe.
