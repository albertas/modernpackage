# Design Discussion

## Current State

The precedence behaviour the task asks for **already exists and is correct**;
what is missing is a *single, explicit rule*. Today the order is an emergent
property of where statements happen to sit in `parse_args()`.

- `parse_args()` is the sole orchestrator (`modernpackage/main.py:290-369`).
- Every metadata flag is declared with `default=None` (`main.py:306-347`), then
  filled in three hand-written blocks, each gated by `if <field> is None:`:
  1. Environment — five lines, one per field (`main.py:349-358`).
  2. Git config — two lines, author_name + author_email only (`main.py:359-362`).
  3. Config file — `_apply_config_file_defaults` repeats five more `if … is None`
     lines (`main.py:264-273`), called once at `main.py:363`.
- Net effect per field: **flag > env > git config > config file > None**. The
  `None` guard is the *only* mechanism enforcing precedence; the source order
  *is* the precedence (research Cross-Cutting Observations).
- The three readers share one "empty/missing/wrong-typed = unset (`None`)"
  convention: `_environment_default` (`main.py:172-174`), `_git_config_default`
  (`main.py:177-197`), `_config_file_default` (`main.py:243-253`).
- Validation runs once on the final resolved value, source-agnostic
  (`_validated_or_error`, `main.py:364-369`).
- Asymmetry: git config backs only the two author fields; the other three get a
  3-level ladder. This is encoded *structurally* (two git lines vs. five) rather
  than declaratively (research Q3).

**Problems this creates:**
- The rule is duplicated across ~14 near-identical `if x is None` lines in two
  functions; adding a field or source means editing several disconnected spots.
- The ordering is implied, not stated — a reader must trace statement order to
  recover it.
- Documentation drifted from behaviour: `--help` advertises only the env var,
  not git/config (`main.py:308-346`); `docs/specification.md:44-48` predates the
  metadata feature; `docs/invocation.md:421` falsely says metadata is not written
  to `pyproject.toml` (research Q5).

## Desired End State

A single declarative description of the precedence ladder that every field and
source is resolved through, plus documentation that matches it.

1. **One precedence rule, data-driven.** A field-descriptor table declares, per
   field, the ordered list of sources that may supply it. A single resolution
   pass walks the table — no per-field `if x is None` blocks scattered through
   `parse_args()`.
2. **The asymmetry is declared, not structural.** A field that has no git source
   simply omits it from its descriptor; the resolver needs no special-casing.
3. **Behaviour is unchanged and provable.** All existing tests in
   `tests/test_main.py` (the `_beats_`/`_overrides_`/`_fills_when_` suite,
   research Q4) pass without modification.
4. **Docs and `--help` state the full ladder consistently.**

**Verification:** `just test` and `just check` pass; existing precedence tests
are green unmodified; `--help` and the three live docs all describe
`flag > env > git config > config file > None` (and the 3-level variant) with no
contradictions.

## Patterns to Follow

- **Module-private `_`-prefixed helpers and `_RE`/`_KEY` constants** already in
  `main.py` (`main.py:87-104`, `_apply_config_file_defaults` at `:256`). New
  descriptor + resolver should be `_`-prefixed module-private symbols.
- **`@dataclass(frozen=True)` for immutable records** (Code Best Practices,
  "Data structures") — the field descriptor is a natural frozen dataclass with
  inline `#`-commented fields.
- **Shared "empty/missing/wrong-type = unset" convention** — reuse the existing
  three readers unchanged (`main.py:172-197`, `:243-253`); the resolver calls
  them, it does not replace them.
- **Source-agnostic validation after resolution** — keep `_validated_or_error`
  applied once to the final value (`main.py:364-369`); do not move validation
  into the per-source readers.
- **Test seams**: patch `modernpackage.main._git_config_default`, use
  `monkeypatch.setenv/delenv`, `_write_config`/`_parse_args_with_config`
  helpers (`test_main.py:635-657`) — the refactor must keep these seams intact
  (the resolver must still call `_git_config_default` by the same name so
  `side_effect` stubs and "loser never consulted" assertions at
  `test_main.py:553-556` keep working).

**Pattern to NOT follow / avoid introducing:**
- Do **not** keep the duplicated `if x is None` ladder — that is the very thing
  being replaced (`main.py:349-362`, `:264-273`).
- Do **not** over-engineer: no plugin registry, no runtime-configurable source
  order, no abstraction for sources that don't exist (CLAUDE.md §2). The order
  is fixed and known.
- Do **not** broaden git config to the three non-author fields — there are no
  git keys for them and none should be invented (research Open Areas).

## Design Decisions

1. **Field-descriptor table + single resolver** (chosen over a priority-number
   table or a generic source registry): a tuple of frozen `_MetadataField`
   records, each naming its namespace attr, env var, optional git key, and config
   key. One loop resolves all fields. Simplest structure that makes the rule
   single and consistently applied without speculative flexibility.

2. **Sources modelled as an ordered per-field list, resolved first-non-None.**
   The canonical order (env → git → config) lives in how each descriptor is
   built; the resolver just tries them top-to-bottom and stops at the first
   non-`None`. Flag values are already in the namespace and win implicitly
   (resolver only fills when the attr is still `None`), preserving today's
   semantics exactly.

3. **Omission encodes asymmetry.** Non-author fields set their git key to `None`
   in the descriptor; the resolver skips a `None` source. No branching on field
   identity. Replaces the structural two-lines-vs-five asymmetry (research Q3).

4. **Reuse the three existing readers verbatim.** `_environment_default`,
   `_git_config_default`, `_config_file_default` keep their names and signatures
   so existing test stubs and the "loser never consulted" assertions still hold.
   The config file is still loaded exactly once and passed to the resolver.

5. **Validation stays where it is** — once, on the final value, after resolution
   (`main.py:364-369`). Not folded into the resolver or readers; keeps it
   source-agnostic and the exit-code-2 tests (research Q4) unchanged.

6. **Documentation brought in line as part of this task.** Update `--help` text
   to mention the full ladder, refresh `docs/specification.md:44-48`, and fix the
   stale `docs/invocation.md:421` paragraph. The task explicitly requires the
   rule be "documented" and "consistently applied", so doc consistency is in
   scope (judgment call — research Q5 flagged the three inconsistencies).

7. **Keep the `license` ↔ `package_license` naming as-is.** The flag attr is
   `license`; downstream the parameter is `package_license` (`main.py:421-452`).
   Renaming is out of scope and would touch unrelated code (CLAUDE.md §3).

## What We're NOT Doing

- Not changing the resolved precedence order or any field's observable result.
- Not adding new metadata fields, new sources, or git keys for non-author fields.
- Not touching `_write_package_metadata` / `init_new_package` flow (research Q6)
  beyond what resolution requires — it consumes the same namespace.
- Not making the source order configurable or pluggable.
- Not refactoring the readers' internals or the "unset" convention.
- Not renaming `license`/`package_license`.

## Open Risks

- **Test seam fragility:** tests assert specific calls (e.g.
  `_GIT_CONFIG_USER_NAME_KEY` absent from `git_mock.call_args_list`,
  `test_main.py:553-556`). The resolver must call `_git_config_default` lazily —
  only when higher sources are unset — or those "never consulted" assertions
  break. Mitigation: resolve each field source-by-source, short-circuiting.
- **Config-file load timing:** today `_load_config_file()` runs once even if no
  field reaches it. Preserve single-load semantics in the resolver.
- **Doc-edit scope creep:** `docs/architecture.md`/`overview.md` already match
  reality (research Q5); only `--help`, `specification.md`, and the one stale
  `invocation.md` paragraph need edits. Resist rewriting correct docs (CLAUDE.md §3).
- **Cyclomatic complexity gate (≤10, `pyproject.toml`):** a single resolver loop
  should stay well under it, but verify with `just check`.
