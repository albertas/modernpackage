# Task

When `modernpackage` scaffolds a new package it runs `just init` via `subprocess.Popen`.
If the `just` command is not installed on the user's system, this currently fails with an
unhelpful `FileNotFoundError` traceback. Detect this case and instead print a clear,
actionable message telling the user that `just` is missing and how to install it, exiting
with the standard failure code (1) like other scaffolding failures.
