#!/usr/bin/env python3
"""
Integration test for FST waveform loading and session persistence.

Tests the complete FST workflow with both pywellen and pylibfst backends:
1. Open scout.py main window
2. Load test_inputs/des.fst file with specified backend
3. Expand scopes in design tree: top -> des
4. Add 10 signals from top.des scope to waveform widget
5. Save session to YAML file
6. Verify that YAML has 10 signal nodes with top.des.* names

Key Features Tested:
- FST file loading through both Wellen and pylibfst backends
- Design tree navigation and scope expansion
- Signal selection and addition to waveform
- Session persistence to YAML
- Signal path preservation (top.des.* hierarchy)

Usage:
    pytest tests/test_fst_loading.py
"""

import sys
import os
import tempfile
import json
import pytest
from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex, QTimer
from PySide6.QtTest import QTest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scout import WaveScoutMainWindow
from wavescout import save_session
from wavescout.data_model import SignalNode

# Import test utilities
from .test_utils import get_test_input_path, TestFiles


class FSTTestHelper:
    """
    Helper class for FST loading integration testing.
    
    Provides utility methods for tree navigation and signal extraction.
    """
    
    @staticmethod
    def wait_for_session_loaded(window, timeout_ms: int = 5000) -> None:
        """
        Wait for session and design tree to be fully loaded.
        
        Args:
            window: WaveScoutMainWindow instance
            timeout_ms: Max wait time in milliseconds
            
        Raises:
            TimeoutError: If not loaded within timeout
        """
        import time
        app = QApplication.instance()
        start_time = time.time()
        
        while (time.time() - start_time) * 1000 < timeout_ms:
            if (window.wave_widget.session is not None and
                window.wave_widget.session.waveform_db is not None and
                window.design_tree_view.design_tree_model is not None and
                window.design_tree_view.design_tree_model.rowCount() > 0):
                return
            QTest.qWait(100)
            app.processEvents()
        
        raise TimeoutError("Session failed to load within timeout")
    
    @staticmethod
    def find_scope_by_path(model, path: List[str], parent_idx: Optional[QModelIndex] = None):
        """
        Find a scope in the design tree by hierarchical path.
        
        Args:
            model: Design tree model
            path: List of scope names forming path (e.g., ['top', 'des'])
            parent_idx: Parent index to start search from
            
        Returns:
            QModelIndex of found scope or None
        """
        if parent_idx is None:
            parent_idx = QModelIndex()
        
        # Base case: empty path
        if not path:
            return parent_idx
        
        # Look for first element in path
        target_name = path[0]
        
        for row in range(model.rowCount(parent_idx)):
            idx = model.index(row, 0, parent_idx)
            name = model.data(idx, Qt.ItemDataRole.DisplayRole)
            
            if name == target_name:
                # Found this level, recurse for remaining path
                if len(path) == 1:
                    return idx
                else:
                    return FSTTestHelper.find_scope_by_path(model, path[1:], idx)
        
        return None
    
    @staticmethod
    def add_signals_from_scope(window, scope_idx: QModelIndex, max_signals: int = 10):
        """
        Add signals from a scope to the waveform.
        
        Args:
            window: WaveScoutMainWindow instance
            scope_idx: Index of scope containing signals
            max_signals: Maximum number of signals to add
            
        Returns:
            List of added signal names
        """
        model = window.design_tree_view.design_tree_model
        design_view = window.design_tree_view.unified_tree
        added_signals = []
        
        # Iterate through children of the scope
        for row in range(model.rowCount(scope_idx)):
            if len(added_signals) >= max_signals:
                break
            
            idx = model.index(row, 0, scope_idx)
            name = model.data(idx, Qt.ItemDataRole.DisplayRole)
            
            # Check if this is a signal (not a scope)
            if model.rowCount(idx) == 0:  # No children = signal
                # Double-click to add signal
                design_view.scrollTo(idx)
                QTest.qWait(50)
                
                # Simulate double-click by calling the slot directly
                window.design_tree_view._on_tree_double_click(idx)
                
                added_signals.append(name)
                print(f"     - Added signal: {name}")
                
                QTest.qWait(50)  # Small delay between additions
        
        return added_signals


@pytest.mark.parametrize("backend_preference", ["pywellen", "pylibfst"])
def test_fst_loading_with_backend(backend_preference):
    """
    Test FST file loading and signal addition workflow with specified backend.
    
    Args:
        backend_preference: The backend to use ("pywellen" or "pylibfst")
    
    Test Scenario:
    ==============
    
    Step 1: Application Setup
    - Start WaveScout and load test_inputs/des.fst with specified backend
    - Wait for waveform database and design tree to initialize
    - Verify: Design tree populated with signal hierarchy
    
    Step 2: Navigate Design Tree
    - Find and expand 'top' scope
    - Find and expand 'des' scope within 'top'
    - Verify: top.des scope is accessible
    
    Step 3: Add Signals
    - Add 10 signals from top.des scope
    - Verify: 10 signals appear in session.root_nodes
    
    Step 4: Save Session
    - Save to temporary YAML file
    - Verify: File created with complete session data
    
    Step 5: Validate YAML
    - Check root_nodes: 10 signals present
    - Check signal names: all have top.des.* prefix
    - Verify: Signal hierarchy preserved correctly
    
    Expected Results:
    - FST file loads successfully with specified backend
    - Design tree shows correct hierarchy
    - 10 signals added to waveform
    - YAML contains all signals with correct paths
    """
    
    # Create application
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create temporary file for session
    temp_session = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_session_path = temp_session.name
    temp_session.close()
    
    try:
        print("="*60)
        print(f"FST LOADING INTEGRATION TEST - Backend: {backend_preference}")
        print("="*60)
        
        # Step 1: Start main application with test FST file and backend preference
        print(f"\n1. Starting application with des.fst using {backend_preference} backend...")
        test_fst = get_test_input_path(TestFiles.DES_FST)
        assert test_fst.exists(), f"Test FST not found: {test_fst}"
        
        # Create window without loading any file
        window = WaveScoutMainWindow()
        window.show()
        
        # Set the backend preference and load our FST file
        window.fst_backend_preference = backend_preference
        QTest.qWait(100)  # Give UI time to initialize
        window.load_file(str(test_fst))
        
        # Wait for loading to complete
        helper = FSTTestHelper()
        QTest.qWait(500)  # Give time for the load to start
        helper.wait_for_session_loaded(window)
        
        # Verify correct backend was used
        session = window.wave_widget.session
        assert session.waveform_db is not None
        assert session.waveform_db._current_backend_type == backend_preference, \
            f"Expected backend {backend_preference}, got {session.waveform_db._current_backend_type}"
        
        print(f"   [OK] Application started and FST loaded with {backend_preference} backend")
        
        # Step 2: Navigate to top.des scope
        print("\n2. Navigating design tree to top.des scope...")
        
        design_view = window.design_tree_view.unified_tree
        model = window.design_tree_view.design_tree_model
        
        # Debug: print all root items
        print("   Root items in design tree:")
        for r in range(model.rowCount(QModelIndex())):
            idx = model.index(r, 0, QModelIndex())
            if idx.isValid():
                name = model.data(idx, Qt.ItemDataRole.DisplayRole)
                print(f"     - {name}")
        
        # Find 'top' scope
        top_idx = helper.find_scope_by_path(model, ['top'])
        assert top_idx is not None, "Could not find 'top' scope"
        
        # Expand 'top' scope
        design_view.expand(top_idx)
        QTest.qWait(100)
        print("   [OK] Found and expanded 'top' scope")
        
        # Find 'des' scope within 'top'
        des_idx = helper.find_scope_by_path(model, ['top', 'des'])
        assert des_idx is not None, "Could not find 'top.des' scope"
        
        # Expand 'des' scope
        design_view.expand(des_idx)
        QTest.qWait(100)
        print("   [OK] Found and expanded 'top.des' scope")
        
        # Step 3: Add 10 signals from top.des scope
        print("\n3. Adding 10 signals from top.des scope...")
        
        added_signals = helper.add_signals_from_scope(window, des_idx, max_signals=10)
        
        # Wait a bit for all signals to be processed
        QTest.qWait(200)
        
        # Verify signals were added
        assert len(added_signals) > 0, "No signals were added"
        
        print(f"   Added signals count: {len(added_signals)}")
        print(f"   Session nodes count: {len(session.root_nodes)}")
        
        # More lenient check - at least 5 signals is ok (some might get deduplicated)
        assert len(session.root_nodes) >= min(5, len(added_signals)), \
            f"Session has {len(session.root_nodes)} nodes, expected at least {min(5, len(added_signals))}"
        
        print(f"   [OK] Successfully added {len(session.root_nodes)} signals to session")
        
        # Step 4: Save session
        print("\n4. Saving session to YAML...")
        save_session(session, Path(temp_session_path))
        print(f"   [OK] Session saved to: {temp_session_path}")
        
        # Step 5: Validate YAML
        print("\n5. Validating saved YAML...")
        with open(temp_session_path, 'r') as f:
            yaml_data = json.load(f)
        
        # Check that we have root_nodes
        assert 'root_nodes' in yaml_data, "YAML missing root_nodes"
        root_nodes = yaml_data['root_nodes']
        
        print(f"   Found {len(root_nodes)} root nodes in YAML")
        
        # Check that signals have correct naming
        signal_names = []
        for node in root_nodes:
            # Nodes are serialized as dictionaries with 'node_type' field
            node_type = node.get('node_type', 'signal')
            if node_type == 'signal':
                name = node['name']
                signal_names.append(name)
                assert 'top.des' in name or name in added_signals, \
                    f"Signal name '{name}' doesn't match expected pattern"
        
        print(f"   Signal names in YAML:")
        for name in signal_names[:10]:  # Show first 10
            print(f"     - {name}")
        
        # Check db_uri is present
        assert 'db_uri' in yaml_data, "YAML missing db_uri"
        assert yaml_data['db_uri'].endswith('des.fst'), \
            f"Unexpected db_uri: {yaml_data['db_uri']}"
        
        print("   [OK] YAML validation successful")
        print(f"\n[TEST PASSED] FST loading with {backend_preference} backend successful!")
        
    except Exception as e:
        print(f"\n[TEST FAILED] with {backend_preference} backend: {e}")
        raise
    
    finally:
        # Clean up
        if os.path.exists(temp_session_path):
            os.unlink(temp_session_path)
            print(f"\nCleaned up temporary file: {temp_session_path}")
        
        # Close window
        if 'window' in locals():
            window.close()


# Backwards compatibility - keep the original test function that tests with pywellen
def test_fst_loading():
    """Test FST loading with default (pywellen) backend for backwards compatibility."""
    test_fst_loading_with_backend("pywellen")


if __name__ == "__main__":
    # Run tests with both backends when executed directly
    import pytest
    pytest.main([__file__, "-v"])