# Structure Outline

## Approach

Replace the ~14 scattered `if <field> is None:` fill-in lines in `parse_args()`
and `_apply_config_file_defaults()` with one declarative `_MetadataField`
descriptor table plus a single first-non-`None` resolver. The three existing
readers (`_environment_default`, `_git_config_default`, `_config_file_default`)
and the post-resolution validation stay verbatim, so behaviour and test seams
are preserved. Then bring `--help` and the three stale docs in line with the
ladder the code actually implements.

This is a behaviour-preserving refactor, so each phase's primary verification is
that the **existing** `tests/test_main.py` precedence suite passes unmodified.

---

## Phase 1: Descriptor table + single resolver

Introduce the data-driven precedence model and rewire `parse_args()` to use it,
deleting the per-field `None`-guard ladders. Crosses data-structure → resolver →
orchestrator; observable CLI behaviour is identical.

**Files**: `modernpackage/main.py`

**Key changes**:
- `@dataclass(frozen=True) _MetadataField { attr: str; env_var: str; git_key: str | None; config_key: str }`
  — new frozen record; `git_key=None` encodes the author-only asymmetry.
- `_METADATA_FIELDS: tuple[_MetadataField, ...]` — new module-private table, one
  entry per field, sources listed in canonical order (env → git → config). The
  three non-author fields set `git_key=None`.
- `_resolve_metadata_defaults(arguments: Namespace, config: Mapping[str, object]) -> None`
  — new resolver. For each descriptor, only when `getattr(arguments, attr) is None`,
  try env → git (skip if `git_key is None`) → config, stopping at first non-`None`.
  Calls `_git_config_default` lazily (only after env is unset) to keep
  "loser never consulted" assertions valid.
- `parse_args()` — delete env block (`:349-358`), git block (`:359-362`), and the
  `_apply_config_file_defaults(...)` call (`:363`); replace with
  `_resolve_metadata_defaults(arguments, _load_config_file())`. Config file still
  loaded exactly once. Validation block (`:364-369`) unchanged.
- Remove `_apply_config_file_defaults` (orphaned by this change; its logic moves
  into the resolver).

**Verify**: `just test` passes with **zero edits** to `tests/test_main.py`
(precedence suite `:174-801`, "loser never consulted" `:553-556`/`:573-575`,
exit-code-2 tests `:611-627`/`:786-801`). `just check` passes (resolver
cyclomatic complexity ≤ 10). Confirm no `if .* is None` metadata ladder remains:
`grep -nE 'is None' modernpackage/main.py` shows no per-field metadata fill
blocks in `parse_args`.

---

## Phase 2: `--help` text states the full ladder

Update each metadata flag's help string so `--help` describes the real source
chain (env → git config → config file) instead of only the env var. Code + test.

**Files**: `modernpackage/main.py`, `tests/test_main.py`

**Key changes**:
- `parse_args()` flag `help=` strings (`:308-346`) — extend author-name/email to
  mention env var, `git config user.name`/`user.email`, and the config file;
  extend description/license/repository-url to mention env var and config file
  (no git, matching the 3-level ladder).
- `tests/test_main.py` — extend `test_parse_args_help_advertises_env_vars`
  (`:267-274`) (or add a sibling test) to assert the git-config and config-file
  mentions now appear. This is the one intended test change.

**Verify**: `just test` passes including the updated help assertion.
`modernpackage init --help` (or `python -m modernpackage --help`) output contains
the substrings `user.name`, `user.email`, and `config.toml`/"config file" for the
relevant flags. Spot-check:
`python -m modernpackage --help | grep -A2 -- '--author-name'` shows the git/config mention.

---

## Phase 3: Documentation brought in line

Fix the two stale prose docs so all written descriptions of the ladder agree with
the code. No code change.

**Files**: `docs/specification.md`, `docs/invocation.md`

**Key changes**:
- `docs/specification.md:44-48` — add the metadata flags and the precedence ladder
  (`flag > env > git config > config file > None` for author name/email;
  `flag > env > config file > None` for description/license/repository-url) to the
  stale CLI section.
- `docs/invocation.md:421` — replace the false "metadata not yet written to
  `pyproject.toml`" paragraph with the accurate statement that resolved metadata
  is written via `_write_package_metadata` before the initial commit.
- Do **not** touch `docs/overview.md` or `docs/architecture.md` (already correct —
  research Q5).

**Verify**: `just check` passes (no doc linters break). File inspection:
`grep -n 'flag > env > git config > config file' docs/specification.md` returns a
match; `grep -n 'not yet written' docs/invocation.md` returns **no** match;
`grep -rn 'flag > env' docs/overview.md docs/architecture.md` still matches
(untouched). No contradiction remains across `docs/` + `--help`.

---

## Testing Checkpoints

- **After Phase 1**: `just test` + `just check` green with an unmodified test
  file; `parse_args()` contains no per-field `if x is None` metadata ladder; one
  resolver walks `_METADATA_FIELDS`; CLI output for every flag/env/git/config
  combination is identical to before. This phase alone delivers the core
  "single, explicit rule" the task asks for.
- **After Phase 2**: `--help` advertises the full ladder; the help test asserts
  git/config mentions. Independently valuable even if Phase 3 is skipped.
- **After Phase 3**: every written description (`--help`, `specification.md`,
  `invocation.md`, `overview.md`, `architecture.md`) agrees with the implemented
  precedence; no stale/contradictory paragraph remains.

If context resets, Phase 1 is the only behaviour-bearing change; Phases 2–3 are
documentation alignment and can be verified independently by the greps above.
