# WaveformScout

PySide6 Digital/Mixed-Signal Waveform Viewer. AI-generated code.

## Overview

WaveformScout is a high-performance waveform viewer widget built with PySide6 (Qt6) for viewing digital and mixed-signal waveforms from VCD, FST, and other formats. It uses a Rust backend ([Wellen library](https://github.com/ekiwi/wellen)) for fast waveform processing.

## Requirements

- Python 3.12+
- Rust toolchain (for building pywellen)
- Poetry
- Make

Once all those tools are installed and in PATH, you can use the provided `Makefile` to manage the project.

## Installation

```bash
# Install dependencies and build pywellen
make install

# Or manually:
poetry config virtualenvs.in-project true
poetry install
poetry run build-pywellen
```

## Quick Start

```bash
# Run the demo application
make dev
# or
poetry run python scout.py

# Run tests
make test

# Type checking
make typecheck
```

## Development

The project uses Poetry with a local virtual environment (`.venv`) for dependency isolation:

```bash
# Activate virtual environment
source .venv/bin/activate

# Build pywellen (Rust bindings)
poetry run build-pywellen

# Run specific test
poetry run python test_<name>.py
```

## Project Structure

```
WaveformScout/
├── wavescout/              # Main package
│   ├── waveform_db.py      # Waveform database interface
│   ├── data_model.py       # Core dataclasses
│   ├── wave_scout_widget.py # Main widget
│   ├── signal_renderer.py  # Signal rendering logic
│   └── waveform_canvas.py  # Waveform drawing canvas
├── wellen/                 # Wellen library submodule
│   └── pywellen/          # Python bindings
├── scout.py               # Main application
└── tests/                 # Test suite
```

## Documentation

- [Project Guide](CLAUDE.md) - Development guide and conventions

## License

[License information to be added]