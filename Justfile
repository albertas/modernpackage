lifecycle:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]
  @count=0; while uv run lifecycle --max-tasks 1 --prior-tasks "$count"; do count=$((count + 1)); done

sync:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]

test *args: sync
  uv run pytest -n "$(nproc --ignore=1)" {{args}}

test-e2e *args: sync
  uv run pytest -m e2e {{args}}

format: sync
  uv run ruff format modernpackage tests

lint: sync
  uv run ruff check modernpackage tests

typecheck: sync
  uv run mypy modernpackage tests

check-format: sync
  uv run ruff format --check modernpackage tests

check-lint: sync
  uv run ruff check modernpackage tests

check-complexity: sync
  uv run ruff check --select C901 modernpackage tests

check-typecheck: sync
  uv run mypy modernpackage tests

audit: sync
  uv run pip-audit --skip-editable

deadcode: sync
  uv run deadcode modernpackage tests

fix-lint: sync
  uv run ruff check --fix --unsafe-fixes modernpackage tests
  uv run deadcode --fix modernpackage tests

fix: format fix-lint

check: check-format check-lint check-complexity check-typecheck test audit deadcode

publish:
  rm -fr dist/*
  uv build
  uv publish

init package_name="modernpackage":
  @echo "Initializing {{package_name}}..."
  @if [ "$(uname)" = "Linux" ]; then \
    git grep -l 'modernpackage' | xargs sed -i 's/modernpackage/{{package_name}}/g'; \
  fi
  @if [ "$(uname)" = "Darwin" ]; then \
    git grep -l 'modernpackage' | xargs sed -i '' -e 's/modernpackage/{{package_name}}/g'; \
  fi
  @sed -i -e 's/[[:digit:]]\+\.[[:digit:]]\+\.[[:digit:]]\+/0.0.1/g' modernpackage/__init__.py
  @mv modernpackage {{package_name}}
  @rm -fr .git/ .venv
  @git init -b main .
  @git add .
  @git commit -m "Initial modern {{package_name}} package setup"
  @echo "Finished initializing {{package_name}}. You can now run: \033[0;32m cd {{package_name}} && just check\033[0m"

compile:
  uv pip compile -U -q pyproject.toml -o requirements.txt
  uv pip compile -U -q --all-extras pyproject.toml -o requirements-dev.txt
  uv lock --upgrade
