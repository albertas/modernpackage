# Task

Write the author name/email, description, license, and repository URL — already
collected by the CLI from flags, environment variables, git config, and the
per-user config file — into the newly scaffolded package's `pyproject.toml`
during `init`. Today `init_new_package` receives these values but discards them,
so the generated project keeps the template's placeholder metadata; this task
makes the generated `pyproject.toml` reflect the values the user supplied.
