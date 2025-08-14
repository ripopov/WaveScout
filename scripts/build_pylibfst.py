#!/usr/bin/env python3
"""Build pylibfst before poetry install."""

import subprocess
import sys
from pathlib import Path


def main():
    """Build pylibfst using maturin."""
    project_root = Path(__file__).parent.parent
    pylibfst_dir = project_root / "pylibfst"
    
    print("Building pylibfst...")
    
    # Build pylibfst with maturin
    print(f"Building pylibfst in {pylibfst_dir}")
    subprocess.run([sys.executable, "-m", "maturin", "develop", "--release"], 
                  cwd=pylibfst_dir, check=True)
    
    print("pylibfst built successfully!")


if __name__ == "__main__":
    main()