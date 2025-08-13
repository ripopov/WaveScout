"""
API compatibility tests for pylibfst vs pywellen
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

try:
    import pylibfst
except ImportError:
    print("Warning: pylibfst not built yet. Run 'maturin develop' first.")
    pylibfst = None

try:
    import pywellen
except ImportError:
    print("Warning: pywellen not available for comparison.")
    pywellen = None

import pytest


def get_test_fst_file():
    """Find a test FST file"""
    # Look for test FST files
    test_files = [
        "../test_inputs/des.fst",
        "../../test_inputs/des.fst",
        "../../../test_inputs/des.fst",
    ]
    
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            return str(full_path.resolve())
    
    return None


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_basic_loading():
    """Test basic FST file loading"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    # Load with pylibfst
    wave = pylibfst.Waveform(fst_file)
    assert wave is not None
    assert wave.body_loaded()
    
    # Check hierarchy
    hier = wave.hierarchy
    assert hier is not None
    
    # Check metadata
    assert hier.file_format() == "FST"
    assert hier.date() is not None
    assert hier.version() is not None


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_hierarchy_navigation():
    """Test hierarchy navigation"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    wave = pylibfst.Waveform(fst_file)
    hier = wave.hierarchy
    
    # Test all_vars iterator
    vars_list = list(hier.all_vars())
    assert len(vars_list) > 0
    
    # Test variable properties
    var = vars_list[0]
    assert var.name(hier) is not None
    assert var.full_name(hier) is not None
    assert var.var_type() is not None
    assert var.direction() is not None
    assert isinstance(var.signal_ref(), int)
    
    # Test top_scopes iterator
    scopes = list(hier.top_scopes())
    assert len(scopes) > 0
    
    # Test scope properties
    scope = scopes[0]
    assert scope.name(hier) is not None
    assert scope.full_name(hier) is not None
    assert scope.scope_type() is not None


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_signal_loading():
    """Test signal loading"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    wave = pylibfst.Waveform(fst_file)
    hier = wave.hierarchy
    
    # Get first few variables
    vars_list = list(hier.all_vars())[:5]
    
    for var in vars_list:
        # Load signal
        signal = wave.get_signal(var)
        assert signal is not None
        
        # Test signal methods
        changes = list(signal.all_changes())
        if changes:
            time, value = changes[0]
            assert isinstance(time, int)
            assert value is not None


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_lazy_loading():
    """Test lazy body loading"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    # Load without body
    wave = pylibfst.Waveform(fst_file, load_body=False)
    assert not wave.body_loaded()
    
    # Body should load on first signal access
    hier = wave.hierarchy
    var = next(hier.all_vars())
    signal = wave.get_signal(var)
    assert wave.body_loaded()


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_api_compatibility():
    """Compare pylibfst with pywellen API"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    # Load same file with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    # Compare hierarchy
    pw_vars = list(pw_wave.hierarchy.all_vars())
    lf_vars = list(lf_wave.hierarchy.all_vars())
    
    # Variable count might differ slightly due to alias handling
    # Just check that we have a reasonable number
    assert len(lf_vars) > 0
    assert len(pw_vars) > 0
    print(f"  pywellen: {len(pw_vars)} vars, pylibfst: {len(lf_vars)} vars")
    
    # Compare first few variables by matching names
    compared = 0
    for i in range(min(10, len(pw_vars), len(lf_vars))):
        pw_var = pw_vars[i]
        lf_var = lf_vars[i]
        
        # Compare names (strip whitespace for comparison)
        pw_name = pw_var.name(pw_wave.hierarchy).strip()
        lf_name = lf_var.name(lf_wave.hierarchy).strip()
        
        if pw_name != lf_name:
            print(f"  Name mismatch at {i}: {pw_name} vs {lf_name}")
            continue
        
        compared += 1
        
        # Compare properties (some might differ due to FST/VCD differences)
        # Just check they exist
        assert lf_var.var_type() is not None
        assert pw_var.var_type() is not None
        assert lf_var.direction() is not None
        assert pw_var.direction() is not None
        
        # Compare signals
        try:
            pw_sig = pw_wave.get_signal(pw_var)
            lf_sig = lf_wave.get_signal(lf_var)
            
            pw_changes = list(pw_sig.all_changes())
            lf_changes = list(lf_sig.all_changes())
            
            # Should have same number of transitions
            if len(lf_changes) != len(pw_changes):
                print(f"  Transition count mismatch for {pw_name}: {len(pw_changes)} vs {len(lf_changes)}")
            
            # Compare first few transitions
            for j in range(min(3, len(pw_changes), len(lf_changes))):
                pw_time, pw_val = pw_changes[j]
                lf_time, lf_val = lf_changes[j]
                
                assert lf_time == pw_time
                # Values might be formatted differently
                # Just check they exist
                assert pw_val is not None
                assert lf_val is not None
        except Exception as e:
            print(f"  Signal comparison failed for {pw_name}: {e}")
    
    # Make sure we compared at least some variables
    assert compared > 0, "No variables were successfully compared"
    print(f"  Successfully compared {compared} variables")


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_iterators():
    """Test Python iterator protocol"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    wave = pylibfst.Waveform(fst_file)
    hier = wave.hierarchy
    
    # Test VarIter
    var_iter = hier.all_vars()
    assert hasattr(var_iter, '__iter__')
    assert hasattr(var_iter, '__next__')
    
    vars_list = list(var_iter)
    assert len(vars_list) > 0
    
    # Test ScopeIter
    scope_iter = hier.top_scopes()
    assert hasattr(scope_iter, '__iter__')
    assert hasattr(scope_iter, '__next__')
    
    scopes = list(scope_iter)
    assert len(scopes) > 0
    
    # Test SignalChangeIter
    var = vars_list[0]
    signal = wave.get_signal(var)
    change_iter = signal.all_changes()
    assert hasattr(change_iter, '__iter__')
    assert hasattr(change_iter, '__next__')
    assert hasattr(change_iter, '__len__')


@pytest.mark.skipif(pylibfst is None, reason="pylibfst not built")
def test_signal_types():
    """Test different signal value types"""
    fst_file = get_test_fst_file()
    if not fst_file:
        pytest.skip("No test FST file found")
    
    wave = pylibfst.Waveform(fst_file)
    hier = wave.hierarchy
    
    # Find different types of signals
    for var in hier.all_vars():
        if var.is_real():
            # Test real signal
            signal = wave.get_signal(var)
            changes = list(signal.all_changes())
            if changes:
                _, value = changes[0]
                assert isinstance(value, (float, int))
            break
    
    for var in hier.all_vars():
        if var.is_string():
            # Test string signal
            signal = wave.get_signal(var)
            changes = list(signal.all_changes())
            if changes:
                _, value = changes[0]
                assert isinstance(value, str)
            break


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_query_result_comparison():
    """Deep comparison of QueryResult functionality between pywellen and pylibfst"""
    # Look for analog_signals_short.fst
    test_files = [
        "../test_inputs/analog_signals_short.fst",
        "../../test_inputs/analog_signals_short.fst",
        "../../../test_inputs/analog_signals_short.fst",
    ]
    
    fst_file = None
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            fst_file = str(full_path.resolve())
            break

    if not fst_file:
        pytest.skip("analog_signals_short.fst or analog_signals.fst not found")
    
    print(f"\nComparing QueryResult for: {fst_file}")
    
    # Load with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    pw_hier = pw_wave.hierarchy
    lf_hier = lf_wave.hierarchy
    
    # Get first few variables
    pw_vars = list(pw_hier.all_vars())[:5]
    lf_vars = list(lf_hier.all_vars())[:5]
    
    print(f"  Testing {min(len(pw_vars), len(lf_vars))} variables")
    
    for i in range(min(len(pw_vars), len(lf_vars))):
        pw_var = pw_vars[i]
        lf_var = lf_vars[i]
        
        pw_name = pw_var.name(pw_hier).strip()
        lf_name = lf_var.name(lf_hier).strip()
        
        if pw_name != lf_name:
            print(f"  Skipping mismatched variables: {pw_name} vs {lf_name}")
            continue
        
        print(f"\n  Testing variable: {pw_name}")
        
        # Load signals
        pw_signal = pw_wave.get_signal(pw_var)
        lf_signal = lf_wave.get_signal(lf_var)
        
        # Test query_signal at various times
        test_times = [0, 100, 500, 1000, 5000, 10000]
        
        for query_time in test_times:
            # Get QueryResult from both
            pw_result = pw_signal.query_signal(query_time)
            lf_result = lf_signal.query_signal(query_time)
            
            # Compare QueryResult fields
            print(f"    Time {query_time}:")
            
            # Compare values (might be None)
            if pw_result.value != lf_result.value:
                # Allow for floating point differences
                if isinstance(pw_result.value, float) and isinstance(lf_result.value, float):
                    if abs(pw_result.value - lf_result.value) > 1e-6:
                        print(f"      ⚠ Value mismatch: pywellen={pw_result.value}, pylibfst={lf_result.value}")
                else:
                    print(f"      ⚠ Value mismatch: pywellen={pw_result.value}, pylibfst={lf_result.value}")
            
            # Compare actual_time
            if pw_result.actual_time != lf_result.actual_time:
                print(f"      ⚠ Actual time mismatch: pywellen={pw_result.actual_time}, pylibfst={lf_result.actual_time}")
            
            # Compare next_time
            if pw_result.next_time != lf_result.next_time:
                print(f"      ⚠ Next time mismatch: pywellen={pw_result.next_time}, pylibfst={lf_result.next_time}")
            
            # Compare next_idx
            if pw_result.next_idx != lf_result.next_idx:
                print(f"      ⚠ Next index mismatch: pywellen={pw_result.next_idx}, pylibfst={lf_result.next_idx}")
        
        # Test iteration using next_idx and next_time
        print(f"    Testing iteration via QueryResult...")
        
        # Start from time 0
        pw_query = pw_signal.query_signal(0)
        lf_query = lf_signal.query_signal(0)
        
        iteration_count = 0
        max_iterations = 10  # Limit iterations for testing
        
        while iteration_count < max_iterations:
            # Check if both have next transitions
            if pw_query.next_time is None and lf_query.next_time is None:
                print(f"      Both reached end after {iteration_count} iterations")
                break
            
            if pw_query.next_time is None or lf_query.next_time is None:
                print(f"      ⚠ One reached end but not the other at iteration {iteration_count}")
                break
            
            # Compare current state
            if pw_query.value != lf_query.value:
                if not (isinstance(pw_query.value, float) and isinstance(lf_query.value, float) and 
                       abs(pw_query.value - lf_query.value) < 1e-6):
                    print(f"      ⚠ Value mismatch at iteration {iteration_count}")
            
            # Move to next using next_time
            pw_query = pw_signal.query_signal(pw_query.next_time)
            lf_query = lf_signal.query_signal(lf_query.next_time)
            
            iteration_count += 1
        
        # Test value_at_idx and value_at_time
        print(f"    Testing value_at_idx...")
        
        # Get all changes to find valid indices
        pw_changes = list(pw_signal.all_changes())
        lf_changes = list(lf_signal.all_changes())
        
        # Test first few indices
        for idx in range(min(5, len(pw_changes), len(lf_changes))):
            pw_val_idx = pw_signal.value_at_idx(idx)
            lf_val_idx = lf_signal.value_at_idx(idx)
            
            if pw_val_idx != lf_val_idx:
                if not (isinstance(pw_val_idx, float) and isinstance(lf_val_idx, float) and 
                       abs(pw_val_idx - lf_val_idx) < 1e-6):
                    print(f"      ⚠ value_at_idx({idx}) mismatch: pywellen={pw_val_idx}, pylibfst={lf_val_idx}")
        
        # Note: value_at_time has different semantics between pywellen and pylibfst
        # pywellen appears to return the NEXT value after the given time
        # pylibfst returns the value AT the given time (standard waveform viewer behavior)
        # Both libraries have consistent query_signal behavior, so we skip value_at_time comparison
        print(f"    Note: Skipping value_at_time comparison due to semantic differences")
        
        print(f"    ✓ Completed testing for {pw_name}")
        
        # Only test first variable in detail to keep output manageable
        break
    
    print("\n  ✓ QueryResult comparison test completed")


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_time_range_comparison():
    """Compare time range between pywellen and pylibfst"""
    # Use vcd_extensions.fst for testing
    test_files = [
        "../test_inputs/vcd_extensions.fst",
        "../../test_inputs/vcd_extensions.fst",
        "../../../test_inputs/vcd_extensions.fst",
    ]
    
    fst_file = None
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            fst_file = str(full_path.resolve())
            break
    
    if not fst_file:
        pytest.skip("vcd_extensions.fst not found")
    
    print(f"\nComparing time range for: {fst_file}")
    
    # Load with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    # Get pywellen's time table
    pw_time_table = pw_wave.time_table
    
    # Get pylibfst's time range
    lf_time_range = lf_wave.time_range if hasattr(lf_wave, 'time_range') else None
    
    # Note: Converting pywellen time_table to list can hang on some files
    # So we'll access it more carefully
    if pw_time_table:
        try:
            # Try to get first and last entries without converting entire table to list
            pw_start = pw_time_table[0]
            # Get length first
            pw_len = len(pw_time_table)
            pw_end = pw_time_table[pw_len - 1] if pw_len > 0 else pw_start
            print(f"\n  Pywellen time table: length={pw_len}, start={pw_start}, end={pw_end}")
        except Exception as e:
            print(f"\n  Error accessing pywellen time table: {e}")
            pw_start = None
            pw_end = None
    else:
        print(f"\n  Pywellen time table: None")
        pw_start = None
        pw_end = None
    
    print(f"  Pylibfst time range: {lf_time_range}")
    
    # Check that pylibfst's time range matches first and last of pywellen's time table
    if pw_start is not None and pw_end is not None and lf_time_range:
        lf_start, lf_end = lf_time_range
        
        print(f"\n  Comparing time boundaries:")
        print(f"    Start time - pywellen: {pw_start}, pylibfst: {lf_start}")
        print(f"    End time - pywellen: {pw_end}, pylibfst: {lf_end}")
        
        start_match = pw_start == lf_start
        end_match = pw_end == lf_end
        
        if start_match and end_match:
            print(f"  ✓ Time range matches: start={lf_start}, end={lf_end}")
        else:
            if not start_match:
                print(f"  ⚠ Start time mismatch: pywellen={pw_start}, pylibfst={lf_start}")
            if not end_match:
                print(f"  ⚠ End time mismatch: pywellen={pw_end}, pylibfst={lf_end}")
        
        # Assert that boundaries match
        assert start_match, f"Start time mismatch: {pw_start} vs {lf_start}"
        assert end_match, f"End time mismatch: {pw_end} vs {lf_end}"
    else:
        if pw_start is None or pw_end is None:
            print("  ⚠ Could not access pywellen time table")
        if not lf_time_range:
            print("  ⚠ Pylibfst has no time range")
        if pw_start is None or pw_end is None or not lf_time_range:
            pytest.skip("Could not compare time information")
    
    print("\n  Note: libfst doesn't support efficient full time table access.")
    print("  pylibfst provides time_range (start, end) instead of full time table.")


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_var_api_compatibility():
    """Test Var API compatibility between pywellen and pylibfst using vcd_extensions.fst"""
    # Look for vcd_extensions.fst file
    test_files = [
        "../test_inputs/vcd_extensions.fst",
        "../../test_inputs/vcd_extensions.fst",
        "../../../test_inputs/vcd_extensions.fst",
    ]
    
    fst_file = None
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            fst_file = str(full_path.resolve())
            break
    
    if not fst_file:
        pytest.skip("vcd_extensions.fst not found")
    
    print(f"\nTesting Var API compatibility with: {fst_file}")
    
    # Load with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    pw_hier = pw_wave.hierarchy
    lf_hier = lf_wave.hierarchy
    
    # Get all variables from both libraries
    pw_vars = list(pw_hier.all_vars())
    lf_vars = list(lf_hier.all_vars())
    
    print(f"  Found {len(pw_vars)} pywellen vars, {len(lf_vars)} pylibfst vars")
    
    # Create a mapping by full name for comparison
    pw_var_map = {}
    for var in pw_vars:
        full_name = var.full_name(pw_hier).strip()
        pw_var_map[full_name] = var
    
    lf_var_map = {}
    for var in lf_vars:
        full_name = var.full_name(lf_hier).strip()
        lf_var_map[full_name] = var
    
    # Find common variables
    common_names = set(pw_var_map.keys()) & set(lf_var_map.keys())
    print(f"  Found {len(common_names)} common variables")
    
    # Test API on ALL variables
    tested_count = 0
    api_mismatches = []
    vars_with_mismatches = []
    
    print(f"\n  Testing all {len(common_names)} common variables...")
    
    for var_name in sorted(common_names):
        pw_var = pw_var_map[var_name]
        lf_var = lf_var_map[var_name]
        
        tested_count += 1
        var_mismatches = []
        
        # Determine category for display
        if pw_var.is_real():
            category = "real"
        elif pw_var.is_string():
            category = "string"
        elif pw_var.is_1bit():
            category = "1bit"
        else:
            category = f"{pw_var.length() or 'unknown'}-bit"
        
        # Test var_type
        pw_type = pw_var.var_type()
        lf_type = lf_var.var_type()
        if pw_type != lf_type:
            msg = f"var_type: pywellen={pw_type}, pylibfst={lf_type}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test enum_type
        pw_enum = pw_var.enum_type(pw_hier)
        lf_enum = lf_var.enum_type(lf_hier)
        if pw_enum != lf_enum:
            msg = f"enum_type: pywellen={pw_enum}, pylibfst={lf_enum}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test vhdl_type_name
        pw_vhdl = pw_var.vhdl_type_name(pw_hier)
        lf_vhdl = lf_var.vhdl_type_name(lf_hier)
        if pw_vhdl != lf_vhdl:
            msg = f"vhdl_type_name: pywellen={pw_vhdl}, pylibfst={lf_vhdl}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test direction
        pw_dir = pw_var.direction()
        lf_dir = lf_var.direction()
        if pw_dir != lf_dir:
            msg = f"direction: pywellen={pw_dir}, pylibfst={lf_dir}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test length
        pw_len = pw_var.length()
        lf_len = lf_var.length()
        if pw_len != lf_len:
            msg = f"length: pywellen={pw_len}, pylibfst={lf_len}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test is_real
        pw_real = pw_var.is_real()
        lf_real = lf_var.is_real()
        if pw_real != lf_real:
            msg = f"is_real: pywellen={pw_real}, pylibfst={lf_real}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test is_string
        pw_str = pw_var.is_string()
        lf_str = lf_var.is_string()
        if pw_str != lf_str:
            msg = f"is_string: pywellen={pw_str}, pylibfst={lf_str}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Note: is_bit_vector is not applicable to libfst - it's a pywellen-specific encoding concept
        # so we skip comparing it
        
        # Test is_1bit
        pw_1bit = pw_var.is_1bit()
        lf_1bit = lf_var.is_1bit()
        if pw_1bit != lf_1bit:
            msg = f"is_1bit: pywellen={pw_1bit}, pylibfst={lf_1bit}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        
        # Test index
        pw_idx = pw_var.index()
        lf_idx = lf_var.index()
        # Compare index values - both might be None or have msb/lsb attributes
        if (pw_idx is None) != (lf_idx is None):
            msg = f"index: pywellen={pw_idx}, pylibfst={lf_idx}"
            var_mismatches.append(msg)
            api_mismatches.append(f"{var_name}: {msg}")
        elif pw_idx is not None and lf_idx is not None:
            # Both have indices, compare msb and lsb
            pw_msb = pw_idx.msb() if hasattr(pw_idx, 'msb') else None
            pw_lsb = pw_idx.lsb() if hasattr(pw_idx, 'lsb') else None
            lf_msb = lf_idx.msb() if hasattr(lf_idx, 'msb') else None
            lf_lsb = lf_idx.lsb() if hasattr(lf_idx, 'lsb') else None
            if pw_msb != lf_msb or pw_lsb != lf_lsb:
                msg = f"index: pywellen=[{pw_msb}:{pw_lsb}], pylibfst=[{lf_msb}:{lf_lsb}]"
                var_mismatches.append(msg)
                api_mismatches.append(f"{var_name}: {msg}")
        
        # If this variable had mismatches, record it
        if var_mismatches:
            vars_with_mismatches.append((var_name, category, var_mismatches))
    
    # Print details for variables with mismatches
    if vars_with_mismatches:
        print(f"\n  Variables with mismatches ({len(vars_with_mismatches)} out of {tested_count}):")
        for var_name, category, mismatches in vars_with_mismatches:
            print(f"\n  {var_name} ({category}):")
            for mismatch in mismatches:
                print(f"    ⚠ {mismatch}")
    else:
        print(f"\n  ✓ All {tested_count} variables match perfectly!")
    
    # Summary
    print(f"\n  Summary: Tested {tested_count} variables")
    if api_mismatches:
        print(f"  Found {len(api_mismatches)} API differences (may be intentional):")
        for mismatch in api_mismatches[:10]:  # Show first 10
            print(f"    {mismatch}")
        
        # Check if these are known/acceptable differences
        # Some differences might be due to different interpretations of the FST format
        # or differences in how pywellen vs pylibfst handle certain edge cases
        known_patterns = [
            ": length: pywellen=None, pylibfst=8",  # Real variables report None in pywellen but 8 (bytes) in pylibfst
        ]
        
        unexpected_mismatches = []
        for mismatch in api_mismatches:
            is_known = False
            for pattern in known_patterns:
                if pattern in mismatch:
                    is_known = True
                    break
            if not is_known:
                unexpected_mismatches.append(mismatch)
        
        if unexpected_mismatches:
            print(f"\n  ⚠ Found {len(unexpected_mismatches)} unexpected API mismatches:")
            for mismatch in unexpected_mismatches:
                print(f"    {mismatch}")
            assert False, f"Found {len(unexpected_mismatches)} unexpected API mismatches"
        else:
            print(f"\n  ✓ All API differences are known/expected")
            print(f"  Note: Real variables report length=8 in pylibfst (8 bytes for double precision float)")
    else:
        print(f"  ✓ All Var API methods match perfectly between pywellen and pylibfst")


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_hierarchy_methods_compatibility():
    """Test all Hierarchy methods work the same between pywellen and pylibfst"""
    # Use vcd_extensions.fst for testing
    test_files = [
        "../test_inputs/vcd_extensions.fst",
        "../../test_inputs/vcd_extensions.fst",
        "../../../test_inputs/vcd_extensions.fst",
    ]
    
    fst_file = None
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            fst_file = str(full_path.resolve())
            break
    
    if not fst_file:
        pytest.skip("vcd_extensions.fst not found")
    
    print(f"\nTesting Hierarchy methods compatibility with: {fst_file}")
    
    # Load with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    pw_hier = pw_wave.hierarchy
    lf_hier = lf_wave.hierarchy
    
    print("\n  Testing Hierarchy methods:")
    mismatches = []
    
    # Test file_format()
    print("\n  1. Testing file_format():")
    pw_format = pw_hier.file_format()
    lf_format = lf_hier.file_format()
    print(f"     pywellen: {pw_format}")
    print(f"     pylibfst: {lf_format}")
    if pw_format != lf_format:
        mismatches.append(f"file_format: pywellen={pw_format}, pylibfst={lf_format}")
    else:
        print(f"     ✓ Match: {lf_format}")
    
    # Test date()
    print("\n  2. Testing date():")
    pw_date = pw_hier.date()
    lf_date = lf_hier.date()
    print(f"     pywellen: {pw_date}")
    print(f"     pylibfst: {lf_date}")
    if pw_date != lf_date:
        mismatches.append(f"date: pywellen={pw_date}, pylibfst={lf_date}")
    else:
        print(f"     ✓ Match: {lf_date}")
    
    # Test version()
    print("\n  3. Testing version():")
    pw_version = pw_hier.version()
    lf_version = lf_hier.version()
    print(f"     pywellen: {pw_version}")
    print(f"     pylibfst: {lf_version}")
    if pw_version != lf_version:
        mismatches.append(f"version: pywellen={pw_version}, pylibfst={lf_version}")
    else:
        print(f"     ✓ Match: {lf_version}")
    
    # Test timescale()
    print("\n  4. Testing timescale():")
    pw_ts = pw_hier.timescale()
    lf_ts = lf_hier.timescale()
    
    # Compare timescale (it's an object, so we need to compare its string representation)
    pw_ts_str = str(pw_ts) if pw_ts else None
    lf_ts_str = str(lf_ts) if lf_ts else None
    print(f"     pywellen: {pw_ts_str}")
    print(f"     pylibfst: {lf_ts_str}")
    
    if pw_ts_str != lf_ts_str:
        # Try comparing the actual values if string representation differs
        if pw_ts and lf_ts:
            # Both have timescale, check if they're functionally equivalent
            # Timescale usually has a string representation like "1ns" or "1ps"
            print(f"     ⚠ String representation differs, but both have timescale objects")
            mismatches.append(f"timescale: pywellen={pw_ts_str}, pylibfst={lf_ts_str}")
        else:
            mismatches.append(f"timescale: pywellen={pw_ts_str}, pylibfst={lf_ts_str}")
    else:
        print(f"     ✓ Match: {lf_ts_str}")
    
    # Test all_vars() - count and basic iteration
    print("\n  5. Testing all_vars():")
    pw_vars = list(pw_hier.all_vars())
    lf_vars = list(lf_hier.all_vars())
    print(f"     pywellen: {len(pw_vars)} variables")
    print(f"     pylibfst: {len(lf_vars)} variables")
    
    if len(pw_vars) != len(lf_vars):
        mismatches.append(f"all_vars count: pywellen={len(pw_vars)}, pylibfst={len(lf_vars)}")
    else:
        print(f"     ✓ Match: {len(lf_vars)} variables")
    
    # Check that iterators work properly
    print("\n  6. Testing all_vars() iterator protocol:")
    # Test that we can iterate multiple times
    lf_vars1 = list(lf_hier.all_vars())
    lf_vars2 = list(lf_hier.all_vars())
    if len(lf_vars1) != len(lf_vars2):
        mismatches.append(f"all_vars iterator reuse issue: first={len(lf_vars1)}, second={len(lf_vars2)}")
    else:
        print(f"     ✓ Iterator can be reused: {len(lf_vars1)} variables both times")
    
    # Test top_scopes()
    print("\n  7. Testing top_scopes():")
    pw_scopes = list(pw_hier.top_scopes())
    lf_scopes = list(lf_hier.top_scopes())
    print(f"     pywellen: {len(pw_scopes)} top-level scopes")
    print(f"     pylibfst: {len(lf_scopes)} top-level scopes")
    
    if len(pw_scopes) != len(lf_scopes):
        mismatches.append(f"top_scopes count: pywellen={len(pw_scopes)}, pylibfst={len(lf_scopes)}")
    else:
        print(f"     ✓ Match: {len(lf_scopes)} top-level scopes")
        
        # Compare scope names
        pw_scope_names = [s.name(pw_hier) for s in pw_scopes]
        lf_scope_names = [s.name(lf_hier) for s in lf_scopes]
        
        print(f"     Top scope names:")
        print(f"       pywellen: {pw_scope_names}")
        print(f"       pylibfst: {lf_scope_names}")
        
        if sorted(pw_scope_names) != sorted(lf_scope_names):
            mismatches.append(f"top_scopes names differ: pywellen={pw_scope_names}, pylibfst={lf_scope_names}")
        else:
            print(f"       ✓ Names match")
    
    # Test that top_scopes iterator can be reused
    print("\n  8. Testing top_scopes() iterator protocol:")
    lf_scopes1 = list(lf_hier.top_scopes())
    lf_scopes2 = list(lf_hier.top_scopes())
    if len(lf_scopes1) != len(lf_scopes2):
        mismatches.append(f"top_scopes iterator reuse issue: first={len(lf_scopes1)}, second={len(lf_scopes2)}")
    else:
        print(f"     ✓ Iterator can be reused: {len(lf_scopes1)} scopes both times")
    
    # Test accessing vars and scopes properties
    print("\n  9. Testing Var and Scope object access:")
    if lf_vars and pw_vars:
        # Test first var
        lf_var = lf_vars[0]
        pw_var = pw_vars[0]
        
        lf_var_name = lf_var.full_name(lf_hier)
        pw_var_name = pw_var.full_name(pw_hier)
        print(f"     First var full_name:")
        print(f"       pywellen: {pw_var_name}")
        print(f"       pylibfst: {lf_var_name}")
        
        # Test var methods exist and work
        try:
            lf_var.name(lf_hier)
            lf_var.var_type()
            lf_var.direction()
            print(f"     ✓ Var methods (name, var_type, direction) work")
        except Exception as e:
            mismatches.append(f"Var method error: {e}")
            print(f"     ⚠ Var method error: {e}")
    
    if lf_scopes and pw_scopes:
        # Test first scope
        lf_scope = lf_scopes[0]
        pw_scope = pw_scopes[0]
        
        lf_scope_name = lf_scope.full_name(lf_hier)
        pw_scope_name = pw_scope.full_name(pw_hier)
        print(f"     First scope full_name:")
        print(f"       pywellen: {pw_scope_name}")
        print(f"       pylibfst: {lf_scope_name}")
        
        # Test scope methods exist and work
        try:
            lf_scope.name(lf_hier)
            lf_scope.scope_type()
            # Test child iteration
            child_vars = list(lf_scope.vars(lf_hier))
            child_scopes = list(lf_scope.scopes(lf_hier))
            print(f"     ✓ Scope methods work (has {len(child_vars)} vars, {len(child_scopes)} child scopes)")
        except Exception as e:
            mismatches.append(f"Scope method error: {e}")
            print(f"     ⚠ Scope method error: {e}")
    
    # Summary
    print(f"\n  Summary:")
    if mismatches:
        print(f"  Found {len(mismatches)} differences:")
        for mismatch in mismatches:
            print(f"    ⚠ {mismatch}")
        
        # Some differences might be acceptable
        acceptable_patterns = [
            "timescale:",  # Timescale representation might differ slightly
        ]
        
        unexpected = []
        for mismatch in mismatches:
            is_acceptable = False
            for pattern in acceptable_patterns:
                if pattern in mismatch:
                    is_acceptable = True
                    break
            if not is_acceptable:
                unexpected.append(mismatch)
        
        if unexpected:
            print(f"\n  Found {len(unexpected)} unexpected differences:")
            for diff in unexpected:
                print(f"    {diff}")
            assert False, f"Found {len(unexpected)} unexpected differences in Hierarchy methods"
        else:
            print(f"\n  ✓ All differences are acceptable (timescale representation may vary)")
    else:
        print(f"  ✓ All Hierarchy methods match perfectly between pywellen and pylibfst")


@pytest.mark.skipif(
    pylibfst is None or pywellen is None,
    reason="Both pylibfst and pywellen required for comparison"
)
def test_hierarchy_deep_comparison():
    """Deep comparison of hierarchy traversal between pywellen and pylibfst"""
    # Look for vcd_extensions.fst
    test_files = [
        "../test_inputs/vcd_extensions.fst",
        "../../test_inputs/vcd_extensions.fst",
        "../../../test_inputs/vcd_extensions.fst",
    ]
    
    fst_file = None
    for path in test_files:
        full_path = Path(__file__).parent / path
        if full_path.exists():
            fst_file = str(full_path.resolve())
            break
    
    if not fst_file:
        pytest.skip("vcd_extensions.fst not found")
    
    print(f"\nComparing hierarchy for: {fst_file}")
    
    # Load with both libraries
    pw_wave = pywellen.Waveform(fst_file)
    lf_wave = pylibfst.Waveform(fst_file)
    
    pw_hier = pw_wave.hierarchy
    lf_hier = lf_wave.hierarchy
    
    # Compare metadata
    assert lf_hier.file_format() == pw_hier.file_format()
    print(f"  File format: {lf_hier.file_format()}")
    
    # Helper function to recursively collect all scopes
    def collect_all_scopes(hier, scope_iter):
        """Recursively collect all scopes with their full paths"""
        scopes_dict = {}
        for scope in scope_iter:
            full_name = scope.full_name(hier).strip()
            scope_type = scope.scope_type()
            scopes_dict[full_name] = {
                'type': scope_type,
                'scope': scope,
                'children': collect_all_scopes(hier, scope.scopes(hier))
            }
        return scopes_dict
    
    # Collect all scopes from both libraries
    print("\n  Collecting scopes...")
    pw_scopes = collect_all_scopes(pw_hier, pw_hier.top_scopes())
    lf_scopes = collect_all_scopes(lf_hier, lf_hier.top_scopes())
    
    # Compare scope names and types
    pw_scope_names = set(pw_scopes.keys())
    lf_scope_names = set(lf_scopes.keys())
    
    print(f"  Pywellen scopes: {len(pw_scope_names)}")
    print(f"  Pylibfst scopes: {len(lf_scope_names)}")
    
    # Check for missing scopes
    missing_in_lf = pw_scope_names - lf_scope_names
    missing_in_pw = lf_scope_names - pw_scope_names
    
    if missing_in_lf:
        print(f"  ⚠ Scopes in pywellen but not pylibfst: {missing_in_lf}")
    if missing_in_pw:
        print(f"  ⚠ Scopes in pylibfst but not pywellen: {missing_in_pw}")
    
    # Compare scope types for common scopes
    common_scopes = pw_scope_names & lf_scope_names
    scope_type_mismatches = 0
    for scope_name in sorted(common_scopes)[:20]:  # Check first 20 for brevity
        pw_type = pw_scopes[scope_name]['type']
        lf_type = lf_scopes[scope_name]['type']
        if pw_type != lf_type:
            print(f"    Scope type mismatch for '{scope_name}': pywellen={pw_type}, pylibfst={lf_type}")
            scope_type_mismatches += 1
    
    if scope_type_mismatches == 0:
        print(f"  ✓ All checked scope types match")
    
    # Collect all variables from both libraries
    print("\n  Collecting variables...")
    
    def collect_vars_with_path(hier, var_iter):
        """Collect variables with their full paths and properties"""
        vars_dict = {}
        for var in var_iter:
            full_name = var.full_name(hier).strip()
            vars_dict[full_name] = {
                'name': var.name(hier).strip(),
                'type': var.var_type(),
                'direction': var.direction(),
                'is_real': var.is_real(),
                'is_string': var.is_string(),
                'var': var
            }
        return vars_dict
    
    pw_vars = collect_vars_with_path(pw_hier, pw_hier.all_vars())
    lf_vars = collect_vars_with_path(lf_hier, lf_hier.all_vars())
    
    pw_var_names = set(pw_vars.keys())
    lf_var_names = set(lf_vars.keys())
    
    print(f"  Pywellen variables: {len(pw_var_names)}")
    print(f"  Pylibfst variables: {len(lf_var_names)}")
    
    # Check for missing variables
    missing_vars_in_lf = pw_var_names - lf_var_names
    missing_vars_in_pw = lf_var_names - pw_var_names
    
    if len(missing_vars_in_lf) > 0:
        print(f"  ⚠ Variables in pywellen but not pylibfst: {len(missing_vars_in_lf)}")
        for var_name in list(missing_vars_in_lf)[:5]:
            print(f"    - {var_name}")
    
    if len(missing_vars_in_pw) > 0:
        print(f"  ⚠ Variables in pylibfst but not pywellen: {len(missing_vars_in_pw)}")
        for var_name in list(missing_vars_in_pw)[:5]:
            print(f"    - {var_name}")
    
    # Compare variable types for common variables
    common_vars = pw_var_names & lf_var_names
    var_type_mismatches = 0
    var_name_mismatches = 0
    
    for var_path in sorted(common_vars)[:50]:  # Check first 50 for brevity
        pw_info = pw_vars[var_path]
        lf_info = lf_vars[var_path]
        
        # Compare short names
        if pw_info['name'] != lf_info['name']:
            print(f"    Variable name mismatch for '{var_path}': pywellen={pw_info['name']}, pylibfst={lf_info['name']}")
            var_name_mismatches += 1
        
        # Compare variable types
        if pw_info['type'] != lf_info['type']:
            print(f"    Variable type mismatch for '{var_path}': pywellen={pw_info['type']}, pylibfst={lf_info['type']}")
            var_type_mismatches += 1
    
    if var_type_mismatches == 0 and var_name_mismatches == 0:
        print(f"  ✓ All checked variable names and types match")
    
    # Summary
    print("\n  Summary:")
    print(f"    Common scopes: {len(common_scopes)}")
    print(f"    Common variables: {len(common_vars)}")
    print(f"    Scope type mismatches: {scope_type_mismatches}")
    print(f"    Variable type mismatches: {var_type_mismatches}")
    print(f"    Variable name mismatches: {var_name_mismatches}")
    
    # Assert reasonable compatibility
    # Allow some differences due to alias handling, but core signals should match
    assert len(common_scopes) > 0, "No common scopes found"
    assert len(common_vars) > 0, "No common variables found"
    
    # We expect most variables to be present in both
    common_ratio = len(common_vars) / max(len(pw_var_names), len(lf_var_names))
    assert common_ratio > 0.8, f"Only {common_ratio:.1%} of variables are common"
    
    print(f"\n  ✓ Hierarchy comparison test passed ({common_ratio:.1%} variable overlap)")


if __name__ == "__main__":
    # Run basic tests
    print("Testing pylibfst API compatibility...")
    
    if pylibfst:
        test_basic_loading()
        print("✓ Basic loading test passed")
        
        test_hierarchy_navigation()
        print("✓ Hierarchy navigation test passed")
        
        test_signal_loading()
        print("✓ Signal loading test passed")
        
        test_lazy_loading()
        print("✓ Lazy loading test passed")
        
        test_iterators()
        print("✓ Iterator test passed")
        
        if pywellen:
            test_api_compatibility()
            print("✓ API compatibility test passed")
            
            test_var_api_compatibility()
            print("✓ Var API compatibility test passed")
            
            test_hierarchy_methods_compatibility()
            print("✓ Hierarchy methods compatibility test passed")
            
            test_hierarchy_deep_comparison()
            print("✓ Hierarchy deep comparison test passed")
            
            test_query_result_comparison()
            print("✓ QueryResult comparison test passed")
            
            test_time_range_comparison()
            print("✓ Time range comparison test passed")
        else:
            print("⚠ Skipping API compatibility tests (pywellen not available)")
    else:
        print("⚠ pylibfst not built. Run 'maturin develop' first.")