# Research Questions

## Context
Focus on how this repository manages Python dependencies and orchestrates
developer/CI tasks. Relevant areas include `pyproject.toml`, `uv.lock`,
`requirements.txt`, `requirements-dev.txt`, the `Justfile`, any `Makefile`, the
CI configuration (`.gitlab-ci.yml`, `.github/`), the scaffolding CLI under
`modernpackage/`, the test suite under `tests/`, and the docs under `docs/` and
`README.md`.

## Questions
1. How are dependencies declared and pinned across `pyproject.toml`, `uv.lock`,
   `requirements.txt`, and `requirements-dev.txt` — which extras or dependency
   groups exist, what populates each file, and how do they relate to each other?

2. What recipes does the `Justfile` define, and for each, which exact `uv`
   subcommands (e.g. `uv pip sync`, `uv pip install`, `uv pip compile`,
   `uv run`, `uv lock`, `uv build`) does it invoke and in what dependency order?

3. Does a `Makefile` exist anywhere in the repository, and if so what
   dependency-installation, build, or test targets does it define? If none
   exists, confirm its absence.

4. How does the scaffolding CLI in `modernpackage/main.py` read, parse, or
   transform `pyproject.toml`, and which specific sections or keys (e.g.
   `[project.optional-dependencies]`, `[project.scripts]`, markers) does its
   logic depend on?

5. How is continuous integration configured (`.gitlab-ci.yml`, `.github/`) to
   provision the environment and install dependencies, and which Justfile
   recipes or commands does it call?

6. How do the test suite (`tests/`) and the documentation (`docs/`, `README.md`)
   describe or assert against the current dependency workflow, the requirements
   files, the `test` extra, and the `just compile`/`just sync` recipes?
