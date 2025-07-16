.PHONY: install build clean test help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies and build pywellen
	poetry config virtualenvs.in-project true
	poetry install
	poetry run build-pywellen

build:  ## Build the project
	poetry run build-pywellen
	poetry build

clean:  ## Clean build artifacts
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:  ## Run tests
	poetry run pytest tests/ --ignore=wellen/

typecheck:  ## Run mypy type checker
	poetry run mypy wavescout/ --config-file mypy.ini

dev:  ## Run the demo application
	poetry run python scout.py