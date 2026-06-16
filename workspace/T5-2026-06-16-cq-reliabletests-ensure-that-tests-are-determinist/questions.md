# Research Questions

## Context
Focus on the test suite under `tests/`, the test-runner configuration in
`Justfile` and `pyproject.toml`, and the development dependency declarations in
`pyproject.toml`/`requirements-dev.txt`. The relevant code under test lives in
`modernpackage/`.

## Questions
1. How are the existing tests structured, and what mocking or patching
   techniques do they currently use (e.g. `unittest.mock.patch`, fixtures)?
2. Which code paths in `modernpackage/` perform external interactions such as
   network requests, subprocess calls, or filesystem operations, and how are
   those interactions exercised by the tests?
3. How is the test runner currently configured and invoked across `Justfile`,
   `pyproject.toml` (`[tool.pytest.ini_options]`), and any CI files, including
   any options for parallelism, coverage, or core counts?
4. What test-related and development dependencies are declared (in
   `pyproject.toml` optional dependencies and `requirements-dev.txt`), and is
   pytest-xdist or any parallel-execution plugin among them?
5. What conventions exist in this project (or its referenced sibling project)
   for selecting CPU core counts when running commands, e.g. `nproc`-based
   expressions in `Justfile`/`Makefile` recipes?
6. Are there any existing end-to-end or integration tests distinguished from
   unit tests, and how (if at all) are such tests marked, grouped, or selected?
