# build_and_run.ps1 - Build and test libfst
# This script sources the environment setup, builds the project, and runs tests

# Source the environment setup
. "$PSScriptRoot\setup_env.ps1"

if ($env:LIBFST_ENV_INITIALIZED -ne "1") {
    Write-Error "Failed to initialize environment"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building libfst with MSVC" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Create build directory if it doesn't exist
$buildDir = Join-Path $PSScriptRoot "build"
if (-not (Test-Path $buildDir)) {
    Write-Host ""
    Write-Host "Creating build directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

# Configure with CMake if not already configured
$cmakeCache = Join-Path $buildDir "CMakeCache.txt"
if (-not (Test-Path $cmakeCache)) {
    Write-Host ""
    Write-Host "Configuring with CMake..." -ForegroundColor Yellow
    
    $vcpkgRoot = Join-Path (Split-Path $PSScriptRoot) "vcpkg"
    $vcpkgToolchain = Join-Path $vcpkgRoot "scripts\buildsystems\vcpkg.cmake"
    $vcpkgInstalled = Join-Path (Split-Path $PSScriptRoot) "vcpkg_installed"
    
    # Find cl.exe for Ninja (needs explicit compiler path)
    $clPath = (Get-Command cl.exe -ErrorAction SilentlyContinue).Source
    if ($clPath) {
        Write-Host "Using compiler: $clPath" -ForegroundColor Green
    }
    
    cmake -B $buildDir `
        -G Ninja `
        -DCMAKE_BUILD_TYPE=Release `
        -DCMAKE_C_COMPILER="$clPath" `
        -DCMAKE_CXX_COMPILER="$clPath" `
        -DCMAKE_TOOLCHAIN_FILE="$vcpkgToolchain" `
        -DVCPKG_TARGET_TRIPLET="x64-windows" `
        -DVCPKG_INSTALLED_DIR="$vcpkgInstalled"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "CMake configuration failed"
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "CMake already configured (delete build/ to reconfigure)" -ForegroundColor Green
}

# Build the project
Write-Host ""
Write-Host "Building project with Ninja..." -ForegroundColor Yellow
cmake --build $buildDir

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed"
    exit 1
}

Write-Host ""
Write-Host "Build completed successfully!" -ForegroundColor Green

# Check if test executable exists
$testExe = Join-Path $buildDir "test_fst_reader.exe"
if (Test-Path $testExe) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Running tests" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    # Change to build directory for test to find relative paths
    Push-Location $buildDir
    try {
        & $testExe
        $testResult = $LASTEXITCODE
        
        if ($testResult -eq 0) {
            Write-Host ""
            Write-Host "All tests passed!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Tests failed with exit code: $testResult" -ForegroundColor Red
            exit $testResult
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host ""
    Write-Host "Test executable not found. Build may have partially failed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Build and test complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Library location: $buildDir\fst.lib" -ForegroundColor Cyan
Write-Host "Test executable:  $testExe" -ForegroundColor Cyan