#!/usr/bin/env python3
"""Simple test for pylibfst"""

import sys
sys.path.insert(0, 'python')

try:
    import pylibfst
    print("✓ Module imported")
    
    # Try to load a file
    fst_file = '../test_inputs/des.fst'
    print(f"Loading: {fst_file}")
    
    try:
        wave = pylibfst.Waveform(fst_file)
        print("✓ Waveform created")
        
        # Try to access hierarchy
        hier = wave.hierarchy
        print("✓ Hierarchy accessed")
        
    except Exception as e:
        print(f"✗ Error creating waveform: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()