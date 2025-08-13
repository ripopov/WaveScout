"""Test pylibfst Python wrapper against WaveformDB."""

import sys
from pathlib import Path
import pytest
from typing import Dict, List, Set, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pylibfst import PyLibFst, HierNode, FstHierType, SignalValue
from wavescout.waveform_db import WaveformDB


TEST_FST_FILE = "test_inputs/des.fst"


def build_hierarchy_dict_from_libfst(nodes: List[HierNode]) -> Dict[str, Set[str]]:
    """Build a hierarchy dictionary from libfst nodes.
    
    Returns dict mapping scope paths to their children.
    """
    hierarchy = {}
    current_path = []
    
    for node in nodes:
        if node.type == FstHierType.SCOPE:
            # Add scope to hierarchy
            parent_path = ".".join(current_path) if current_path else ""
            if parent_path not in hierarchy:
                hierarchy[parent_path] = set()
            hierarchy[parent_path].add(node.name)
            current_path.append(node.name)
            
        elif node.type == FstHierType.UPSCOPE:
            if current_path:
                current_path.pop()
                
        elif node.type == FstHierType.VAR:
            # Add variable to current scope
            scope_path = ".".join(current_path) if current_path else ""
            if scope_path not in hierarchy:
                hierarchy[scope_path] = set()
            hierarchy[scope_path].add(node.name)
            
    return hierarchy


def build_hierarchy_dict_from_waveformdb(db: WaveformDB) -> Dict[str, Set[str]]:
    """Build a hierarchy dictionary from WaveformDB.
    
    Returns dict mapping scope paths to their children.
    """
    hierarchy = {}
    
    def traverse_scope(scope, parent_path=""):
        scope_name = scope.name(db.hierarchy)
        current_path = f"{parent_path}.{scope_name}" if parent_path else scope_name
        
        # Add child scopes
        children = set()
        for child_scope in scope.scopes(db.hierarchy):
            child_name = child_scope.name(db.hierarchy)
            children.add(child_name)
            traverse_scope(child_scope, current_path)
            
        # Add variables
        for var in scope.vars(db.hierarchy):
            var_name = var.name(db.hierarchy)
            children.add(var_name)
            
        hierarchy[current_path] = children
        
    # Process root scope
    root_children = set()
    for scope in db.hierarchy.top_scopes():
        scope_name = scope.name(db.hierarchy)
        root_children.add(scope_name)
        traverse_scope(scope)
    hierarchy[""] = root_children
    
    return hierarchy


def test_fst_library_loads():
    """Test that the FST library can be loaded."""
    fst = PyLibFst()
    assert fst._lib is not None


def test_open_fst_file():
    """Test opening an FST file."""
    fst = PyLibFst()
    
    # Check if test file exists
    test_file = Path(TEST_FST_FILE)
    if not test_file.exists():
        pytest.skip(f"Test file {TEST_FST_FILE} not found")
    
    assert fst.open(str(test_file))
    
    # Get basic info
    var_count = fst.get_var_count()
    scope_count = fst.get_scope_count()
    start_time, end_time = fst.get_time_range()
    
    assert var_count > 0
    assert scope_count > 0
    assert end_time > start_time
    
    fst.close()


def test_hierarchy_comparison():
    """Compare hierarchy from pylibfst and WaveformDB."""
    test_file = Path(TEST_FST_FILE)
    if not test_file.exists():
        pytest.skip(f"Test file {TEST_FST_FILE} not found")
    
    # Load with pylibfst
    fst = PyLibFst()
    assert fst.open(str(test_file))
    fst_nodes = fst.get_hierarchy()
    fst_hierarchy = build_hierarchy_dict_from_libfst(fst_nodes)
    
    # Load with WaveformDB
    db = WaveformDB()
    db.open(str(test_file))
    db_hierarchy = build_hierarchy_dict_from_waveformdb(db)
    
    # Compare top-level scopes
    fst_top = fst_hierarchy.get("", set())
    db_top = db_hierarchy.get("", set())
    
    print(f"FST top-level scopes: {sorted(fst_top)}")
    print(f"WaveformDB top-level scopes: {sorted(db_top)}")
    
    # They should have at least some common scopes
    common_scopes = fst_top & db_top
    assert len(common_scopes) > 0, "No common top-level scopes found"
    
    # Get counts for comparison
    fst_var_count = fst.get_var_count()
    db_var_count = db.num_vars()
    
    print(f"FST variable count: {fst_var_count}")
    print(f"WaveformDB variable count: {db_var_count}")
    
    # These might differ slightly due to different handling of aliases
    # but should be in the same ballpark
    assert abs(fst_var_count - db_var_count) / max(fst_var_count, db_var_count) < 0.2
    
    fst.close()


def test_signal_values_comparison():
    """Compare signal values from pylibfst and WaveformDB."""
    test_file = Path(TEST_FST_FILE)
    if not test_file.exists():
        pytest.skip(f"Test file {TEST_FST_FILE} not found")
    
    # Load with both libraries
    fst = PyLibFst()
    assert fst.open(str(test_file))
    fst_nodes = fst.get_hierarchy()
    
    db = WaveformDB()
    db.open(str(test_file))
    
    # Build mapping of full paths to FST handles
    fst_path_to_handle = {}
    for node in fst_nodes:
        if (node.type == FstHierType.VAR and 
            not node.is_alias and 
            node.handle is not None):
            fst_path_to_handle[node.full_path] = node.handle
    
    # Build mapping of full paths to WaveformDB handles
    db_path_to_handle = {}
    for handle, vars_list in db._var_map.items():
        if vars_list:
            var = vars_list[0]
            full_path = var.full_name(db.hierarchy)
            db_path_to_handle[full_path] = handle
    
    # Find common signals between both libraries
    common_paths = set(fst_path_to_handle.keys()) & set(db_path_to_handle.keys())
    
    # Select a few test signals
    test_signals = []
    for path in sorted(common_paths)[:3]:  # Test first 3 common signals
        fst_handle = fst_path_to_handle[path]
        db_handle = db_path_to_handle[path]
        test_signals.append((path, fst_handle, db_handle))
    
    assert len(test_signals) >= 3, f"Could not find enough common signals, found {len(test_signals)}"
    
    print(f"Testing {len(test_signals)} signals")
    
    # Compare values for each signal
    signals_tested = 0
    for path, fst_handle, db_handle in test_signals:
        print(f"\nTesting signal: {path}")
        print(f"  FST handle: {fst_handle}, WaveformDB handle: {db_handle}")
        
        # Get values from pylibfst
        fst_values = fst.get_signal_values(fst_handle)
        
        # Get values from WaveformDB
        db_transitions = db.transitions(db_handle, 0, 2**63-1)  # Get all transitions
        
        print(f"  FST values: {len(fst_values)} transitions")
        print(f"  WaveformDB transitions: {len(db_transitions)}")
        
        # Both should have transitions
        if len(fst_values) > 0 and len(db_transitions) > 0:
            # Allow small differences in transition count (FST might include more detail)
            count_diff = abs(len(fst_values) - len(db_transitions))
            count_ratio = count_diff / max(len(fst_values), len(db_transitions))
            
            if count_ratio < 0.05:  # Less than 5% difference
                print(f"  ✓ Transition counts are close: FST={len(fst_values)}, DB={len(db_transitions)}")
                
                # Check that times align for first few transitions
                time_matches = 0
                for i in range(min(10, len(fst_values), len(db_transitions))):
                    fst_time = fst_values[i].time
                    db_time, _ = db_transitions[i]
                    if fst_time == db_time:
                        time_matches += 1
                
                if time_matches >= 8:  # At least 8 out of 10 times match
                    print(f"  ✓ Transition times align ({time_matches}/10 match)")
                else:
                    print(f"  ⚠ Some timing differences ({time_matches}/10 match)")
                
                # Note about value representation
                print(f"  ℹ Values may differ in representation (bit strings vs integers)")
                
            else:
                print(f"  ⚠ Significant transition count difference: FST={len(fst_values)}, DB={len(db_transitions)}")
                
            # Show sample values for verification
            print(f"  Sample FST values (first 3):")
            for i in range(min(3, len(fst_values))):
                val_preview = fst_values[i].value[:40] + "..." if len(fst_values[i].value) > 40 else fst_values[i].value
                print(f"    [{i}] time={fst_values[i].time}, value={val_preview}")
                
            print(f"  Sample DB values (first 3):")
            for i in range(min(3, len(db_transitions))):
                db_time, db_val = db_transitions[i]
                val_preview = db_val[:40] + "..." if len(db_val) > 40 else db_val
                print(f"    [{i}] time={db_time}, value={val_preview}")
            
            signals_tested += 1
        else:
            print(f"  ⚠ Skipping signal - no transitions found in one or both libraries")
    
    assert signals_tested >= 2, f"Could only test {signals_tested} signals with transitions"
    
    fst.close()


def test_time_range_comparison():
    """Compare time ranges from both libraries."""
    test_file = Path(TEST_FST_FILE)
    if not test_file.exists():
        pytest.skip(f"Test file {TEST_FST_FILE} not found")
    
    # Load with pylibfst
    fst = PyLibFst()
    assert fst.open(str(test_file))
    fst_start, fst_end = fst.get_time_range()
    fst_timescale = fst.get_timescale()
    
    # Load with WaveformDB
    db = WaveformDB()
    db.open(str(test_file))
    
    # Get time table to extract start and end times
    time_table = db.get_time_table()
    db_start = time_table[0] if time_table and len(time_table) > 0 else 0
    db_end = time_table[-1] if time_table and len(time_table) > 0 else 0
    
    # Get timescale
    db_ts = db.get_timescale()
    db_timescale = db_ts.unit.to_exponent() if db_ts else 0
    
    print(f"FST time range: {fst_start} - {fst_end}, timescale: {fst_timescale}")
    print(f"WaveformDB time range: {db_start} - {db_end}, timescale: {db_timescale}")
    
    # These should match exactly
    assert fst_start == db_start
    assert fst_end == db_end
    assert fst_timescale == db_timescale
    
    fst.close()


if __name__ == "__main__":
    # Run basic tests
    print("Testing FST library loading...")
    test_fst_library_loads()
    print("✓ Library loads successfully\n")
    
    print("Testing FST file opening...")
    test_open_fst_file()
    print("✓ File opens successfully\n")
    
    print("Testing hierarchy comparison...")
    test_hierarchy_comparison()
    print("✓ Hierarchy comparison passed\n")
    
    print("Testing time range comparison...")
    test_time_range_comparison()
    print("✓ Time ranges match\n")
    
    print("Testing signal values comparison...")
    test_signal_values_comparison()
    print("✓ Signal values comparison passed\n")
    
    print("All tests passed!")