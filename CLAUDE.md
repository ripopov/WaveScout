# WaveScout Project Guide

## Overview

WaveScout is a waveform viewer widget for digital design verification. It is built with PySide6 for the GUI and uses a
Rust backend (Wellen library: https://github.com/ekiwi/wellen) for processing waveform databases.

## Project Structure
```
WaveScout/
├── wavescout/          # Main package
│   ├── __init__.py
│   ├── waveform_db.py  # Waveform database interface using pywellen
│   ├── data_model.py   # Core data structures
│   └── ...
├── wellen/             # Wellen waveform library submodule
│   └── pywellen/       # Python bindings
├── scout.py            # Demo application
└── tests/              # Test directory with various test files
```

## Key Dependencies
- PySide6 (Qt6 for Python)
- pywellen (Python bindings for Wellen waveform library)
- Rust toolchain (for building pywellen)

## Important Commands

### Initial Setup
```bash
# Install dependencies and build pywellen
# This creates a local .venv in the project directory
make install

# Or manually:
poetry config virtualenvs.in-project true
poetry install
poetry run build-pywellen
```

### Virtual Environment
The project uses Poetry with a local virtual environment (.venv) in the project directory.
This ensures all dependencies are isolated and makes the project portable.

To activate the virtual environment:
```bash
# Direct activation (recommended)
source .venv/bin/activate

# Or use Poetry's env activate command
poetry env activate

# All poetry commands automatically use the virtual environment
poetry run python scout.py
poetry run pytest
```

### Building
```bash
# Build pywellen only
poetry run build-pywellen

# Build entire project
make build
```

### Running tests
```bash
# Run all tests
make test

# Run specific test
poetry run python test_<name>.py

# Run demo
make dev
# or
poetry run python scout.py
```

### Linting and Type Checking
```bash
# Run mypy type checker
make typecheck

# Or directly with poetry
poetry run mypy wavescout/
```

## Key Classes
- `WaveScoutWidget`: Main waveform viewer widget
- `WaveformDB`: Waveform database using Wellen library for VCD/FST files

## Notes
- The pywellen module provides access to VCD/FST waveform files
- Rendering is optimized using Rust-based pixel region generation
- The project uses single-threaded rendering for simplicity