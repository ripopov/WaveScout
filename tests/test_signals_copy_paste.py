"""Test copy-paste functionality for signals in SignalNamesView."""

import pytest
import tempfile
from pathlib import Path
from typing import List
import json

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QMimeData, QModelIndex
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest

from scout import WaveScoutMainWindow
from wavescout.wave_scout_widget import WaveScoutWidget
from wavescout.data_model import SignalNode
from wavescout.signal_names_view import SignalNamesView
from wavescout.persistence import save_session, load_session


@pytest.fixture(autouse=True)
def clear_clipboard():
    """Clear clipboard before and after each test to prevent segfaults."""
    # Clear before test
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.clear()
    
    yield
    
    # Clear after test
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.clear()
        # Process events to ensure clipboard operations complete
        QApplication.processEvents()


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
    session_file = tmp_path / "test_session.json"
    save_session(session, session_file)
    
    assert session_file.exists(), "Session file should be created"
    
    # Step 7: Verify all SignalNodes are as expected
    # Load the JSON and check
    with open(session_file, 'r') as f:
        data = json.load(f)
    
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


def test_copy_paste_nested_groups(qtbot, tmp_path):
    """Test copying and pasting nested groups (groups within groups).
    
    This is a regression test for the recursion bug that occurred when
    copying groups due to circular parent-child references.
    """
    
    # Create main window
    window = WaveScoutMainWindow(wave_file='test_inputs/apb_sim.vcd')
    qtbot.addWidget(window)
    
    # Wait for file to load
    max_wait = 5000
    elapsed = 0
    while elapsed < max_wait:
        QTest.qWait(200)
        elapsed += 200
        if window.wave_widget.session is not None:
            break
    
    assert window.wave_widget.session is not None, "Session should be loaded"
    
    # Add 6 signals
    signals_to_add = get_signals_from_hierarchy(window, 6)
    for signal in signals_to_add:
        window._add_node_to_session(signal)
    
    QTest.qWait(100)
    
    session = window.wave_widget.session
    controller = window.wave_widget.controller
    names_view = window.wave_widget._names_view
    
    # Create first group from signals 0-1
    group1_id = controller.create_group_from_nodes(
        session.root_nodes[:2],
        "Group 1"
    )
    QTest.qWait(100)
    
    # Create second group from signals 2-3 (now at positions 1-2)
    group2_id = controller.create_group_from_nodes(
        session.root_nodes[1:3],
        "Group 2"
    )
    QTest.qWait(100)
    
    # Now create a parent group containing both groups
    parent_group_id = controller.create_group_from_nodes(
        session.root_nodes[:2],  # The two groups
        "Parent Group"
    )
    QTest.qWait(100)
    
    # Should have 3 root nodes: Parent Group + 2 remaining signals
    assert len(session.root_nodes) == 3, f"Should have 3 root nodes, got {len(session.root_nodes)}"
    
    # Verify nested structure
    parent_group = session.root_nodes[0]
    assert parent_group.is_group, "First node should be parent group"
    assert len(parent_group.children) == 2, "Parent group should have 2 child groups"
    assert parent_group.children[0].is_group, "First child should be a group"
    assert parent_group.children[1].is_group, "Second child should be a group"
    assert len(parent_group.children[0].children) == 2, "First child group should have 2 signals"
    assert len(parent_group.children[1].children) == 2, "Second child group should have 2 signals"
    
    # Select and copy the nested parent group
    model = names_view.model()
    selection_model = names_view.selectionModel()
    selection_model.clear()
    
    index = model.index(0, 0, QModelIndex())
    selection_model.select(index, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # This would previously cause RecursionError due to circular references
    names_view._copy_selected_nodes()
    
    # Verify clipboard has data
    clipboard = QApplication.clipboard()
    if clipboard:
        mime_data = clipboard.mimeData()
        assert mime_data.hasFormat(SignalNamesView.SIGNAL_NODE_MIME_TYPE), "Clipboard should have signal data"
    
    # Paste the nested group
    selection_model.clear()
    names_view._paste_nodes()
    QTest.qWait(100)
    
    # Should now have 4 root nodes
    assert len(session.root_nodes) == 4, f"Should have 4 root nodes after paste, got {len(session.root_nodes)}"
    
    # Verify the pasted nested structure
    pasted_group = session.root_nodes[-1]
    assert pasted_group.is_group, "Pasted node should be a group"
    assert len(pasted_group.children) == 2, "Pasted parent should have 2 child groups"
    assert pasted_group.children[0].is_group, "Pasted first child should be a group"
    assert pasted_group.children[1].is_group, "Pasted second child should be a group"
    assert len(pasted_group.children[0].children) == 2, "Pasted first child group should have 2 signals"
    assert len(pasted_group.children[1].children) == 2, "Pasted second child group should have 2 signals"
    
    # Verify all instance IDs are unique
    all_ids = set()
    
    def collect_ids(node):
        all_ids.add(node.instance_id)
        for child in node.children:
            collect_ids(child)
    
    for node in session.root_nodes:
        collect_ids(node)
    
    # Count total nodes: 2 remaining signals + 2*(1 parent + 2 groups + 4 signals) = 2 + 2*7 = 16
    assert len(all_ids) == 16, f"Should have 16 unique IDs, got {len(all_ids)}"
    
    # Verify parent references are correct
    def verify_parent_refs(node, expected_parent=None):
        assert node.parent == expected_parent, f"Node {node.name} parent reference incorrect"
        for child in node.children:
            verify_parent_refs(child, node)
    
    for root_node in session.root_nodes:
        verify_parent_refs(root_node, None)
    
    print("✅ Nested groups copy-paste test passed!")
    print("  • Created nested group structure (groups within groups)")
    print("  • Successfully copied without RecursionError")
    print("  • Pasted correctly with all structure preserved")
    print("  • All instance IDs are unique")
    print("  • Parent references are correct")


def test_copy_paste_mixed_selection(qtbot, tmp_path):
    """Test copying and pasting a mixed selection of signals and groups."""
    
    # Create main window
    window = WaveScoutMainWindow(wave_file='test_inputs/apb_sim.vcd')
    qtbot.addWidget(window)
    
    # Wait for file to load
    max_wait = 5000
    elapsed = 0
    while elapsed < max_wait:
        QTest.qWait(200)
        elapsed += 200
        if window.wave_widget.session is not None:
            break
    
    assert window.wave_widget.session is not None, "Session should be loaded"
    
    # Add 5 signals
    signals_to_add = get_signals_from_hierarchy(window, 5)
    for signal in signals_to_add:
        window._add_node_to_session(signal)
    
    QTest.qWait(100)
    
    session = window.wave_widget.session
    controller = window.wave_widget.controller
    names_view = window.wave_widget._names_view
    
    # Create a group from signals 1-2
    group_id = controller.create_group_from_nodes(
        session.root_nodes[1:3],
        "Mixed Group"
    )
    QTest.qWait(100)
    
    # Now we have: signal0, group(signal1, signal2), signal3, signal4
    assert len(session.root_nodes) == 4, f"Should have 4 root nodes, got {len(session.root_nodes)}"
    
    # Select mixed: first signal + the group + last signal
    model = names_view.model()
    selection_model = names_view.selectionModel()
    selection_model.clear()
    
    # Select signal at index 0
    index0 = model.index(0, 0, QModelIndex())
    selection_model.select(index0, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Select group at index 1
    index1 = model.index(1, 0, QModelIndex())
    selection_model.select(index1, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Select signal at index 3
    index3 = model.index(3, 0, QModelIndex())
    selection_model.select(index3, selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows)
    
    # Verify selection
    selected_nodes = names_view._get_all_selected_nodes()
    assert len(selected_nodes) == 3, f"Should have 3 selected nodes, got {len(selected_nodes)}"
    
    # Copy the mixed selection
    names_view._copy_selected_nodes()
    
    # Paste at end
    selection_model.clear()
    names_view._paste_nodes()
    QTest.qWait(100)
    
    # Should now have 7 root nodes (4 original + 3 pasted)
    assert len(session.root_nodes) == 7, f"Should have 7 root nodes after paste, got {len(session.root_nodes)}"
    
    # Verify the pasted nodes
    # Last 3 should be: signal (copy of first), group (copy), signal (copy of last)
    assert not session.root_nodes[-3].is_group, "First pasted should be a signal"
    assert session.root_nodes[-2].is_group, "Second pasted should be a group"
    assert not session.root_nodes[-1].is_group, "Third pasted should be a signal"
    
    # Verify the pasted group has children
    pasted_group = session.root_nodes[-2]
    assert len(pasted_group.children) == 2, f"Pasted group should have 2 children, got {len(pasted_group.children)}"
    
    print("✅ Mixed selection copy-paste test passed!")
    print("  • Selected mix of signals and groups")
    print("  • Successfully copied mixed selection")
    print("  • Pasted correctly with structure preserved")


def test_copy_paste_recursion_regression(qtbot):
    """Regression test to ensure the recursion bug doesn't return.
    
    This test specifically creates the conditions that caused the original bug:
    - Deep nesting of groups
    - Circular parent-child references
    - Equality comparisons that would trigger infinite recursion
    """
    
    from wavescout.data_model import SignalNode, DisplayFormat, RenderType
    from wavescout.persistence import _serialize_node, _deserialize_node
    import json
    
    # Create a deeply nested structure
    root = SignalNode(name="ROOT", is_group=True)
    
    # Level 1
    level1 = SignalNode(name="L1", is_group=True)
    level1.parent = root
    root.children.append(level1)
    
    # Level 2
    level2 = SignalNode(name="L2", is_group=True)
    level2.parent = level1
    level1.children.append(level2)
    
    # Level 3
    level3 = SignalNode(name="L3", is_group=True)
    level3.parent = level2
    level2.children.append(level3)
    
    # Add signals at each level
    for i, parent in enumerate([root, level1, level2, level3]):
        signal = SignalNode(
            name=f"{parent.name}_signal",
            handle=i,
            format=DisplayFormat(render_type=RenderType.BOOL)
        )
        signal.parent = parent
        parent.children.append(signal)
    
    # Test 1: Equality comparison (would previously cause RecursionError)
    try:
        result = (root == root)
        assert result == True, "Self-equality should be True"
        
        # Compare different nodes
        result2 = (level1 == level2)
        assert result2 == False, "Different nodes should not be equal"
        
        # Compare with deep copy
        copied = root.deep_copy()
        result3 = (root == copied)
        assert result3 == False, "Original and copy should have different instance_ids"
        
    except RecursionError:
        pytest.fail("RecursionError occurred in equality comparison - regression detected!")
    
    # Test 2: Serialization (would fail with recursion)
    try:
        serialized = _serialize_node(root)
        json_str = json.dumps(serialized, indent=2)
        assert len(json_str) > 0, "Serialization should produce output"
    except RecursionError:
        pytest.fail("RecursionError occurred in serialization - regression detected!")
    
    # Test 3: Deserialization
    try:
        deserialized_data = json.loads(json_str)
        deserialized = _deserialize_node(deserialized_data)
        assert deserialized.name == "ROOT", "Deserialized root should have correct name"
        
        # Verify structure
        assert len(deserialized.children) == 2, "Root should have 2 children (L1 + signal)"
        assert deserialized.children[0].name == "L1", "First child should be L1"
        assert len(deserialized.children[0].children) == 2, "L1 should have 2 children"
        
    except RecursionError:
        pytest.fail("RecursionError occurred in deserialization - regression detected!")
    
    # Test 4: Deep copy with circular references
    try:
        deep_copied = deserialized.deep_copy()
        
        # Verify parent references are set correctly
        assert deep_copied.parent is None, "Root parent should be None"
        assert deep_copied.children[0].parent == deep_copied, "L1 parent should be root"
        
        # Verify instance IDs are different
        assert deep_copied.instance_id != deserialized.instance_id, "Instance IDs should differ"
        
    except RecursionError:
        pytest.fail("RecursionError occurred in deep_copy - regression detected!")
    
    print("✅ Recursion regression test passed!")
    print("  • Deep nested structures work correctly")
    print("  • Equality comparisons don't cause recursion")
    print("  • Serialization/deserialization works")
    print("  • Deep copy maintains correct parent references")
    print("  • No infinite recursion detected")


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
        print("Running comprehensive copy-paste regression tests...\n")
        print("=" * 60)
        
        test_copy_paste_signals(qtbot, tmp_dir)
        print("=" * 60)
        
        test_copy_paste_with_groups(qtbot, tmp_dir)
        print("=" * 60)
        
        test_copy_paste_nested_groups(qtbot, tmp_dir)
        print("=" * 60)
        
        test_copy_paste_mixed_selection(qtbot, tmp_dir)
        print("=" * 60)
        
        test_copy_paste_recursion_regression(qtbot)
        print("=" * 60)
        
        print("\n✅ All comprehensive regression tests passed successfully!")
        print("\nSummary of tests:")
        print("  1. Basic signal copy-paste")
        print("  2. Group copy-paste")
        print("  3. Nested groups (groups within groups)")
        print("  4. Mixed selection (signals + groups)")
        print("  5. Recursion regression (deep nesting)")
        
    finally:
        # Clean up temp directory
        import shutil
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        
        # Process remaining events before quitting
        QTest.qWait(100)
        app.processEvents()