# Task

Distribution names accepted by the CLI may contain hyphens, dots, and
underscores (PEP 508 / PyPI form), but a Python import package directory must be
a valid import-safe identifier. This task adds normalization that converts an
accepted distribution name (e.g. `my-cool.package`) into an import-safe module
name (e.g. `my_cool_package`) so the scaffolded package directory and import
path are always valid Python.
