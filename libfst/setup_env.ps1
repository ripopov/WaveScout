# setup_env.ps1 - PowerShell environment setup for libfst development
# This script sets up Visual Studio, CMake, and vcpkg for building libfst
# Usage: . .\setup_env.ps1

# Check if already initialized
if ($env:LIBFST_ENV_INITIALIZED -eq "1") {
    Write-Host "Environment already initialized." -ForegroundColor Green
    return
}

Write-Host "Setting up libfst development environment..." -ForegroundColor Cyan

# Find Visual Studio installation
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vsWhere)) {
    Write-Error "vswhere.exe not found. Please install Visual Studio 2022."
    return
}

$vsPath = & $vsWhere -latest -products * -requires Microsoft.Component.MSBuild -property installationPath
if (-not $vsPath) {
    Write-Error "Visual Studio not found. Please install Visual Studio 2022 with C++ workload."
    return
}

Write-Host "Found Visual Studio at: $vsPath" -ForegroundColor Green

# Import Visual Studio environment
$vsDevShell = Join-Path $vsPath "Common7\Tools\Microsoft.DevShell.dll"
if (Test-Path $vsDevShell) {
    Import-Module $vsDevShell
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments "-arch=x64"
} else {
    # Fallback method using vcvarsall.bat
    $vcvarsall = Join-Path $vsPath "VC\Auxiliary\Build\vcvarsall.bat"
    if (Test-Path $vcvarsall) {
        Write-Host "Using vcvarsall.bat to setup environment..." -ForegroundColor Yellow
        $envVars = & cmd /c "`"$vcvarsall`" x64 && set"
        foreach ($line in $envVars) {
            if ($line -match "^([^=]+)=(.*)$") {
                $varName = $matches[1]
                $varValue = $matches[2]
                # Only set environment variables that are different
                $currentValue = [System.Environment]::GetEnvironmentVariable($varName, "Process")
                if ($currentValue -ne $varValue) {
                    [System.Environment]::SetEnvironmentVariable($varName, $varValue, "Process")
                }
            }
        }
    } else {
        Write-Error "Could not find Visual Studio development tools."
        return
    }
}

# Add vcpkg to PATH if not already there
$vcpkgRoot = Join-Path (Split-Path $PSScriptRoot) "vcpkg"
if (Test-Path $vcpkgRoot) {
    $vcpkgExe = Join-Path $vcpkgRoot "vcpkg.exe"
    if (Test-Path $vcpkgExe) {
        $currentPath = $env:PATH
        if ($currentPath -notlike "*$vcpkgRoot*") {
            $env:PATH = "$vcpkgRoot;$currentPath"
            Write-Host "Added vcpkg to PATH" -ForegroundColor Green
        }
    }
}

# Set vcpkg environment variables
$env:VCPKG_ROOT = $vcpkgRoot
$env:VCPKG_DEFAULT_TRIPLET = "x64-windows"
$env:VCPKG_INSTALLED_DIR = Join-Path (Split-Path $PSScriptRoot) "vcpkg_installed"

# Verify tools are available
$tools = @{
    "cl.exe" = "MSVC compiler"
    "cmake.exe" = "CMake"
    "ninja.exe" = "Ninja build system"
    "vcpkg.exe" = "vcpkg package manager"
}

Write-Host ""
Write-Host "Verifying tools:" -ForegroundColor Cyan
$allToolsFound = $true

foreach ($tool in $tools.Keys) {
    $toolPath = Get-Command $tool -ErrorAction SilentlyContinue
    if ($toolPath) {
        Write-Host "  OK $($tools[$tool]): $($toolPath.Source)" -ForegroundColor Green
    } else {
        Write-Host "  MISSING $($tools[$tool]): NOT FOUND" -ForegroundColor Red
        $allToolsFound = $false
    }
}

if (-not $allToolsFound) {
    Write-Warning "Some tools are missing. Build may fail."
}

# Set compiler paths for Ninja (required due to spaces in paths)
# This must be done after verifying tools are available
$clPath = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($clPath) {
    $env:CC = $clPath.Source
    $env:CXX = $clPath.Source
    Write-Host ""
    Write-Host "Compiler environment variables set for Ninja:" -ForegroundColor Cyan
    Write-Host "  CC=$($env:CC)" -ForegroundColor Green
    Write-Host "  CXX=$($env:CXX)" -ForegroundColor Green
}

# Set environment marker
$env:LIBFST_ENV_INITIALIZED = "1"

# Set convenient aliases
Set-Alias -Name build -Value "cmake --build build" -Scope Global -ErrorAction SilentlyContinue
Set-Alias -Name test -Value ".\build\test_fst_reader.exe" -Scope Global -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Environment setup complete!" -ForegroundColor Green
Write-Host "You can now use cmake, cl, and vcpkg commands." -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
$vcpkgInstalledDir = Join-Path (Split-Path $PSScriptRoot) "vcpkg_installed"
$cmakeCmd = "cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=`"$vcpkgRoot\scripts\buildsystems\vcpkg.cmake`" -DVCPKG_TARGET_TRIPLET=`"x64-windows`" -DVCPKG_INSTALLED_DIR=`"$vcpkgInstalledDir`""
Write-Host "  Configure: $cmakeCmd"
Write-Host "  Build:     cmake --build build"
Write-Host "  Test:      .\build\test_fst_reader.exe"