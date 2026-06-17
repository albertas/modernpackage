# modernpackage — Vision

This document captures the project's distinct visions and aspirational features.
Each vision has a stable `V<num>` identifier that is never renumbered or reused.

## V1 — Fail-loud scaffolding with actionable errors

Today `init_new_package()` spawns `git clone` and `just init` and silently
discards their output, so any failure leaves the user with no signal. This
vision makes scaffolding fail loudly and helpfully: check the return code of
both subprocess calls, surface the captured stderr to the user, and exit
non-zero whenever a step fails. Error messages should be human-readable and
actionable — for example, "git clone failed: repository unreachable — check your
network" or "just is not installed" — rather than a silent no-op. The result is
a tool the user can trust to tell them exactly what went wrong and what to do
about it.

## V2 — End-to-end smoke test of the generated package

A scaffolder is only as good as the package it produces. This vision adds an
optional `--verify` step (backed by an e2e test) that, immediately after
scaffolding, runs `just check` inside the freshly created package and reports
whether it passes. By proving the generated package is buildable, lint-clean,
and type-checked before control returns to the user, the tool guarantees that
every new project starts from a known-good state rather than one the user only
discovers is broken later.

## V3 — Richer, validated package naming

The current `isalnum()` rule rejects perfectly valid distribution names. This
vision relaxes validation to accept valid PEP 508 / PyPI distribution names —
including hyphens and underscores — while normalizing them into an import-safe
module name. It also rejects names that would collide with standard-library
modules or with already-taken PyPI packages, and returns a precise explanation
of why any name was refused. The maintainer gets flexible, real-world naming
without the foot-guns of invalid or conflicting names.

## V4 — Configurable author/metadata seeding

A freshly scaffolded package should not ship with template placeholders. This
vision populates `pyproject.toml` author name and email, description, license,
and initial repository URL during init, drawing values from CLI flags,
environment variables, or the user's git config (`user.name` / `user.email`).
A per-user config file can supply defaults so the maintainer never re-enters the
same metadata. The outcome is a package whose metadata is correct and personal
from the first commit.

## V5 — Preflight environment checks before cloning

Before doing any work, this vision verifies that the environment can succeed:
that `git`, `just`, and `uv` are on `PATH`, that the target directory does not
already exist (refusing to overwrite existing work), and that the GitHub remote
is reachable. The tool prints a concise checklist and, if any precondition
fails, aborts early with a specific remediation hint — catching problems before
they cause a half-finished scaffold.

## V6 — Dry-run and post-init summary output

This vision replaces the current silent success/no-op behavior with clear
feedback at both ends of a run. A `--dry-run` flag prints exactly what would be
created and renamed without touching the disk, letting the user preview the
operation. On a real run, the tool prints a short summary afterward: the created
path, the package name, the reset version, and the next commands to run
(`cd <name> && just check`). The user always knows what happened and what to do
next.

## V7 — Offline / vendored template mode

Scaffolding should not require a network round-trip to GitHub. This vision
bundles the template inside the published wheel (or caches the last successful
clone) so `modernpackage <name>` can scaffold entirely offline. An `--offline`
flag forces use of the vendored copy, and the tool falls back to it
automatically whenever the network is unavailable — making the scaffolder
reliable on planes, in CI, and behind restrictive firewalls.

## V8 — Self-update / version-pinned templating

This vision gives the user control over which template they scaffold from. A
`--ref <tag>` flag pins scaffolding to a specific template ref, and
`modernpackage --version` reports the template and tooling versions it will
produce, not just the CLI's own version. The tool also warns when the installed
CLI is older than the latest published release, so the maintainer can choose
between reproducibility and staying current with intent.
