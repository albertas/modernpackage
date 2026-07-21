# Research Findings

Scope: the preflight-check layer of the package-initialization flow in
`modernpackage/main.py`, its tests in `tests/test_main.py`, and the docs under
`docs/`. All references are `file:line`.

## Q1: End-to-end control flow of `init_new_package` and where the preflight step sits

### Findings
- `init_new_package` is defined at `modernpackage/main.py:1032` and returns `int`.
- Step order inside the function:
  1. `module_name = normalize_module_name(package_name)` — `main.py:1045`
  2. `new_package_path = Path.cwd() / module_name` — `main.py:1046`
  3. **Preflight**: `_run_preflight_checks(new_package_path)` — `main.py:1048` (runs before any subprocess/filesystem mutation).
  4. Dry-run short-circuit: if `dry_run`, `_print_dry_run_plan(...)` then `return 0` — `main.py:1050-1062`.
  5. `git clone` via `Popen` — `main.py:1064-1077` (failure handling at 1073-1077).
  6. `_write_package_metadata(...)` — `main.py:1079-1086`.
  7. `_strip_scaffolding(...)` — `main.py:1088`.
  8. `if backend or fullstack: _inject_templates(...)` — `main.py:1090-1091`.
  9. `just init` via `Popen` (with `FileNotFoundError` guard) — `main.py:1093-1112`.
  10. `just check` streamed live (no PIPE) + summary/next-steps — `main.py:1114-1145`.
- The preflight checklist itself is invoked by `_run_preflight_checks` (`main.py:880-906`):
  - Builds a per-call tuple of four `PreflightCheck` instances — `main.py:887-898`.
  - The registry is built per-call so `_verify_target_directory_absent` can bind `target_path` via closure — `main.py:884-886, 893-896`.
  - Prints `_PREFLIGHT_HEADER` (`main.py:899`), then loops: runs each `check.run()`; on `RuntimeError` prints a `[FAIL]` line and re-raises (`main.py:901-905`); otherwise prints an `[ok]` line (`main.py:906`).
- The four checks in order (`main.py:888-897`): `package name valid` (a no-op `lambda: None`, display-only since argparse already validated), `required tools on PATH` (`_verify_required_tools`), `target directory available` (`_verify_target_directory_absent`), `template remote reachable` (`_verify_template_remote_reachable`).
- `main()` (`main.py:1148`) calls `init_new_package` and catches `RuntimeError` to print to stderr and return 1 — `main.py:1156-1170`.

## Q2: Preflight helper functions and module-level constants; shared vs. preflight-only

### Findings
- `PreflightCheck` dataclass (`frozen=True`) — `main.py:664-671`; fields `label` and `run` (a `Callable[[], None]`). **Preflight-only** (only used in `_run_preflight_checks`).
- `_run_preflight_checks(target_path)` — `main.py:880-906`. **Preflight-only**; called from `init_new_package:1048`.
- Verifiers (all **preflight-only**):
  - `_verify_required_tools()` — `main.py:820-831`; uses `shutil.which` over `_REQUIRED_TOOLS`, builds hint text from `_TOOL_INSTALL_HINTS`.
  - `_verify_target_directory_absent(target_path)` — `main.py:834-841`.
  - `_verify_template_remote_reachable()` — `main.py:844-877`; runs `git ls-remote`, bounded by `_REMOTE_REACHABILITY_TIMEOUT_SECONDS`, classifies stderr via `humanize_git_clone_error`.
- Constants:
  - `_REQUIRED_TOOLS` — `main.py:56`. Referenced by `_verify_required_tools:822` and by the check label at `main.py:890`. **Preflight-only.**
  - `_TOOL_INSTALL_HINTS` — `main.py:62-66`. Only `_verify_required_tools:829`. **Preflight-only.**
  - `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` — `main.py:75`. Only `_verify_template_remote_reachable:858, 864`. **Preflight-only.**
  - `_PREFLIGHT_HEADER` — `main.py:674`. Only `_run_preflight_checks:899`. **Preflight-only.**
- **Shared** helpers/constants (used by preflight AND elsewhere):
  - `humanize_git_clone_error` — `main.py:78-84`. Used by preflight `_verify_template_remote_reachable:875` AND by the real clone path `init_new_package:1075`. Backed by `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20-52`).
  - `_TEMPLATE_REPOSITORY_URL` — `main.py:71`. Used by preflight probe (`:854`), the clone (`:1065`), metadata replacement (`_write_package_metadata:486`), and dry-run plan (`_format_dry_run_plan:738`).
  - `_format_check_line` — `main.py:701-707`. Only called by preflight (`_run_preflight_checks:904, 906`) but itself calls the shared `_green` (`:706`). See Q6.
  - `_green` / `_color_enabled` — `main.py:685-698`. Shared: used by `_format_check_line:706` and by the success/summary output in `init_new_package:1132-1133`.

## Q3: Clone and `just init` failure handling, independent of preflight

### Findings
- **git clone failure**: after `pipe.communicate()`, non-zero `returncode` builds a raw message, runs `humanize_git_clone_error(stderr_text)`, and raises `RuntimeError` combining friendly + raw — `main.py:1070-1077`.
- **`humanize_git_clone_error`** (`main.py:78-84`) walks `_GIT_CLONE_ERROR_MESSAGES` (`main.py:20-52`), ordered most-specific-first; categories: network unreachable, repo not found, auth failure, `already exists and is not an empty directory`, broad filesystem permission. Returns first match or `None`.
- **missing `just` executable**: `Popen(['just', 'init', module_name], ...)` wrapped in `try/except FileNotFoundError`, raising a `RuntimeError` pointing to the install page — `main.py:1093-1106`.
- **`just init` non-zero exit**: raises `RuntimeError` with exit code + stderr — `main.py:1110-1112`.
- **existing-directory conditions**: handled in TWO independent places —
  - Preflight `_verify_target_directory_absent` (`main.py:834-841`) fires before any subprocess.
  - The clone-time variant is matched by `_GIT_CLONE_ERROR_MESSAGES` at `main.py:43-46` (`already exists and is not an empty directory` → "destination directory already exists — choose a different package name").
- **`just check`** is a separate final phase; it does not raise but returns exit code 1 with a stderr notice when it fails — `main.py:1140-1145`.

## Q4: Test coverage of preflight behavior in `tests/test_main.py`

### Findings
- `_verify_required_tools` tests: `test_verify_required_tools_missing_git` (`test_main.py:421`), `_missing_just` (`:436`), `_missing_uv` (`:451`), `_all_present` (`:466`, asserts `which` call count == `len(_REQUIRED_TOOLS)`), `_reports_all_missing` (`:474`), and three install-hint tests `_hint_points_at_git/uv/just_install_docs` (`:493, :508, :523`), `_lists_all_install_hints_when_all_missing` (`:538`).
- `_verify_target_directory_absent` tests: `test_init_new_package_aborts_when_target_directory_exists` (`:1401`), `_proceeds_when_target_directory_absent` (`:1417`), `test_verify_target_directory_absent_raises_when_exists` (`:1435`), `_passes_when_absent` (`:1442`).
- `_verify_template_remote_reachable` tests: `_returns_none_when_reachable` (`:1447`), `_raises_on_resolve_host` (`:1453`), `_raises_on_repo_not_found` (`:1466`), `_raises_on_timeout` (`:1478`), plus integration `test_init_new_package_aborts_when_remote_unreachable` (`:832`).
- Full-checklist output tests (via `init_new_package` + `capsys`): `test_run_preflight_checks_prints_full_checklist_on_clean_run` (`:732`, asserts header + all four `[ok]` lines in order), `_marks_failing_check_and_aborts` (`:845`), `_aborts_on_earlier_check_without_later_lines` (`:867`, asserts later check lines absent).
- Fixtures/helpers used: `capsys` (`:732, 845, 867, 1898...`), `tmp_path` (`:1401, 1417, 1435, 1442`), `monkeypatch` (`chdir` at `:1401, 1417`; `isatty`/`NO_COLOR` at `:1879-1927`). Patch seams: `modernpackage.main.shutil.which`, `.Popen` (assert `call_count == 0` on abort), `.run` (mock `git ls-remote`), `._strip_scaffolding`. No `_`-prefixed seed helpers are used by preflight tests (`_seed_pyproject:1218`, `_seed_clone:1324` are used only by metadata/inject tests).
- **Shared-helper assertions**: `_format_check_line` is tested both indirectly (preflight stdout at `:732, 845, 867`) and directly (`test_check_line_ok_is_green_on_tty:1898`, `_ok_is_plain_off_tty:1906`, `_fail_is_never_green:1913`). `_green` / `_color_enabled` tested only in non-preflight direct tests (`:1879-1895`). `humanize_git_clone_error` tested directly in five standalone tests (`:644-677`) plus clone-path integration (`:813-827`) — not inside preflight tests.
- **Clone/`just init` failure tests (independent of preflight)**: `test_init_new_package_git_clone_failure` (`:376`), `_git_clone_network_failure` (`:813`), `_just_not_installed` (`:388`, matches `r'just.*install'`), `_just_init_failure` (`:403`). Five `humanize_git_clone_error` unit tests at `:644, 649, 658, 665, 675`.

## Q5: Documentation coverage of preflight in `docs/`

### Findings
- **`invocation.md`**: dedicated section "Preflight checks and checklist" at `docs/invocation.md:398-505`; states preflight runs "Before any subprocess is spawned or any directory is created" (`:400`), lists the four checks in order (`:425-430`), and that failure prints up to the failing `[FAIL]` line and aborts before clone (`:434-435`). Dry-run runs preflight first (`:53, :60, :144`); literal `[ok]` output blocks at `:70-74, :95-99, :123-127`. Clone occurs "only after the preflight check has passed" (`:509`).
- **`overview.md`**: inline sequence at `:7` (name valid → tools on PATH → directory absent → clone); "Preflight checks with checklist" bullets at `:15-16` ("Before any git clone or filesystem mutation") and `:63-67` (names `_run_preflight_checks`, `_verify_required_tools`, `_verify_target_directory_absent`, `_verify_template_remote_reachable`).
- **`architecture.md`**: constant docs `_PREFLIGHT_HEADER` (`:84-91`), `_REMOTE_REACHABILITY_TIMEOUT_SECONDS` (`:73-82`); verifier function docs (`_verify_required_tools:412-445`, `_verify_target_directory_absent:447-469`, `_verify_template_remote_reachable:471-497`); `PreflightCheck` dataclass (`:499-514`); `_run_preflight_checks` (`:673-722`, incl. "Integration with `init_new_package()`" at `:718-722`). Step-numbered flow: "Step 0: Preflight checks & checklist" (`:1345-1350`), "Step 0.5: Dry-run short-circuit" (`:1351`), "Step 1: Clone" (`:1352`).
- **`data_flows.md`**: index row `:29`; "Step 4: Preflight Checks" (`:57-80`) enumerating the three verifiers with `shutil.which`, `Path.exists`, `git ls-remote` + timeout + `humanize_git_clone_error`; Step 4.5 dry-run (`:82`), Step 5 git clone (`:104`). Most explicit sequential placement (preflight between target-path compute and clone).
- **`specification.md`**: 8-step `init_new_package` list at `:60-74`; step 2 = "Runs preflight checks (tools on PATH, target directory absent, template reachable)" before `git clone` (step 3).
- **`vision.md`**: section heading "V5 — Preflight environment checks before cloning" (`:48-55`).
- No preflight mentions in `fastapi_backend.md`, `reactjs_frontend.md`, `containerization.md`, `backlog_formats.md`, `persona.md`.

## Q6: stdout formatting/colorization and which helpers extend beyond preflight

### Findings
- `_color_enabled()` — `main.py:685-691`: true only when `sys.stdout.isatty()` and `NO_COLOR` unset. Never raises.
- `_green(text)` — `main.py:694-698`: wraps in `_ANSI_GREEN`/`_ANSI_RESET` (`main.py:681-682`) when color enabled. **Used beyond preflight**: success line in `init_new_package:1132-1133` (`just check passed`, `scaffold is valid`).
- `_format_check_line(label, *, ok)` — `main.py:701-707`: marker `[ok]`/`[FAIL]` padded to 6 chars; greens the marker when `ok`. Preflight-only caller (`_run_preflight_checks:904, 906`) but depends on shared `_green`.
- Dry-run block: `_format_dry_run_plan` (`main.py:710-754`) + `_print_dry_run_plan` (`:757-782`); header `_DRY_RUN_HEADER` (`:675`); plain text, no color.
- Summary block: `_format_init_summary` / `_print_init_summary` (`main.py:785-802`); header `_INIT_SUMMARY_HEADER` (`:679`); uses `_RESET_VERSION` (`:678`). Plain text.
- Next-steps block: `_format_next_commands` / `_print_next_commands` (`main.py:805-817`); header `_NEXT_COMMANDS_HEADER` (`:680`). Plain text.
- Color helpers (`_green`/`_color_enabled`) are the only formatting helpers shared across preflight and non-preflight output. `_format_check_line`, dry-run, summary, and next-steps formatters are each single-purpose.

## Cross-Cutting Observations
- Preflight is a distinct "Step 0" layer: a per-call registry of `PreflightCheck` records (`main.py:887-898`) run before any subprocess or filesystem mutation, aborting fail-fast on the first `RuntimeError`.
- Two constants/helpers straddle the preflight boundary and are reused by the real clone path: `humanize_git_clone_error` (+`_GIT_CLONE_ERROR_MESSAGES`) and `_TEMPLATE_REPOSITORY_URL`. The `git ls-remote` probe deliberately reuses the same error classifier as the clone (`main.py:875` and `:1075`).
- Color output goes through one shared path (`_green`/`_color_enabled`) used by both the preflight checklist marker and the post-`just check` success line.
- Existing-directory failure is defended in two independent spots: preflight `_verify_target_directory_absent` and the clone-time regex in `_GIT_CLONE_ERROR_MESSAGES:43-46`.
- All five documentation files that enumerate the flow agree on the same fixed order and the same four preflight checks; the term "V5" (`vision.md:48`) frames preflight as an added milestone.

## Open Areas
- The `package name valid` check is a display-only `lambda: None` (`main.py:888`); real validation happens at argparse time via `validate_package_name` (`main.py:183`). Docs note this (`invocation.md:425-430`), so removing preflight display does not remove name validation.
- No question probed the `tests_e2e/` end-to-end suite; it was not analyzed here.
