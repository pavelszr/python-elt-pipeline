.DEFAULT_GOAL := help
PYTHON ?= python
PIP ?= $(PYTHON) -m pip

# Default run parameters (override on the command line, e.g. `make run START=2024-06-01`)
START ?= 2024-01-01
END ?= 2024-03-01
BASE ?= USD
SYMBOLS ?= EUR,GBP,HNL,MXN

.PHONY: help setup lint format test run clean

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Install the package (editable) plus dev dependencies.
	$(PIP) install -e ".[dev]"
	pre-commit install || true

lint:  ## Run ruff lint checks.
	ruff check src tests

format:  ## Auto-format and fix with ruff.
	ruff format src tests
	ruff check --fix src tests

test:  ## Run the test suite with coverage.
	pytest --cov=fxpipeline --cov-report=term-missing

run:  ## Run the pipeline (override START/END/BASE/SYMBOLS as needed).
	$(PYTHON) -m fxpipeline run --start $(START) --end $(END) --base $(BASE) --symbols $(SYMBOLS)

clean:  ## Remove caches and the local warehouse file.
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f warehouse.duckdb
