# Task

Add command-line flags to the `modernpackage` CLI for supplying package metadata:
author name, author email, description, license, and repository URL. This lets a
user provide these values when scaffolding a new package, forming the foundation
for later V4 work that reads defaults from other sources and writes the values
into the generated `pyproject.toml`.

The scope of this task is the CLI surface: defining the flags, validating their
inputs, and threading the parsed values through to the package-initialization
entry point.
