# Task

When `git clone` fails during scaffolding, `modernpackage` currently surfaces the
raw git exit code and stderr to the user. This task adds a mapping layer that
recognizes common git clone failure stderr patterns (e.g. "Could not resolve
host", "Repository not found", "already exists", authentication failures) and
turns them into human-readable, actionable messages such as "repository
unreachable — check your network connection", while still preserving the
underlying git output for diagnostics.
