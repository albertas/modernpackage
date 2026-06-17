# modernpackage — Operator Persona

[overview.md](overview.md)

## Who Relies on This Tool

**The Pragmatic Python Maintainer.** A working Python developer — often a solo
maintainer, library author, or tech lead on a small team — who starts new
packages often enough that re-wiring tooling by hand has become a tax. They care
about clean, strict, reproducible projects but have no patience for boilerplate
or for re-deciding the same config questions every time.

## Primary Goals

They want to go from "I have an idea" to "a buildable, lint-clean,
type-checked, tested package" in one command. They expect strict defaults baked
in — ruff, mypy strict mode, 95% coverage gates, complexity limits, pip-audit,
deadcode — so every project they spawn starts at the same high quality bar. The
`Justfile` is their muscle memory: `just check`, `just fix`, `just test`,
`just publish` should mean the same thing in every repo they touch.

## Pain Points It Addresses

It kills the cold-start cost of a new package: no copy-pasting `pyproject.toml`
from an old project, no drift between tools, no forgetting to set up CI or the
coverage gate. Because the tool replicates itself, every generated package
inherits a single, consistent, modern toolchain — so the maintainer spends their
time on the actual code, not on scaffolding, and never debugs a project that was
misconfigured from day one.
