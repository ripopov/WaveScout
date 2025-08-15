# setup_env.ps1 - PowerShell environment setup for WaveScout development
# This script sets up Visual Studio and Python environment for building WaveScout
# Usage: . .\setup_env.ps1

# Check if already initialized
if ($env:WAVESCOUT_ENV_INITIALIZED -eq "1") {
    Write-Host "Environment already initialized." -ForegroundColor Green
    return
}

Write-Host "Setting up WaveScout development environment..." -ForegroundColor Cyan

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

# Add vcpkg to PATH if present
$vcpkgRoot = Join-Path $PSScriptRoot "vcpkg"
if (Test-Path $vcpkgRoot) {
    $vcpkgExe = Join-Path $vcpkgRoot "vcpkg.exe"
    if (Test-Path $vcpkgExe) {
        $currentPath = $env:PATH
        if ($currentPath -notlike "*$vcpkgRoot*") {
            $env:PATH = "$vcpkgRoot;$currentPath"
            Write-Host "Added vcpkg to PATH" -ForegroundColor Green
        }
        
        # Set vcpkg environment variables
        $env:VCPKG_ROOT = $vcpkgRoot
        $env:VCPKG_DEFAULT_TRIPLET = "x64-windows"
        $env:VCPKG_INSTALLED_DIR = Join-Path $PSScriptRoot "vcpkg_installed"
    }
}

# Add Python Scripts directory to PATH for user-installed packages
$pythonScriptsPath = "$env:APPDATA\Python\Python313\Scripts"
if (Test-Path $pythonScriptsPath) {
    $currentPath = $env:PATH
    if ($currentPath -notlike "*$pythonScriptsPath*") {
        $env:PATH = "$pythonScriptsPath;$currentPath"
        Write-Host "Added Python Scripts to PATH" -ForegroundColor Green
    }
}

# Check for Poetry in project virtual environment
$venvPath = Join-Path $PSScriptRoot ".venv"
$poetryExe = Join-Path $venvPath "Scripts\poetry.exe"
if (Test-Path $poetryExe) {
    Write-Host "Found Poetry in project virtual environment" -ForegroundColor Green
} else {
    # Check for system Poetry
    $poetryCmd = Get-Command poetry -ErrorAction SilentlyContinue
    if (-not $poetryCmd) {
        Write-Warning "Poetry not found. Please install Poetry or run 'make install' first."
    }
}

# Verify tools are available
$tools = @{
    "cl.exe" = "MSVC compiler"
    "make.exe" = "Make build system"
    "python.exe" = "Python"
}

# Optional tools
$optionalTools = @{
    "poetry.exe" = "Poetry package manager"
    "cargo.exe" = "Rust toolchain"
    "maturin.exe" = "Maturin (Python/Rust bindings)"
}

Write-Host ""
Write-Host "Verifying required tools:" -ForegroundColor Cyan
$allRequiredToolsFound = $true

foreach ($tool in $tools.Keys) {
    $toolPath = Get-Command $tool -ErrorAction SilentlyContinue
    if ($toolPath) {
        Write-Host "  OK $($tools[$tool]): $($toolPath.Source)" -ForegroundColor Green
    } else {
        Write-Host "  MISSING $($tools[$tool]): NOT FOUND" -ForegroundColor Red
        $allRequiredToolsFound = $false
    }
}

Write-Host ""
Write-Host "Checking optional tools:" -ForegroundColor Cyan
foreach ($tool in $optionalTools.Keys) {
    $toolPath = Get-Command $tool -ErrorAction SilentlyContinue
    if ($toolPath) {
        Write-Host "  OK $($optionalTools[$tool]): $($toolPath.Source)" -ForegroundColor Green
    } else {
        Write-Host "  -- $($optionalTools[$tool]): Not found (optional)" -ForegroundColor Yellow
    }
}

if (-not $allRequiredToolsFound) {
    Write-Error "Some required tools are missing. Please install them first."
    return
}

# Note: We don't set CC/CXX environment variables here because cc-rs
# (used by Rust builds) will automatically find cl.exe from the Visual Studio
# environment that we've already set up. Setting CC with spaces in the path
# can cause issues with some build tools.

# Set environment marker
$env:WAVESCOUT_ENV_INITIALIZED = "1"

Write-Host ""
Write-Host "Environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
Write-Host "  make install    - Install dependencies and build pywellen"
Write-Host "  make dev        - Run WaveScout application"
Write-Host "  make test       - Run tests"
Write-Host "  make typecheck  - Run type checking"
Write-Host ""
Write-Host "For first-time setup, run: make install" -ForegroundColor Yellow