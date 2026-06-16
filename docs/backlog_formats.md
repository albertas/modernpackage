# BACKLOG.md Format

[overview.md](overview.md)

The [`BACKLOG.md`](../BACKLOG.md) file tracks planned work using a hierarchical task structure with progress markers and category tags.

## Task Structure

BACKLOG.md organizes tasks into categories (headings) with sub-tasks (nested bullets). Each task uses a **progress marker** in square brackets, followed by optional metadata tags and a description.

## Progress Markers

| Marker | Meaning |
|--------|---------|
| `[ ]` | **Incomplete** — task is planned but not started. |
| `[x]` | **Complete** — task is finished. |
| `[~]` | **In-progress** — task is actively being worked on. |

## Task Tags

Tasks may include category tags in square brackets to group related work:

- `[T2]`, `[T3]`, `[T4]`, etc. — **Task IDs** for tracking and cross-referencing (e.g., `[T2]` for a task in iteration 2).
- `[cq:*]` — **Code quality category tags** (e.g., `[cq:spec]`, `[cq:aliases]`, `[cq:coverage]`).
  - `[cq:spec]` — Write specification documentation.
  - `[cq:aliases]` — Add Justfile targets / command aliases.
  - `[cq:coverage]` — Improve test coverage.
  - `[cq:reliabletests]` — Ensure deterministic, fast tests.
  - `[cq:ruff-format]` — Code formatting audit.
  - `[cq:ruff-lint]` — Linting audit.
  - `[cq:typecheck]` — Type-checking audit.
  - `[cq:complexity]` — Cyclomatic complexity audit.
  - `[cq:check]` — Validation of combined `check` target.
  - `[cq:python]` — Python version updates.
  - `[cq:versions]` — Dependency version updates.

## Example Structure

```markdown
# Category Name
- [ ] Main task description [T1] [cq:category]
  - [x] Sub-task that is complete
  - [~] Sub-task in progress [cq:subcategory]
  - [ ] Sub-task not yet started
```

## Use Cases

**Tracking progress toward milestones:** Mark a task `[~]` when starting work, then `[x]` when complete.

**Cross-referencing:** Tags like `[cq:aliases]` can be used in commit messages, PR titles, or issue trackers to link work back to backlog items.

**Hierarchical organization:** Sub-tasks under a parent task inherit the parent's context; use indentation to show dependency and logical grouping.

## Current Status

See [`BACKLOG.md`](../BACKLOG.md) for the current task list and progress toward code quality milestones.

Code quality audits (marked with `[cq:*]` tags) ensure that the package maintains strict type checking, linting, formatting, test coverage, and code complexity standards. The `[cq:typecheck]` category specifically tracks mypy strict-mode verification—currently passing with no issues found.
