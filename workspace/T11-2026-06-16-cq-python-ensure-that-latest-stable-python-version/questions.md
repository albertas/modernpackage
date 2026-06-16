# Research Questions

## Context
Focus on where the Python interpreter version is declared, pinned, or assumed
across the repository: packaging metadata (`pyproject.toml`), environment
creation and CI (`Makefile`, `Justfile`, `.github/workflows/`, `.gitlab-ci.yml`),
static-analysis tool targets, and documentation under `docs/` and `README.md`.
Also consider how the self-cloning scaffolder copies and rewrites these files
into newly generated packages.

## Questions
1. In `pyproject.toml`, which fields encode a Python version (e.g. `requires-python`, trove classifiers, tool sections such as `[tool.mypy]`), and what value does each currently hold?
2. How is the development virtual environment created in `Makefile` and `Justfile`, and where (if anywhere) is a specific Python interpreter version requested when building it?
3. How do the CI definitions (`.github/workflows/` files and `.gitlab-ci.yml`) select or set up the Python version used to run checks, including any version embedded in workflow file names or step names?
4. Which static-analysis or build tools in this project are configured with a target Python version (e.g. mypy, ruff, hatchling), and where is each such setting defined?
5. Where do `README.md` and the files under `docs/` mention or assume a specific Python version, and what versions appear in those references?
6. How does the scaffolder (`modernpackage/main.py` and the `make init` flow) copy and rewrite repository files into a new package, and do any Python-version strings get propagated, rewritten, or left untouched during that process?
