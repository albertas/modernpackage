# Research Questions

## Context
Focus on the project's task-runner definitions (`Makefile` and `Justfile`) and
everything that invokes them: the Python CLI source under `modernpackage/` and
its tests, the CI pipeline definitions (`.github/workflows/`, `.gitlab-ci.yml`),
and the developer-facing documentation (`README.md`, `docs/`). The aim is to map
which build/dev commands exist, how they are defined, and where they are called
from.

## Questions
1. What targets/recipes does the `Makefile` define, what shell commands does
   each run, and which of them have no equivalent recipe in the current
   `Justfile`?
2. How does the `Justfile` define its recipes — recipe dependencies (e.g. the
   `sync` prerequisite), argument passing syntax (`{{args}}`, `*args`), and any
   environment/shebang conventions — and how does that differ structurally from
   how the `Makefile` expresses the same ideas (`.PHONY`, the `.venv` target,
   `args`/`MAKECMDGOALS`, OS branching, the `%:` catch-all)?
3. Where in the Python source (`modernpackage/`) is `make` invoked as a
   subprocess, what arguments are passed, how is its output handled, and what is
   the surrounding initialisation flow?
4. How do the existing tests cover the code path that invokes `make`, and what
   exactly do they assert or mock about that invocation?
5. Which CI configuration files reference `make` targets, and which specific
   targets do they call during their build/test steps?
6. Where does the documentation (`README.md`, `docs/`) reference `make` commands
   or describe the project's toolset and developer workflow?
7. What does the `Makefile`'s `init` recipe do step by step (package renaming via
   `git grep`/`sed`, version reset, directory move, git re-initialisation, OS
   branching), and what constraints would translating it to a `just` recipe
   impose?
