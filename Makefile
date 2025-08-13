# Detect operating system
ifeq ($(OS),Windows_NT)
    detected_OS := Windows
    SHELL := cmd.exe
    .SHELLFLAGS := /c
    MKDIR := mkdir
    RM := del /q /f
    RMDIR := rmdir /s /q
    NULL := nul
    PATHSEP := \\
else
    detected_OS := $(shell uname -s)
    MKDIR := mkdir -p
    RM := rm -f
    RMDIR := rm -rf
    NULL := /dev/null
    PATHSEP := /
endif

.PHONY: install build clean test help compile build-libfst

help:  ## Show this help
ifeq ($(detected_OS),Windows)
	@echo Available targets:
	@echo   install      - Install dependencies and build pywellen and libfst
	@echo   build        - Build the project
	@echo   build-libfst - Build libfst C library
	@echo   clean        - Clean build artifacts
	@echo   test         - Run tests
	@echo   typecheck    - Run mypy type checker
	@echo   dev          - Run the demo application
	@echo   compile      - Compile scout.py into executable
else
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
endif

build-libfst:  ## Build libfst C library
ifeq ($(detected_OS),Windows)
	@echo Building libfst...
	@if not exist libfst$(PATHSEP)build $(MKDIR) libfst$(PATHSEP)build
	@if defined CMAKE_TOOLCHAIN_FILE (cd libfst$(PATHSEP)build && cmake -DCMAKE_TOOLCHAIN_FILE="$(CMAKE_TOOLCHAIN_FILE)" -DVCPKG_TARGET_TRIPLET=x64-windows -DVCPKG_INSTALLED_DIR="$(VCPKG_INSTALLED_DIR)" .. && cmake --build . --config Release) else (cd libfst$(PATHSEP)build && cmake .. && cmake --build . --config Release)
else
	@echo "Building libfst..."
	@$(MKDIR) libfst/build
	cd libfst/build && cmake .. && make
endif

install:  ## Install dependencies and build pywellen and libfst
	poetry config virtualenvs.in-project true
	poetry install
	poetry run build-pywellen
	$(MAKE) build-libfst

build:  ## Build the project
	poetry run build-pywellen
	$(MAKE) build-libfst
	poetry build

clean:  ## Clean build artifacts
ifeq ($(detected_OS),Windows)
	@if exist dist $(RMDIR) dist 2>$(NULL) || echo.
	@if exist build $(RMDIR) build 2>$(NULL) || echo.
	@if exist libfst$(PATHSEP)build $(RMDIR) libfst$(PATHSEP)build 2>$(NULL) || echo.
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" $(RMDIR) "%%d" 2>$(NULL) || echo.
	@for /r . %%f in (*.pyc) do @if exist "%%f" $(RM) "%%f" 2>$(NULL) || echo.
	@for /r . %%f in (*.egg-info) do @if exist "%%f" $(RMDIR) "%%f" 2>$(NULL) || echo.
else
	$(RMDIR) dist build *.egg-info 2>$(NULL) || true
	$(RMDIR) libfst/build 2>$(NULL) || true
	find . -type d -name __pycache__ -exec $(RMDIR) {} + 2>$(NULL) || true
	find . -type f -name "*.pyc" -delete 2>$(NULL) || true
endif

test:  ## Run tests
	poetry run pytest tests/ --ignore=wellen/

typecheck:  ## Run mypy type checker (strict mode)
	poetry run mypy wavescout/ --strict --config-file mypy.ini

dev: install  ## Run the demo application
	poetry run python scout.py

compile: install  ## Compile scout.py into executable using Nuitka
	poetry add --group dev nuitka setuptools wheel
	poetry run pip install --upgrade setuptools wheel
ifeq ($(detected_OS),Windows)
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
		scout.py
else
	poetry run python -m nuitka --standalone --onefile \
		--enable-plugin=pyside6 \
		--include-package=wavescout \
		--include-package=numpy \
		--include-package=yaml \
		--include-package=rapidfuzz \
		--include-package=qdarkstyle \
		--include-data-dir=wellen=wellen \
		--assume-yes-for-downloads \
		--no-progress-bar \
		--output-filename=WaveformScout \
		scout.py
endif
