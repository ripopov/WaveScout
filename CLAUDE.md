# WaveScout Project Guide

## Overview

WaveScout is a waveform viewer widget for digital design verification. It is built with PySide6 for the GUI and uses a
Rust backend (Wellen library: https://github.com/ekiwi/wellen) for processing waveform databases.

Project must use modern Python 3.12 features and use Poetry for dependency management.

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
- Poetry
- Python 3.12
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

## Type Safety Guidelines

### Strict Typing Requirements
This project enforces strict type safety. All code must adhere to these guidelines:

1. **No `Any` types**: Replace all `Any` types with specific type annotations
2. **Use TypedDict**: Define structured dictionaries with `TypedDict` for better type safety
3. **Explicit Optional**: Use `Optional[T]` for nullable values, never implicit `None`
4. **Type all parameters and returns**: Every function must have complete type annotations
5. **Use Union sparingly**: Prefer specific types or protocols over broad unions
6. **Leverage TypeAlias**: Create type aliases for complex types to improve readability

### Type Annotation Examples
```python
from typing import Optional, TypedDict, Protocol, TypeAlias
from collections.abc import Sequence

# Use TypedDict for structured data
class SignalData(TypedDict):
    name: str
    value: int
    transitions: list[int]

# Use Protocol for interfaces
class Renderable(Protocol):
    def render(self, params: RenderParams) -> None: ...

# Use TypeAlias for complex types
SignalMap: TypeAlias = dict[str, SignalData]

# Avoid Any - be specific
# Bad:  def process(data: Any) -> Any
# Good: def process(data: SignalData) -> ProcessedSignal
```

### MyPy Configuration
The project uses strict mypy checking. Run type checks with:
```bash
make typecheck
```

Expected mypy configuration:
- `strict = true`
- `warn_return_any = true`
- `disallow_any_explicit = true`
- `disallow_untyped_defs = true`

### Qt Type Annotations
For PySide6/Qt types:
- Use specific Qt types: `QWidget`, `QEvent`, `QPaintEvent`, etc.
- Never use `Any` for Qt objects
- Import types from appropriate modules: `from PySide6.QtCore import QEvent`

## Notes
- The pywellen module provides access to VCD/FST waveform files
- Rendering is optimized using Rust-based pixel region generation
- The project uses single-threaded rendering for simplicity