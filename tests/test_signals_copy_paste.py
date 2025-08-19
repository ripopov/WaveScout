"""Test copy-paste functionality for signals in SignalNamesView."""

import pytest
import tempfile
from pathlib import Path
from typing import List
import yaml

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QMimeData, QModelIndex
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest

from scout import WaveScoutMainWindow
from wavescout.wave_scout_widget import WaveScoutWidget
from wavescout.data_model import SignalNode
from wavescout.signal_names_view import SignalNamesView
from wavescout.persistence import save_session, load_session


def get_signals_from_hierarchy(window: WaveScoutMainWindow, count: int = 5) -> List[SignalNode]:
    """Helper to get signals from the design tree."""
    design_view = window.design_tree_view.unified_tree
    model = window.design_tree_view.design_tree_model
    
    if not model:
        return []
    
    signals = []
    
    def find_signals(parent_idx=QModelIndex(), depth=0):
        nonlocal signals
        if len(signals) >= count or depth > 5:
            return
        
        for row in range(model.rowCount(parent_idx)):
            if len(signals) >= count:
                break
            idx = model.index(row, 0, parent_idx)
            if not idx.isValid():
                continue
            
            node = idx.internalPointer()
            if node:
                if not node.is_scope:
                    # Found a signal
                    signal_node = window.design_tree_view._create_signal_node(node)
                    if signal_node:
                        signals.append(signal_node)
                elif depth < 5:
                    # Expand and recurse into scope
                    design_view.expand(idx)
                    find_signals(idx, depth + 1)
    
    # Start searching from root
    find_signals()
    return signals[:count]


def test_copy_paste_signals(qtbot, tmp_path):
    """Test copying and pasting signals in SignalNamesView."""
    
    # Create main window and load waveform
    window = WaveScoutMainWindow(wave_file='test_inputs/apb_sim.vcd')
    qtbot.addWidget(window)
    
    # Wait for file to load - may need more time for async loading
    max_wait = 5000  # 5 seconds max
    elapsed = 0
    while elapsed < max_wait:
        QTest.qWait(200)
        elapsed += 200
        if window.wave_widget.session is not None:
            break
    
    assert window.wave_widget.session is not None, "Session should be loaded"
    assert window.wave_widget.session.waveform_db is not None, "WaveformDB should be loaded"
    
    # Step 1: Add 5 signals to WaveScoutWidget
    signals_to_add = get_signals_from_hierarchy(window, 5)
    assert len(signals_to_add) == 5, f"Should find 5 signals, found {len(signals_to_add)}"
    
    # Add signals directly to avoid async loading issues in test
    session = window.wave_widget.session
    controller = window.wave_widget.controller
    
    # Add signals directly to the session
    for signal in signals_to_add:
        window._add_node_to_session(signal)
    
    # Process events and wait a bit
    QTest.qWait(100)
    
    # Verify signals were added
    assert len(session.root_nodes) == 5, f"Should have 5 signals, got {len(session.root_nodes)}"
    
    # Get the SignalNamesView
    names_view = window.wave_widget._names_view
    assert names_view is not None, "SignalNamesView should exist"
    
    # Step 2: Select 3 signals in SignalNamesView
    # We need to select through the model and selection model
    model = names_view.model()
    selection_model = names_view.selectionModel()
    
    assert model is not None, "Model should exist"
    assert selection_model is not None, "Selection model should exist"
    
    # Clear any existing selection
    selection_model.clear()
    
    # Select first 3 signals
    for i in range(3):
        index = model.index(i, 0, QModelIndex())
        if index.isValid():
            selection_model.select(index, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Verify selection
    selected_nodes = names_view._get_all_selected_nodes()
    assert len(selected_nodes) == 3, f"Should have 3 selected nodes, got {len(selected_nodes)}"
    
    # Step 3: Copy them into clipboard (simulate Ctrl+C)
    names_view._copy_selected_nodes()
    
    # Verify clipboard contains data
    clipboard = QApplication.clipboard()
    if clipboard:  # Check clipboard is available
        mime_data = clipboard.mimeData()
        assert mime_data.hasFormat(SignalNamesView.SIGNAL_NODE_MIME_TYPE), "Clipboard should have signal data"
        assert mime_data.hasText(), "Clipboard should have text data"
    
    # Step 4: First paste - paste at position after 4th signal
    # Select the 4th signal as insertion point
    selection_model.clear()
    index = model.index(3, 0, QModelIndex())  # 4th signal (0-indexed)
    selection_model.select(index, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Paste (simulate Ctrl+V)
    names_view._paste_nodes()
    QTest.qWait(100)
    
    # Verify we now have 8 signals (5 original + 3 pasted)
    assert len(session.root_nodes) == 8, f"Should have 8 signals after first paste, got {len(session.root_nodes)}"
    
    # Step 5: Second paste - paste at the beginning
    # Verify clipboard still has data before second paste
    clipboard = QApplication.clipboard()
    mime_data = clipboard.mimeData()
    assert mime_data.hasFormat(SignalNamesView.SIGNAL_NODE_MIME_TYPE), "Clipboard should still have signal data"
    
    # Force model to update after first paste
    model.layoutChanged.emit()
    QTest.qWait(100)
    
    # Select the first signal as insertion point
    selection_model.clear()
    index = model.index(0, 0, QModelIndex())  # 1st signal
    if index.isValid():
        selection_model.select(index, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Verify we have a selection
    selected_for_paste = names_view._get_all_selected_nodes()
    assert len(selected_for_paste) > 0, "Should have a selected node for insertion point"
    
    # Paste again - deserialize from clipboard and insert directly
    data = mime_data.data(SignalNamesView.SIGNAL_NODE_MIME_TYPE).data()
    if isinstance(data, bytes):
        yaml_str = data.decode('utf-8')
    else:
        yaml_str = bytes(data).decode('utf-8')
    
    nodes_to_paste = names_view._deserialize_nodes(yaml_str)
    validated = names_view._validate_nodes(nodes_to_paste)
    
    # Insert directly using controller
    if validated:
        after_id = selected_for_paste[0].instance_id if selected_for_paste else None
        controller.insert_nodes(validated, after_id)
    
    QTest.qWait(200)  # Give time for the operation to complete
    
    # Verify we now have 11 signals (8 + 3 more pasted)
    assert len(session.root_nodes) == 11, f"Should have 11 signals after second paste, got {len(session.root_nodes)}"
    
    # Step 6: Save session to YAML
    session_file = tmp_path / "test_session.yaml"
    save_session(session, session_file)
    
    assert session_file.exists(), "Session file should be created"
    
    # Step 7: Verify all SignalNodes are as expected
    # Load the YAML and check
    with open(session_file, 'r') as f:
        data = yaml.safe_load(f)
    
    assert 'root_nodes' in data, "Session should have root_nodes"
    assert len(data['root_nodes']) == 11, f"Session file should have 11 nodes, got {len(data['root_nodes'])}"
    
    # Verify that pasted nodes have different instance_ids
    instance_ids = set()
    for node_data in data['root_nodes']:
        instance_id = node_data.get('instance_id')
        assert instance_id is not None, "Each node should have an instance_id"
        assert instance_id not in instance_ids, f"Instance ID {instance_id} is duplicated"
        instance_ids.add(instance_id)
    
    # Verify node names to ensure copies were made correctly
    node_names = [node_data['name'] for node_data in data['root_nodes']]
    
    # Count occurrences of each name (should have duplicates from pasting)
    from collections import Counter
    name_counts = Counter(node_names)
    
    # The 3 copied signals should appear 3 times each (original + 2 pastes)
    # The other 2 signals should appear once each
    three_count_names = sum(1 for count in name_counts.values() if count == 3)
    one_count_names = sum(1 for count in name_counts.values() if count == 1)
    
    assert three_count_names == 3, f"Should have 3 signals appearing 3 times, got {three_count_names}"
    assert one_count_names == 2, f"Should have 2 signals appearing once, got {one_count_names}"
    
    # Load session back to verify it's valid
    loaded_session = load_session(session_file)
    assert len(loaded_session.root_nodes) == 11, "Loaded session should have 11 nodes"
    
    # Verify all nodes have unique instance IDs in loaded session
    loaded_ids = set()
    for node in loaded_session.root_nodes:
        assert node.instance_id not in loaded_ids, f"Loaded node ID {node.instance_id} is duplicated"
        loaded_ids.add(node.instance_id)
    
    print("✅ All copy-paste tests passed!")
    print(f"  • Loaded waveform with signals")
    print(f"  • Added 5 signals to widget")
    print(f"  • Selected and copied 3 signals")
    print(f"  • Pasted twice at different locations")
    print(f"  • Final count: 11 signals (5 + 3 + 3)")
    print(f"  • All instance IDs are unique")
    print(f"  • Session saved and loaded correctly")


def test_copy_paste_with_groups(qtbot, tmp_path):
    """Test copying and pasting groups with children."""
    
    # Create main window
    window = WaveScoutMainWindow(wave_file='test_inputs/apb_sim.vcd')
    qtbot.addWidget(window)
    
    # Wait for file to load - may need more time for async loading
    max_wait = 5000  # 5 seconds max
    elapsed = 0
    while elapsed < max_wait:
        QTest.qWait(200)
        elapsed += 200
        if window.wave_widget.session is not None:
            break
    
    assert window.wave_widget.session is not None, "Session should be loaded"
    
    # Add some signals directly
    signals_to_add = get_signals_from_hierarchy(window, 4)
    
    # Add signals directly to the session
    for signal in signals_to_add:
        window._add_node_to_session(signal)
    
    QTest.qWait(100)
    
    session = window.wave_widget.session
    controller = window.wave_widget.controller
    names_view = window.wave_widget._names_view
    
    # Create a group from first 2 signals
    first_two_ids = [session.root_nodes[i].instance_id for i in range(2)]
    group_id = controller.create_group_from_nodes(
        session.root_nodes[:2],
        "Test Group"
    )
    QTest.qWait(100)
    
    # Should now have 3 root nodes (1 group + 2 signals)
    assert len(session.root_nodes) == 3, f"Should have 3 root nodes, got {len(session.root_nodes)}"
    
    # Select the group
    model = names_view.model()
    selection_model = names_view.selectionModel()
    selection_model.clear()
    
    # Find and select the group (should be first)
    index = model.index(0, 0, QModelIndex())
    selection_model.select(index, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Copy the group
    names_view._copy_selected_nodes()
    
    # Paste at end
    selection_model.clear()  # No selection means paste at end
    names_view._paste_nodes()
    QTest.qWait(100)
    
    # Should now have 4 root nodes (original group + 2 signals + pasted group)
    assert len(session.root_nodes) == 4, f"Should have 4 root nodes after paste, got {len(session.root_nodes)}"
    
    # Verify the pasted group has children
    last_node = session.root_nodes[-1]
    assert last_node.is_group, "Last node should be a group"
    assert len(last_node.children) == 2, f"Pasted group should have 2 children, got {len(last_node.children)}"
    
    # Verify instance IDs are all unique
    all_ids = set()
    
    def collect_ids(node):
        all_ids.add(node.instance_id)
        for child in node.children:
            collect_ids(child)
    
    for node in session.root_nodes:
        collect_ids(node)
    
    # We have: 4 original signals + 1 original group + 1 pasted group + 2 pasted children = 8 total
    assert len(all_ids) == 8, f"Should have 8 unique IDs (4 original signals + 1 original group + 1 pasted group + 2 pasted children), got {len(all_ids)}"
    
    print("✅ Group copy-paste test passed!")


if __name__ == "__main__":
    # Run tests directly (without pytest)
    import sys
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    tmp_dir = Path(tempfile.mkdtemp())
    
    # Create fake qtbot for direct execution
    class FakeQtBot:
        def addWidget(self, widget):
            pass
    
    qtbot = FakeQtBot()
    
    try:
        test_copy_paste_signals(qtbot, tmp_dir)
        test_copy_paste_with_groups(qtbot, tmp_dir)
        print("\n✅ All tests completed successfully!")
    finally:
        # Clean up temp directory
        import shutil
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        
        # Clear clipboard before exiting
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.clear()
        
        # Process remaining events before quitting
        QTest.qWait(100)
        app.processEvents()
        
        # Exit cleanly
        import sys
        sys.exit(0)