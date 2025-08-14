# libfst Windows Build Guide

C library for FST (Fast Signal Trace) waveform files with MSVC build support.

## Prerequisites

- **Visual Studio 2022** with C++ workload (includes MSVC and CMake)
- **vcpkg** (included at `../vcpkg/`)
- **zlib** (provided via vcpkg at `../vcpkg_installed/`)

## Quick Build

```powershell
# Automated build (recommended)
powershell -ExecutionPolicy Bypass -File test_build.ps1
```

Output: `build/Release/fst.lib`

## Manual Build

```batch
# 1. Setup environment
setup_vs_env.bat

# 2. Configure and build
mkdir build && cd build
cmake .. -G "Visual Studio 17 2022" -A x64 ^
    -DCMAKE_TOOLCHAIN_FILE="../vcpkg/scripts/buildsystems/vcpkg.cmake" ^
    -DVCPKG_TARGET_TRIPLET="x64-windows" ^
    -DVCPKG_INSTALLED_DIR="../vcpkg_installed"
cmake --build . --config Release
```

## Key Files

- `fstapi.c/h` - Main FST API
- `fastlz.c/h`, `lz4.c/h` - Compression algorithms
- `fst_config_stub.h` - Windows config header
- `setup_vs_env.bat` - VS environment setup
- `test_build.ps1` - Automated build script

## Troubleshooting

| Issue | Solution |
|-------|----------|
| ZLIB not found | Run `../vcpkg/vcpkg.exe install zlib:x64-windows` |
| VS not detected | Install VS 2022 with C++ workload |
| CMake not found | Comes with VS 2022, or install from cmake.org |

## Build Details

- **Platform**: Windows x64
- **Compiler**: MSVC 2022 (v143)
- **C Standard**: C99
- **Dependencies**: zlib (via vcpkg)