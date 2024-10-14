
.PHONY: compile publish check fix lint fixlint format mypy deadcode audit test
args = $(filter-out $@,$(MAKECMDGOALS))

check: test lint mypy audit deadcode
fix: format fixlint

.venv:
	pip install uv
	uv venv -p 3.11
	uv pip sync requirements-dev.txt
	uv pip install -e .[test]

publish: .venv
	rm -fr dist/*
	.venv/bin/hatch build
	.venv/bin/hatch -v publish

lint: .venv
	.venv/bin/ruff check modernpackage tests

fixlint: .venv
	.venv/bin/ruff check --fix modernpackage tests --unsafe-fixes
	.venv/bin/deadcode --fix modernpackage tests

format: .venv
	.venv/bin/ruff format modernpackage tests

mypy: .venv
	.venv/bin/mypy modernpackage tests

audit: .venv
	.venv/bin/pip-audit

deadcode: .venv
	.venv/bin/deadcode modernpackage tests

test: .venv
	.venv/bin/pytest $(TEST_NAME)

sync: .venv
	uv pip sync requirements-dev.txt
	uv pip install -e .[test]

compile:
	uv pip compile -U -q pyproject.toml -o requirements.txt
	uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt

init:
	@echo "Initializing" $(args)

%:
	@:
