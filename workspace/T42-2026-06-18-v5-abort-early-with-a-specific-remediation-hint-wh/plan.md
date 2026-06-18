# Implementation Plan

## Overview

Close the hint-quality gap in the scaffolding CLI's fail-fast preflight: when
required tools are missing, `_verify_required_tools` must emit a per-tool install
URL (git → git's docs, uv → uv's docs, just → just's docs) instead of always
pointing at just's install page, while preserving the existing abort-before-clone
guarantee and all current test substrings.

Both phases touch only the CLI/preflight layer. There is no DB/API/UI. Phase 1 is
the behavior change (constant + verifier body) and is functionally complete on its
own. Phase 2 adds per-tool/all-missing regression tests.

---

## Phase 1: Per-tool install hints in `_verify_required_tools`

### Changes

#### 1. Add the install-hint table

**File**: `modernpackage/main.py`
**Action**: modify

Add a module-level constant immediately after `_REQUIRED_TOOLS` (currently
`main.py:56`), modeled on `_GIT_CLONE_ERROR_MESSAGES` (`main.py:19-52`). Keep the
existing just URL verbatim (`main.py:510`) so the link does not drift.

```python
# Required executables that must resolve on PATH before scaffolding begins.
_REQUIRED_TOOLS: tuple[str, ...] = ('git', 'just', 'uv')


# Canonical install page per required tool, surfaced as a remediation hint when
# the tool is missing from PATH. Keyed by tool name; iteration order is driven by
# `_REQUIRED_TOOLS`/`missing`, not by this dict.
_TOOL_INSTALL_HINTS: dict[str, str] = {
    'git': 'https://git-scm.com/downloads',
    'just': 'https://github.com/casey/just#installation',
    'uv': 'https://docs.astral.sh/uv/getting-started/installation/',
}
```

#### 2. Rewrite the verifier body

**File**: `modernpackage/main.py`
**Action**: modify (`main.py:503-512`)

Same signature and contract (silent on success, `RuntimeError` on failure). The
header keeps the substrings `install` and the joined tool names so existing
assertions (`test_main.py:439-441`) stay green; one indented line per missing
tool carries its specific URL. Iteration is over `missing` (already ordered by
`_REQUIRED_TOOLS`), not over the dict.

```python
def _verify_required_tools() -> None:
    """Raise RuntimeError if any required executable is absent from PATH."""
    missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        header = (
            f'required tool(s) not found on PATH: {", ".join(missing)}'
            ' — install the missing tool(s) before scaffolding:'
        )
        hints = ''.join(
            f'\n  - {tool}: {_TOOL_INSTALL_HINTS[tool]}' for tool in missing
        )
        raise RuntimeError(header + hints)
```

Notes / assumptions:
- The git/uv URLs are authored (design Decision 5 flags them as judgment calls):
  `git` → `https://git-scm.com/downloads`, `uv` →
  `https://docs.astral.sh/uv/getting-started/installation/`. These are the
  official canonical install pages.
- The word `install` is retained in the header so
  `test_verify_required_tools_reports_all_missing` (`test_main.py:441`) still
  passes.
- No other verifier, the checklist format (`_format_check_line`), check ordering,
  exit codes, or post-clone steps change.

### Verification

#### Automated
- [x] `just check` passes (format + lint + complexity + typecheck + test + audit).
- [x] Existing required-tools tests still pass unchanged:
  `cd /home/niekas/tools/modernpackage && uv run pytest tests/test_main.py -k "required_tools" -q`
  exits 0 (covers the `git`/`uv`/`just`/`install` substring matches at
  `test_main.py:373-442`).

#### Manual
- [x] Per-tool hint, only-uv-missing case prints `OK` (uv hint present, git/just
  URLs absent):
  ```bash
  cd /home/niekas/tools/modernpackage && uv run python -c "
  import unittest.mock as m, modernpackage.main as M
  with m.patch.object(M.shutil, 'which', side_effect=lambda t: None if t == 'uv' else '/x'):
      try:
          M._verify_required_tools()
      except RuntimeError as e:
          s = str(e)
          assert 'docs.astral.sh/uv' in s, s
          assert 'git-scm.com' not in s, s
          assert 'casey/just' not in s, s
          print('OK')
  "
  ```
- [x] All-missing case lists all three URLs, one line per tool:
  ```bash
  cd /home/niekas/tools/modernpackage && uv run python -c "
  import unittest.mock as m, modernpackage.main as M
  with m.patch.object(M.shutil, 'which', return_value=None):
      try:
          M._verify_required_tools()
      except RuntimeError as e:
          s = str(e)
          assert 'git-scm.com/downloads' in s, s
          assert 'docs.astral.sh/uv' in s, s
          assert 'github.com/casey/just#installation' in s, s
          assert s.count(chr(10) + '  - ') == 3, s
          print('OK')
  "
  ```

---

## Phase 2: Per-tool URL test coverage + multi-missing regression guard

### Changes

#### 1. Add per-tool and all-missing unit tests

**File**: `tests/test_main.py`
**Action**: modify (insert new `def test_*` functions immediately after
`test_verify_required_tools_reports_all_missing`, `test_main.py:442`)

Mirror the existing seam: patch `modernpackage.main.shutil.which` with a
`side_effect` returning `None` for the targeted tool, raise via the verifier, and
inspect `str(exc_info.value)` for the correct URL fragment plus the absence of the
others. Use plain `assert`, top-level functions, no classes (Code Best Practices,
Testing). `_verify_required_tools` is already imported (`test_main.py:18`); no new
imports are required.

```python
def test_verify_required_tools_hint_points_at_git_install_docs() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'git' else f'/usr/bin/{tool}'

    with patch('modernpackage.main.shutil.which', side_effect=which):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_required_tools()
    message = str(exc_info.value)
    assert 'git-scm.com/downloads' in message
    assert 'docs.astral.sh/uv' not in message
    assert 'github.com/casey/just#installation' not in message


def test_verify_required_tools_hint_points_at_uv_install_docs() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'uv' else f'/usr/bin/{tool}'

    with patch('modernpackage.main.shutil.which', side_effect=which):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_required_tools()
    message = str(exc_info.value)
    assert 'docs.astral.sh/uv' in message
    assert 'git-scm.com/downloads' not in message
    assert 'github.com/casey/just#installation' not in message


def test_verify_required_tools_hint_points_at_just_install_docs() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'just' else f'/usr/bin/{tool}'

    with patch('modernpackage.main.shutil.which', side_effect=which):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_required_tools()
    message = str(exc_info.value)
    assert 'github.com/casey/just#installation' in message
    assert 'git-scm.com/downloads' not in message
    assert 'docs.astral.sh/uv' not in message


def test_verify_required_tools_lists_all_install_hints_when_all_missing() -> None:
    with patch('modernpackage.main.shutil.which', return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            _verify_required_tools()
    message = str(exc_info.value)
    assert 'git-scm.com/downloads' in message
    assert 'docs.astral.sh/uv' in message
    assert 'github.com/casey/just#installation' in message
```

Notes / assumptions:
- These call `_verify_required_tools()` directly (no `Popen`/`run` patching),
  following the `test_verify_required_tools_all_present` pattern
  (`test_main.py:418-423`) rather than the `init_new_package` integration shape;
  the abort-before-mutation guarantee is already covered by the existing
  `popen_mock.call_count == 0` tests and is re-verified below.
- The `just`-missing message contains the substring `just` in both the tool name
  and the URL; asserting on the full URL `github.com/casey/just#installation`
  keeps the per-tool assertion unambiguous.

### Verification

#### Automated
- [x] `just check` passes.
- [x] The four new tests are collected and pass:
  `cd /home/niekas/tools/modernpackage && uv run pytest tests/test_main.py -k "required_tools or hint" -q`
  exits 0.
- [x] Abort-early guard intact:
  `cd /home/niekas/tools/modernpackage && uv run pytest tests/test_main.py -k "aborts or reports_all_missing" -q`
  exits 0 (confirms the `popen_mock.call_count == 0` paths at
  `test_main.py:373-442`, `654-664`, `1146-1159` are unaffected).
- [x] Full suite green:
  `cd /home/niekas/tools/modernpackage && uv run pytest tests/test_main.py -q`
  exits 0.

#### Manual
- [x] Exactly four new test functions were added (grep returns 4):
  ```bash
  cd /home/niekas/tools/modernpackage && grep -c \
    -e 'def test_verify_required_tools_hint_points_at_git_install_docs' \
    -e 'def test_verify_required_tools_hint_points_at_uv_install_docs' \
    -e 'def test_verify_required_tools_hint_points_at_just_install_docs' \
    -e 'def test_verify_required_tools_lists_all_install_hints_when_all_missing' \
    tests/test_main.py
  ```

---

## Testing Checkpoints

- **After Phase 1**: `just check` green; `_verify_required_tools` raises a
  `RuntimeError` whose message contains the *specific* install URL for each
  missing tool and omits URLs for present tools; legacy `git`/`uv`/`install`
  substring assertions (`test_main.py:373-442`) still pass; no clone/`Popen` is
  reached on failure. Feature is functionally complete here even if Phase 2 is
  skipped.
- **After Phase 2**: Four new per-tool/all-missing unit tests pass; full
  `uv run pytest tests/test_main.py -q` exits 0; exit-code mapping
  (`RuntimeError` → 1) and checklist `[ok]`/`[FAIL]` output are unchanged.

## Notes / Out of Scope (per design)

- No package-name preflight verifier; name validation stays at the argparse layer
  (`validate_package_name`, exit code 2). The `package name valid` registry slot
  remains `lambda: None` (`main.py:569`).
- No friendly+raw two-part split for the tools message — single header + per-tool
  hint lines.
- No changes to check ordering, exit codes, target-dir/remote verifiers,
  `humanize_git_clone_error`, the checklist format, or any post-clone step.
