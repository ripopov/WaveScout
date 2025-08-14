# PowerShell script to test Windows CMake build with MSVC

# Find Visual Studio installation
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -latest -products * -requires Microsoft.Component.MSBuild -property installationPath
    if ($vsPath) {
        Write-Host "Found Visual Studio at: $vsPath"
        
        # Import Visual Studio environment
        $vsDevShell = Join-Path $vsPath "Common7\Tools\Microsoft.DevShell.dll"
        if (Test-Path $vsDevShell) {
            Import-Module $vsDevShell
            Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments "-arch=x64"
        } else {
            # Fallback to vcvarsall.bat
            $vcvarsall = Join-Path $vsPath "VC\Auxiliary\Build\vcvarsall.bat"
            if (Test-Path $vcvarsall) {
                & cmd /c "`"$vcvarsall`" x64 && set" | ForEach-Object {
                    if ($_ -match "^([^=]+)=(.*)$") {
                        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
                    }
                }
            }
        }
    } else {
        Write-Error "Visual Studio not found"
        exit 1
    }
} else {
    Write-Error "vswhere.exe not found"
    exit 1
}

# Check if tools are available
$clFound = Get-Command cl.exe -ErrorAction SilentlyContinue
$cmakeFound = Get-Command cmake.exe -ErrorAction SilentlyContinue

if (-not $clFound) {
    Write-Error "cl.exe not found after setting up VS environment"
    exit 1
}

if (-not $cmakeFound) {
    Write-Error "cmake.exe not found. Please install CMake."
    exit 1
}

Write-Host "Build environment ready."
Write-Host "cl.exe location: $((Get-Command cl.exe).Source)"
Write-Host "cmake.exe location: $((Get-Command cmake.exe).Source)"

# Create build directory
$buildDir = "build"
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

# Run CMake configuration with vcpkg toolchain
Write-Host "`nConfiguring with CMake using vcpkg..."
Push-Location $buildDir
try {
    $vcpkgRoot = Join-Path (Split-Path $PSScriptRoot) "vcpkg"
    $vcpkgToolchain = Join-Path $vcpkgRoot "scripts\buildsystems\vcpkg.cmake"
    
    if (-not (Test-Path $vcpkgToolchain)) {
        Write-Error "vcpkg toolchain file not found at: $vcpkgToolchain"
        exit 1
    }
    
    Write-Host "Using vcpkg toolchain: $vcpkgToolchain"
    
    # Set VCPKG_INSTALLED_DIR to point to the parent's vcpkg_installed directory
    $vcpkgInstalledDir = Join-Path (Split-Path $PSScriptRoot) "vcpkg_installed"
    
    cmake .. -G "Visual Studio 17 2022" -A x64 `
        -DCMAKE_TOOLCHAIN_FILE="$vcpkgToolchain" `
        -DVCPKG_TARGET_TRIPLET="x64-windows" `
        -DVCPKG_INSTALLED_DIR="$vcpkgInstalledDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "CMake configuration failed"
        exit 1
    }
    
    Write-Host "`nBuilding with MSBuild..."
    cmake --build . --config Release
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed"
        exit 1
    }
    
    Write-Host "`nBuild completed successfully!"
    
    # Run tests if built
    if (Test-Path "Release\test_fst_reader.exe") {
        Write-Host "`nRunning tests..."
        .\Release\test_fst_reader.exe
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Tests failed"
            exit 1
        }
        Write-Host "Tests passed!"
    }
} finally {
    Pop-Location
}