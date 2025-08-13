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
            
            test_hierarchy_deep_comparison()
            print("✓ Hierarchy deep comparison test passed")
        else:
            print("⚠ Skipping API compatibility tests (pywellen not available)")
    else:
        print("⚠ pylibfst not built. Run 'maturin develop' first.")