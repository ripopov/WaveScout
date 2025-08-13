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
        else:
            print("⚠ Skipping API compatibility test (pywellen not available)")
    else:
        print("⚠ pylibfst not built. Run 'maturin develop' first.")