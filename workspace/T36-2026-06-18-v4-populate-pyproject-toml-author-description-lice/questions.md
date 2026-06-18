# Research Questions

## Context
Focus on the package-scaffolding code in `modernpackage/main.py` (especially the
clone-and-init flow), the cloned template's `pyproject.toml` and the `just init`
recipe in the `Justfile`, and the tests covering the init path in
`tests/test_main.py` and `tests/test_e2e.py`. The design and decision records
under `docs/` are also relevant.

## Questions
1. Trace the end-to-end flow of `init_new_package`: which subprocess steps run,
   in what order, against which directory, and how does the cloned template's
   `just init` recipe transform files on disk before control returns?

2. How is the template's `pyproject.toml` structured — specifically, which keys
   and tables hold the author name and email, the project description, the
   license, and any repository/project URLs, and how is the license currently
   represented (e.g. a dedicated field versus a trove classifier)?

3. How does metadata move from CLI parsing through to scaffolding: which
   `Namespace` attributes and `init_new_package` parameters carry the author,
   description, license, and repository values, and how are those parameters
   currently handled inside the function?

4. What existing patterns and dependencies are available in this codebase for
   reading or modifying TOML files, and which TOML-related libraries are
   already imported or declared in `pyproject.toml` / lockfiles?

5. How do the existing tests exercise the init/scaffolding path — what is
   mocked (subprocess, filesystem), how are generated files or their contents
   asserted, and how do unit tests differ from the e2e tests for this flow?

6. What do the design and decision records under `docs/` say about how
   collected metadata is intended to be applied to a generated project, and
   about precedence/placeholder handling for author, description, license, and
   repository URL?
