lifecycle:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]
  @count=0; while uv run lifecycle --max-tasks 1 --prior-tasks "$count"; do count=$((count + 1)); done

sync:
  @uv pip sync requirements-dev.txt
  @uv pip install -e .[test]

test *args: sync
  uv run pytest {{args}}

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

check: check-format check-lint check-complexity check-typecheck test
