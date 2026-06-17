# Plan

## Phase 1: Map common git clone failures to actionable messages

### Goal
When `git clone` fails in `init_new_package`, recognize common failure modes from
the captured stderr and raise a `RuntimeError` whose message leads with a
human-readable, actionable explanation, while still including the raw git stderr
for diagnostics.

### Current behavior
`modernpackage/main.py::init_new_package` runs `git clone` via `Popen`, captures
stderr, and on a non-zero return code raises:

```python
message = f'git clone failed with exit code {pipe.returncode}: {stderr_text}'
raise RuntimeError(message)
```

`main()` already catches `RuntimeError` and prints the message to stderr (T18),
returning exit code 1 (T19). We only change *what* the message says.

### Implementation (in `modernpackage/main.py`)

1. Add module-level mapping of compiled, case-insensitive regex patterns to
   friendly messages, ordered most-specific first. Follow project conventions:
   compiled-regex constants suffixed `_RE`, full-word names, inline `#` comments.

   Candidate mappings (each pattern matched against the lowercased stderr):
   - `could not resolve host` / `could not read from remote` /
     `failed to connect` / `connection timed out` / `network is unreachable`
     → `repository unreachable — check your network connection`
   - `repository not found` / `remote: not found` / `does not exist`
     → `template repository not found — it may have moved or been removed`
   - `permission denied (publickey)` / `authentication failed` /
     `could not read username`
     → `authentication failed — check your git credentials or access rights`
   - `already exists and is not an empty directory`
     → `destination directory already exists — choose a different package name`
   - `permission denied` / `could not create` / `unable to create`
     → `cannot write to the destination directory — check filesystem permissions`

   Represent as an ordered list of `(compiled_regex, message)` tuples, e.g.
   `_GIT_CLONE_ERROR_MESSAGES: list[tuple[re.Pattern[str], str]]`.

2. Add a pure helper, e.g.
   `humanize_git_clone_error(stderr_text: str) -> str | None`, that returns the
   first matching friendly message or `None` when nothing matches. Keep
   cyclomatic complexity low (a simple loop over the mapping).

3. In `init_new_package`, on git clone failure build the message as:
   - If a friendly message matches:
     `f'{friendly}\n\ngit clone failed with exit code {pipe.returncode}: {stderr_text}'`
   - Otherwise fall back to the existing
     `f'git clone failed with exit code {pipe.returncode}: {stderr_text}'`

   This preserves the raw stderr (T17/T18) and the exit-code substring that
   existing tests assert on, while leading with the actionable message.

   Keep the `just init` failure branch unchanged.

### Testing (in `tests/test_main.py`)
Add `def test_*` functions (plain `assert`, no classes), patching `Popen` the
same way existing tests do:

1. `test_humanize_git_clone_error_network` — stderr containing
   `Could not resolve host: github.com` maps to the network message.
2. `test_humanize_git_clone_error_repo_not_found` — `Repository not found`
   maps to the not-found message.
3. `test_humanize_git_clone_error_auth` — `Permission denied (publickey)`
   maps to the authentication message.
4. `test_humanize_git_clone_error_directory_exists` — `already exists and is
   not an empty directory` maps to the destination message.
5. `test_humanize_git_clone_error_unknown_returns_none` — unrecognized stderr
   returns `None`.
6. `test_init_new_package_git_clone_network_failure` — patch `Popen` so git
   clone returns code 1 with `b'fatal: ... Could not resolve host: github.com'`;
   assert the raised `RuntimeError` message contains both the friendly
   "check your network" text and the raw stderr.

Verify the existing `test_init_new_package_git_clone_failure` still passes (its
`match='git clone failed with exit code 1'` substring is preserved by the
fallback/suffix in the message).

### Verification
- [x] `just check` passes (format, lint, complexity ≤ 10, mypy, tests).
- [x] New and existing tests pass; coverage stays ≥ 95%. (18 tests, 100% coverage)
