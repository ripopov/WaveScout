# libfst Windows Build Guide

C library for FST (Fast Signal Trace) waveform files with MSVC build support.

## Prerequisites

- **Visual Studio 2022** with C++ workload (includes MSVC and CMake)
- **Ninja** build system (for faster builds)
- **vcpkg** (included at `../vcpkg/`)
- **zlib** (provided via vcpkg at `../vcpkg_installed/`)
- **PowerShell** (for build scripts)

## Environment Setup

### Interactive Development

For manual development and debugging, source the environment setup:

```powershell
# Open PowerShell and navigate to libfst directory
cd C:\work\wave\WaveScout\libfst

# Source the environment (note the dot and space)
. .\setup_env.ps1
```

This will:
- Set up Visual Studio development environment
- Add cmake, cl.exe, ninja, and vcpkg to PATH
- Set VCPKG environment variables
- Display available tools and their locations

After sourcing, you can use standard cmake commands:

```powershell
# Configure (using Ninja for fast builds)
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build build

# Run tests
.\build\test_fst_reader.exe
```

## Quick Build

For automated build and test:

```powershell
.\build_and_run.ps1
```

This script will:
1. Source the environment setup
2. Configure CMake with Ninja (if needed)
3. Build the library
4. Run tests automatically

Output: `build/fst.lib`

## Key Files

- `setup_env.ps1` - PowerShell environment setup (dot source this)
- `build_and_run.ps1` - Automated build and test script
- `fstapi.c/h` - Main FST API with MSVC fixes
- `test_fst_reader.cpp` - Test program

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "cl.exe not found" | Run `. .\setup_env.ps1` to set up environment |
| "ninja.exe not found" | Install Ninja or use `winget install Ninja-build.Ninja` |
| ZLIB not found | Ensure vcpkg_installed exists: `../vcpkg/vcpkg.exe install zlib:x64-windows` |
| VS not detected | Install VS 2022 with C++ workload |
| Script execution blocked | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## Build Details

- **Platform**: Windows x64
- **Compiler**: MSVC 2022 (v143)
- **Build System**: Ninja (for faster builds)
- **C Standard**: C99
- **Dependencies**: zlib (via vcpkg)

## MSVC Compatibility Fixes

The following fixes were applied for MSVC compatibility:
- Use `tmpfile_s()` instead of `tmpfile()` for secure temp files
- Set binary mode on duplicated file descriptors
- Properly seek duplicated file descriptors after reading
- Include `<fcntl.h>` for `_O_BINARY` mode constants