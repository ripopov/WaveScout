#!/usr/bin/env python3
"""Build pylibfst before poetry install."""

import os
import platform
import subprocess
import sys
from pathlib import Path


def main():
    """Build pylibfst using maturin."""
    project_root = Path(__file__).parent.parent
    pylibfst_dir = project_root / "pylibfst"
    
    print("Building pylibfst...")
    
    # On Windows, use the Windows-specific build script
    if platform.system() == "Windows":
        windows_build_script = project_root / "scripts" / "build_pylibfst_windows.py"
        if windows_build_script.exists():
            print("Using Windows-specific build script...")
            result = subprocess.run([sys.executable, str(windows_build_script)])
            if result.returncode != 0:
                raise RuntimeError("Failed to build pylibfst on Windows")
            return
    
    # Build pylibfst with maturin (Linux/macOS or fallback)
    print(f"Building pylibfst in {pylibfst_dir}")
    subprocess.run([sys.executable, "-m", "maturin", "develop", "--release"], 
                  cwd=pylibfst_dir, check=True)
    
    print("pylibfst built successfully!")


if __name__ == "__main__":
    main()