#!/usr/bin/env python3
"""Build script for pylibfst on Windows - ensures proper environment setup."""

import os
import sys
import subprocess
from pathlib import Path

def setup_visual_studio_env():
    """Set up Visual Studio environment variables for the build."""
    # Check if cl.exe is already available
    result = subprocess.run(["where", "cl.exe"], capture_output=True, shell=True)
    if result.returncode == 0:
        print("Visual Studio environment already set up")
        return True
    
    # Find VS installation
    vswhere_path = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    if not vswhere_path.exists():
        vswhere_path = Path(r"C:\Program Files\Microsoft Visual Studio\Installer\vswhere.exe")
    
    if not vswhere_path.exists():
        print("ERROR: vswhere.exe not found. Please install Visual Studio with C++ build tools.")
        return False
    
    # Get VS installation path
    result = subprocess.run([
        str(vswhere_path),
        "-latest",
        "-requires", "Microsoft.Component.MSBuild",
        "-products", "*",
        "-property", "installationPath"
    ], capture_output=True, text=True)
    
    if result.returncode != 0 or not result.stdout.strip():
        print("ERROR: Visual Studio installation not found")
        return False
    
    vs_path = Path(result.stdout.strip())
    vcvars_path = vs_path / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    
    if not vcvars_path.exists():
        print(f"ERROR: vcvars64.bat not found at {vcvars_path}")
        return False
    
    print(f"Found Visual Studio at: {vs_path}")
    
    # Get environment variables from vcvars64.bat
    cmd = f'"{vcvars_path}" && set'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    
    if result.returncode != 0:
        print("ERROR: Failed to run vcvars64.bat")
        return False
    
    # Parse and set environment variables
    for line in result.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            # Don't set CC or CXX environment variables from vcvars - let cc-rs find it
            if key.upper() not in ('CC', 'CXX'):
                os.environ[key] = value
    
    # Explicitly unset CC and CXX to ensure cc-rs auto-detects
    if 'CC' in os.environ:
        del os.environ['CC']
    if 'CXX' in os.environ:
        del os.environ['CXX']
    
    print("Visual Studio environment variables set")
    return True

def main():
    """Main build function."""
    # Get project root
    project_root = Path(__file__).parent.parent
    pylibfst_dir = project_root / "pylibfst"
    
    if not pylibfst_dir.exists():
        print(f"ERROR: pylibfst directory not found at {pylibfst_dir}")
        return 1
    
    # Setup Visual Studio environment
    if not setup_visual_studio_env():
        print("ERROR: Failed to setup Visual Studio environment")
        return 1
    
    # Set VCPKG_ROOT if available
    vcpkg_root = project_root / "vcpkg"
    if vcpkg_root.exists():
        os.environ["VCPKG_ROOT"] = str(vcpkg_root)
        vcpkg_installed = project_root / "vcpkg_installed" / "x64-windows"
        if vcpkg_installed.exists():
            # Add vcpkg lib path to LIB environment variable
            lib_path = vcpkg_installed / "lib"
            if lib_path.exists():
                current_lib = os.environ.get("LIB", "")
                os.environ["LIB"] = f"{lib_path};{current_lib}"
                print(f"Added vcpkg lib path: {lib_path}")
    
    print(f"Building pylibfst in {pylibfst_dir}")
    
    # Run maturin develop
    result = subprocess.run(
        [sys.executable, "-m", "maturin", "develop", "--release"],
        cwd=pylibfst_dir
    )
    
    if result.returncode != 0:
        print("ERROR: Failed to build pylibfst")
        return 1
    
    print("pylibfst built successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())