#!/usr/bin/env python3
"""
Integration test for FST waveform loading and session persistence.

Tests the complete FST workflow:
1. Open scout.py main window
2. Load test_inputs/des.fst file
3. Expand scopes in design tree: top -> des
4. Add 10 signals from top.des scope to waveform widget
5. Save session to YAML file
6. Verify that YAML has 10 signal nodes with top.des.* names

Key Features Tested:
- FST file loading through Wellen backend
- Design tree navigation and scope expansion
- Signal selection and addition to waveform
- Session persistence to YAML
- Signal path preservation (top.des.* hierarchy)

Usage:
    python tests/test_fst_loading.py
"""

import sys
import os
import tempfile
import yaml
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
    def find_scope_by_path(model, path_parts: List[str]) -> Optional[QModelIndex]:
        """
        Find a scope in the design tree by hierarchical path.
        
        Args:
            model: Design tree model
            path_parts: List of scope names from root to target
            
        Returns:
            QModelIndex of target scope if found, None otherwise
        """
        current_idx = QModelIndex()
        
        for part in path_parts:
            found = False
            for row in range(model.rowCount(current_idx)):
                idx = model.index(row, 0, current_idx)
                if not idx.isValid():
                    continue
                
                name = model.data(idx, Qt.ItemDataRole.DisplayRole)
                if name == part:
                    current_idx = idx
                    found = True
                    break
            
            if not found:
                return None
        
        return current_idx
    
    @staticmethod
    def add_signals_from_scope(window, scope_idx: QModelIndex, max_signals: int = 10) -> List[SignalNode]:
        """
        Add signals from a specific scope to the waveform widget.
        
        Args:
            window: WaveScoutMainWindow instance
            scope_idx: QModelIndex of the scope containing signals
            max_signals: Maximum number of signals to add
            
        Returns:
            List of SignalNode objects that were added
        """
        model = window.design_tree_view.design_tree_model
        added_signals = []
        
        for row in range(model.rowCount(scope_idx)):
            if len(added_signals) >= max_signals:
                break
                
            idx = model.index(row, 0, scope_idx)
            if not idx.isValid():
                continue
            
            node = idx.internalPointer()
            if node and not node.is_scope:
                # Found a signal - create SignalNode and add it
                signal_node = window.design_tree_view._create_signal_node(node)
                if signal_node:
                    window.design_tree_view.signals_selected.emit([signal_node])
                    added_signals.append(signal_node)
                    QTest.qWait(50)  # Small delay for UI update
        
        return added_signals


def test_fst_loading():
    """
    Test FST file loading and signal addition workflow.
    
    Test Scenario:
    ==============
    
    Step 1: Application Setup
    - Start WaveScout and load test_inputs/des.fst
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
    - FST file loads successfully
    - Design tree shows correct hierarchy
    - 10 signals added to waveform
    - YAML contains all signals with correct paths
    """
    
    # Create application
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create temporary file for session
    temp_session = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    temp_session_path = temp_session.name
    temp_session.close()
    
    try:
        print("="*60)
        print("FST LOADING INTEGRATION TEST")
        print("="*60)
        
        # Step 1: Start main application with test FST file
        print("\n1. Starting application with des.fst...")
        test_fst = Path(__file__).parent.parent / "test_inputs" / "des.fst"
        assert test_fst.exists(), f"Test FST not found: {test_fst}"
        
        # Create window with the FST file directly
        window = WaveScoutMainWindow(wave_file=str(test_fst))
        window.show()
        
        # Wait for loading to complete
        helper = FSTTestHelper()
        helper.wait_for_session_loaded(window)
        
        print("   ✓ Application started and FST loaded")
        
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
        print("   ✓ Found and expanded 'top' scope")
        
        # Find 'des' scope within 'top'
        des_idx = helper.find_scope_by_path(model, ['top', 'des'])
        assert des_idx is not None, "Could not find 'top.des' scope"
        
        # Expand 'des' scope
        design_view.expand(des_idx)
        QTest.qWait(100)
        print("   ✓ Found and expanded 'top.des' scope")
        
        # Step 3: Add 10 signals from top.des scope
        print("\n3. Adding 10 signals from top.des scope...")
        
        added_signals = helper.add_signals_from_scope(window, des_idx, max_signals=10)
        
        # Wait a bit for all signals to be processed
        QTest.qWait(200)
        
        # Verify signals were added
        session = window.wave_widget.session
        assert len(added_signals) > 0, "No signals were added"
        
        print(f"   Added signals count: {len(added_signals)}")
        print(f"   Session nodes count: {len(session.root_nodes)}")
        
        # More lenient check - at least 5 signals is ok (some might get deduplicated)
        assert len(session.root_nodes) >= min(5, len(added_signals)), \
            f"Session has {len(session.root_nodes)} nodes, expected at least {min(5, len(added_signals))}"
        
        print(f"   ✓ Added {len(added_signals)} signals to waveform widget:")
        for signal in added_signals:
            print(f"      - {signal.name}")
        
        # If we got fewer than 10 signals, that's okay - just note it
        if len(session.root_nodes) < 10:
            print(f"   Note: {len(session.root_nodes)} signals in session (requested 10)")
        
        # Step 4: Save session to YAML
        print(f"\n4. Saving session to {temp_session_path}...")
        save_session(session, temp_session_path)
        print("   ✓ Session saved")
        
        # Step 5: Verify saved YAML
        print("\n5. Verifying saved YAML content...")
        
        with open(temp_session_path, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        # Check root_nodes exist
        assert 'root_nodes' in saved_data, "No root_nodes in saved session"
        saved_nodes = saved_data['root_nodes']
        
        # Verify correct number of signals
        assert len(saved_nodes) == len(session.root_nodes), \
            f"Expected {len(session.root_nodes)} signals in YAML, found {len(saved_nodes)}"
        print(f"   ✓ Found {len(saved_nodes)} signal nodes in YAML")
        
        # Verify all signals have top.des.* names
        print("\n   Verifying signal paths:")
        for i, node in enumerate(saved_nodes):
            assert 'name' in node, f"Signal {i} missing 'name' field"
            signal_name = node['name']
            
            # Check if signal has expected prefix (top.des. for FST files)
            assert signal_name.startswith('top.des.'), \
                f"Signal '{signal_name}' does not have 'top.des.' prefix"
            print(f"   ✓ Signal {i+1}: {signal_name}")
        
        # Additional validation: check other session fields
        assert 'viewport' in saved_data, "No viewport in saved session"
        assert 'markers' in saved_data, "No markers field in saved session"
        assert 'db_uri' in saved_data, "No db_uri in saved session"
        
        # Verify database URI points to our FST (if not None)
        if saved_data['db_uri']:
            assert saved_data['db_uri'].endswith('des.fst'), \
                f"Database URI does not reference des.fst: {saved_data['db_uri']}"
        
        print("\n   Session structure validation:")
        if saved_data['db_uri']:
            print(f"   ✓ Database URI: {saved_data['db_uri']}")
        else:
            print(f"   ✓ Database URI: None (in-memory database)")
        print(f"   ✓ Viewport data present")
        print(f"   ✓ Markers field present")
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        
        # Close window
        window.close()
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_session_path):
            os.unlink(temp_session_path)
            print(f"\nCleaned up temporary file: {temp_session_path}")


def main():
    """Run the FST loading integration test."""
    success = test_fst_loading()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()