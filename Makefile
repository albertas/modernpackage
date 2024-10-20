.PHONY: compile publish check fix lint fixlint format mypy deadcode audit test init
args = $(or $(filter-out $@,$(MAKECMDGOALS)), "modernpackage")
UV := $(shell uv --version 2>/dev/null)
OS := $(shell uname)

check: test lint mypy audit deadcode
fix: format fixlint

uv:
ifndef UV
	@echo "uv not found. Installing uv.."
	pip install uv
endif

.venv: uv
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
	.venv/bin/pip-audit --skip-editable

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

## NOTE: --quiet removes some useful output from commonly used targets.
# Another workaround should be found to suppress init error for target up to date rule.
# MAKEFLAGS += --quiet
init:
	@echo "Initializing ${args}..."
	@if [ $(OS) = "Linux" ]; then\
		git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/$(args)/g';\
	fi
	@if [ $(OS) = "Darwin" ]; then\
		git grep -l 'modernpackage' | xargs sed -i '' -e 's/modernpackage/$(args)/g';\
	fi
	@mv modernpackage $(args)
	@rm -fr .git/ .venv
	@git init -b main .
	@git add .
	@git commit -m "Initial modern $(args) package setup"
	@echo "Finished initializing ${args}. You can now run `cd ${args} && make check`"
	@exit 0

%:
	@:
