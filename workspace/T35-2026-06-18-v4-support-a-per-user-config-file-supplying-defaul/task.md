# Task

Add a per-user configuration file as an additional source of default metadata
values (author name, author email, description, license, repository URL) for
the `modernpackage` CLI. The file supplies defaults when the corresponding
command-line flag, environment variable, and git-config sources do not provide
a value, so users can set their preferred defaults once instead of repeating
flags on every invocation.
