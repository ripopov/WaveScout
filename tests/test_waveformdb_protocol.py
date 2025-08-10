"""Tests for WaveformDB protocol conformance and new helper methods."""

import pytest
from pathlib import Path
from typing import TYPE_CHECKING

from wavescout.waveform_db import WaveformDB
from wavescout.protocols import WaveformDBProtocol

if TYPE_CHECKING:
    from pywellen import Var


def test_waveformdb_conforms_to_protocol():
    """Test that WaveformDB provides all required protocol methods."""
    db = WaveformDB()
    
    # Check all protocol methods exist
    assert hasattr(db, 'find_handle_by_path')
    assert hasattr(db, 'find_handle_by_name')
    assert hasattr(db, 'get_handle_for_var')
    assert hasattr(db, 'get_var')
    assert hasattr(db, 'get_all_vars_for_handle')
    assert hasattr(db, 'iter_handles_and_vars')
    assert hasattr(db, 'get_var_bitwidth')
    assert hasattr(db, 'get_time_table')
    assert hasattr(db, 'get_timescale')
    
    # Check attributes
    assert hasattr(db, 'waveform')
    assert hasattr(db, 'hierarchy')
    
    # Type check - ensure it's protocol compatible
    protocol_db: WaveformDBProtocol = db  # This should not raise type errors


def test_find_handle_by_path():
    """Test find_handle_by_path with and without TOP prefix."""
    # Find a test VCD file
    test_dir = Path(__file__).parent.parent / "test_inputs"
    vcd_file = test_dir / "swerv1.vcd"
    
    if not vcd_file.exists():
        pytest.skip(f"Test VCD file not found: {vcd_file}")
    
    db = WaveformDB()
    db.open(str(vcd_file))
    
    # Get some variables to test with
    handles_and_vars = db.iter_handles_and_vars()
    test_cases = []
    
    for handle, var_list in handles_and_vars[:5]:  # Test first 5 signals
        if var_list:
            var = var_list[0]
            full_name = var.full_name(db.hierarchy)
            test_cases.append((handle, full_name))
    
    # Test exact path lookup
    for expected_handle, full_path in test_cases:
        found_handle = db.find_handle_by_path(full_path)
        assert found_handle == expected_handle, f"Failed to find {full_path}"
    
    # Test the TOP prefix addition for simple names
    # The logic only adds TOP. prefix for names without dots
    # First, find a signal with pattern "TOP.simple_name" (no dots after TOP.)
    simple_top_signal = None
    for expected_handle, full_path in test_cases:
        if full_path.startswith("TOP.") and full_path.count(".") == 1:
            # This is a simple signal directly under TOP
            simple_top_signal = (expected_handle, full_path)
            break
    
    if simple_top_signal:
        expected_handle, full_path = simple_top_signal
        short_name = full_path[4:]  # Remove "TOP."
        found_handle = db.find_handle_by_path(short_name)
        assert found_handle == expected_handle, f"Failed to find {short_name} (should resolve to {full_path})"
    
    # Test non-existent path
    assert db.find_handle_by_path("non.existent.signal") is None
    assert db.find_handle_by_path("nonexistent") is None


def test_get_var_bitwidth():
    """Test get_var_bitwidth for normal and default cases."""
    test_dir = Path(__file__).parent.parent / "test_inputs"
    vcd_file = test_dir / "swerv1.vcd"
    
    if not vcd_file.exists():
        pytest.skip(f"Test VCD file not found: {vcd_file}")
    
    db = WaveformDB()
    db.open(str(vcd_file))
    
    # Test with actual signals
    handles_and_vars = db.iter_handles_and_vars()
    tested_widths = set()
    
    for handle, var_list in handles_and_vars[:20]:  # Test first 20 signals
        if var_list:
            var = var_list[0]
            
            # Get bit width using new method
            bit_width = db.get_var_bitwidth(handle)
            assert isinstance(bit_width, int)
            assert bit_width > 0
            
            # Verify it matches the var's bitwidth if available
            if hasattr(var, 'bitwidth'):
                expected_width = var.bitwidth()
                assert bit_width == expected_width
                tested_widths.add(bit_width)
    
    # Ensure we tested various bit widths
    assert len(tested_widths) > 0, "Should have tested at least one signal with bitwidth"
    
    # Test with invalid handle (should return default)
    invalid_handle = 999999
    assert db.get_var_bitwidth(invalid_handle) == 32  # Default value


def test_iter_handles_and_vars_returns_iterable():
    """Test that iter_handles_and_vars returns an iterable of correct type."""
    test_dir = Path(__file__).parent.parent / "test_inputs"
    vcd_file = test_dir / "swerv1.vcd"
    
    if not vcd_file.exists():
        pytest.skip(f"Test VCD file not found: {vcd_file}")
    
    db = WaveformDB()
    db.open(str(vcd_file))
    
    # Get the iterable
    handles_and_vars = db.iter_handles_and_vars()
    
    # Check it's iterable
    assert hasattr(handles_and_vars, '__iter__')
    
    # Check the structure
    count = 0
    for item in handles_and_vars:
        assert isinstance(item, tuple)
        assert len(item) == 2
        
        handle, var_list = item
        assert isinstance(handle, int)
        assert isinstance(var_list, list)
        
        # Each var in the list should be a Var object
        for var in var_list:
            assert hasattr(var, 'full_name')  # Basic check for Var object
            assert hasattr(var, 'bitwidth')
        
        count += 1
        if count >= 5:  # Just test first 5
            break
    
    assert count > 0, "Should have at least one handle/var pair"


def test_protocol_methods_with_empty_db():
    """Test protocol methods work correctly with an empty/unloaded database."""
    db = WaveformDB()
    
    # All methods should handle empty DB gracefully
    assert db.find_handle_by_path("any.path") is None
    assert db.find_handle_by_name("any_name") is None
    assert db.get_var(0) is None
    assert db.get_all_vars_for_handle(0) == []
    assert list(db.iter_handles_and_vars()) == []
    assert db.get_var_bitwidth(0) == 32  # Default
    assert db.get_time_table() is None
    assert db.get_timescale() is None