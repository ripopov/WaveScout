#!/usr/bin/env python3
"""Build pywellen before poetry install."""

import subprocess
import sys
from pathlib import Path


def main():
    """Build pywellen using maturin."""
    project_root = Path(__file__).parent.parent
    pywellen_dir = project_root / "wellen" / "pywellen"
    
    print("Building pywellen...")
    
    # Install maturin if not present
    try:
        subprocess.run([sys.executable, "-m", "pip", "show", "maturin"], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Installing maturin...")
        subprocess.run([sys.executable, "-m", "pip", "install", "maturin"], 
                      check=True)
    
    # Build pywellen with maturin
    print(f"Building pywellen in {pywellen_dir}")
    subprocess.run([sys.executable, "-m", "maturin", "develop", "--release"], 
                  cwd=pywellen_dir, check=True)
    
    print("pywellen built successfully!")


if __name__ == "__main__":
    main()