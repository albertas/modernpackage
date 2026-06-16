# Task: Ensure latest dependency versions are used

Update the project's dependencies so that the latest stable versions are
used across the dependency declarations, the lock file, and the compiled
requirements files, keeping all of them mutually consistent. This is a
code-quality task for a "bleeding edge toolset" package template, so the
goal is for development, CI, and packaging to resolve to current upstream
releases while `just check` continues to pass.
