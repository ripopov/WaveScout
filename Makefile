.PHONY: install build clean test help compile

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
	if exist dist rmdir /s /q dist
	if exist build rmdir /s /q build
	if exist *.egg-info rmdir /s /q *.egg-info
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	for /r . %%f in (*.pyc) do @if exist "%%f" del "%%f"

test:  ## Run tests
	poetry run pytest tests/ --ignore=wellen/

typecheck:  ## Run mypy type checker (strict mode)
	poetry run mypy wavescout/ --strict --config-file mypy.ini

dev: install  ## Run the demo application
	poetry run python scout.py

compile: install  ## Compile scout.py into executable using Nuitka
	poetry add --group dev nuitka setuptools wheel
	poetry run pip install --upgrade setuptools wheel
	poetry run python -m nuitka --standalone --onefile \
		--enable-plugin=pyside6 \
		--include-package=wavescout \
		--include-package=numpy \
		--include-package=yaml \
		--include-package=rapidfuzz \
		--include-package=qdarkstyle \
		--include-data-dir=wellen=wellen \
		--windows-console-mode=disable \
		--assume-yes-for-downloads \
		--no-progress-bar \
		--output-filename=WaveformScout.exe \
		--output-dir=dist \
		scout.py
