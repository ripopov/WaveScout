#!/usr/bin/env python3
"""Debug script to identify segfault location"""

import sys
import os
sys.path.insert(0, 'python')

print("1. Starting debug script")

try:
    import pylibfst
    print("2. Module imported successfully")
except Exception as e:
    print(f"Failed to import: {e}")
    sys.exit(1)

# Check if test file exists
fst_file = '../test_inputs/des.fst'
if not os.path.exists(fst_file):
    print(f"File not found: {fst_file}")
    # Try other locations
    for path in ['test_inputs/des.fst', '../../test_inputs/des.fst']:
        if os.path.exists(path):
            fst_file = path
            print(f"Found file at: {fst_file}")
            break
    else:
        print("No FST file found")
        sys.exit(1)

print(f"3. Attempting to load: {fst_file}")
print("4. Creating Waveform object...")

try:
    # This is where the segfault likely occurs
    wave = pylibfst.Waveform(fst_file)
    print("5. Waveform created successfully")
except Exception as e:
    print(f"Exception during Waveform creation: {e}")
    import traceback
    traceback.print_exc()