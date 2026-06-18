# Task

Allow the package-metadata CLI options (author name, author email, description,
license, repository URL) to fall back to values read from environment variables
when their corresponding command-line flags are not supplied. This gives users a
way to set sane defaults once in their shell environment instead of repeating
flags on every `modernpackage` invocation, while keeping explicit flags
authoritative when present.
