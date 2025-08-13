#!/usr/bin/env python3
"""Test script to verify type hints work correctly"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "python"))

from pylibfst import Waveform, Hierarchy, Var, Signal, SignalChangeIter

def test_types() -> None:
    """Test that type hints work properly"""
    
    # Test Waveform initialization
    wave: Waveform = Waveform("test.fst", multi_threaded=True, load_body=True)
    
    # Test hierarchy access
    hier: Hierarchy = wave.hierarchy
    
    # Test variable iteration
    for var in hier.all_vars():
        # Type should be inferred as Var
        name: str = var.name(hier)
        full_name: str = var.full_name(hier)
        var_type: str = var.var_type()
        is_real: bool = var.is_real()
        
        # Test signal loading
        signal: Signal = wave.get_signal(var)
        
        # Test signal methods
        value = signal.value_at_time(0)  # Union[int, str, float, None]
        
        # Test iterator
        changes: SignalChangeIter = signal.all_changes()
        for time, val in changes:
            # time should be int
            # val should be Union[int, str, float]
            pass
        
        break  # Just test first variable
    
    # Test signal loading by path
    signal2: Signal = wave.get_signal_from_path("top.module.signal")
    
    # Test multiple signal loading
    vars_list: list[Var] = list(hier.all_vars())[:5]
    signals: list[Signal] = wave.load_signals(vars_list)
    
    print("✓ All type annotations work correctly")

if __name__ == "__main__":
    # This would fail at runtime without a real FST file,
    # but type checkers can validate the types
    print("Type test script - for type checking only")