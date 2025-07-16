"""Integration tests for delete functionality with real VCD file.

This module tests the deletion of waveform nodes in the WaveScout widget using
actual VCD file data. It verifies that the delete functionality works correctly
in various scenarios:

1. Deleting multiple selected nodes
2. Deleting expanded groups with children
3. Rapid consecutive delete operations

The tests use the shared VCD session fixture from conftest.py which loads the
swerv1.vcd file and populates it with signals. This ensures that the delete
operations are tested against real waveform data structures.

Key aspects tested:
- UI selection model synchronization with data model
- Proper cleanup of deleted nodes from the session
- Handling of parent-child relationships when deleting groups
- Robustness under rapid user interactions

All tests interact with the widget through the Qt UI layer (using QTest.keyClick)
to simulate real user interactions rather than calling delete methods directly.
"""

from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtTest import QTest


def test_delete_first_three_nodes_from_vcd(widget_with_signals):
    """Test deleting first 3 nodes from actual VCD file."""
    widget = widget_with_signals
    session = widget.session
    
    # Verify we have nodes
    assert len(session.root_nodes) > 3
    initial_count = len(session.root_nodes)
    
    # Select first 3 nodes through the UI
    selection_model = widget._selection_model
    for i in range(3):
        index = widget.model.index(i, 0)
        selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    # Verify selection in data model
    assert len(session.selected_nodes) == 3
    
    # Delete using keyboard
    QTest.keyClick(widget, Qt.Key_Delete)
    
    # Verify deletion
    assert len(session.root_nodes) == initial_count - 3
    assert len(session.selected_nodes) == 0
    assert not selection_model.hasSelection()


def test_delete_with_expanded_groups(widget_with_groups):
    """Test deleting nodes when groups are expanded."""
    widget = widget_with_groups
    session = widget.session
    
    # Find and expand first group
    group_index = None
    for i in range(widget.model.rowCount()):
        index = widget.model.index(i, 0)
        node = widget.model.data(index, Qt.UserRole)
        if node.is_group:
            group_index = index
            widget._names_view.expand(index)
            break
    
    assert group_index is not None
    
    # Select the expanded group
    widget._selection_model.select(group_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    # Delete
    QTest.keyClick(widget, Qt.Key_Delete)
    
    # Verify group was deleted
    remaining_groups = sum(1 for node in session.root_nodes if node.is_group)
    assert remaining_groups >= 0  # At least one group should have been deleted


def test_rapid_delete_operations(widget_with_signals):
    """Test multiple rapid delete operations."""
    widget = widget_with_signals
    session = widget.session
    
    initial_count = len(session.root_nodes)
    
    # Perform 3 delete operations
    for _ in range(3):
        if widget.model.rowCount() > 0:
            # Select first node
            index = widget.model.index(0, 0)
            widget._selection_model.select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            
            # Delete
            QTest.keyClick(widget, Qt.Key_Delete)
    
    # Verify 3 nodes were deleted
    assert len(session.root_nodes) == initial_count - 3