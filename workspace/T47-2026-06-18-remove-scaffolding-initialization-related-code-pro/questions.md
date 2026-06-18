# Research Questions

## Context
Focus on the `modernpackage/` Python package, the `Justfile`, the `tests/`
suite, and the `docs/`/`README.md` documentation. The areas of interest are the
package-initialization flow (the `just init` recipe and the Python orchestrator
that clones a template and transforms the copy), the internal structure of
`main.py`, the quality gates bundled into `just check`, and how the test suite
and documentation describe the flow and the contents of a freshly created
package.

## Questions
1. How does the package-initialization flow work end to end — what steps does
   `init_new_package` in `modernpackage/main.py` perform, and what
   transformations does the `init` recipe in the `Justfile` apply to a cloned
   copy (renaming, version reset, directory move, git re-init)?

2. What is the module-level structure of `modernpackage/main.py` — which
   functions, dataclasses, and module constants does it define, how do they
   depend on each other, and what does `modernpackage/__init__.py` contain and
   expose?

3. How is the `check` target composed in the `Justfile`, and what does each
   gate require (ruff format, ruff lint, C901 complexity, mypy, pytest)? What
   coverage configuration and thresholds are set in `pyproject.toml`, and how
   are tests, coverage, and entry-point scripts configured there?

4. How is the `tests/` suite organized across `test_main.py` and `test_e2e.py` —
   what symbols does it import from `modernpackage.main`, and what does the
   end-to-end test assert about a package produced by the init flow?

5. What do `README.md` and the files under `docs/` describe about the
   initialization/scaffolding flow and about what the resulting generated
   package is expected to contain after initialization?

6. Which files in the repository would be carried into a cloned copy of the
   template, and which of them are referenced or rewritten by the init flow
   (e.g. `pyproject.toml` metadata substitution, `__init__.py` version reset,
   the renamed package directory)?
