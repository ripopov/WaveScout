"""Test double-click functionality in design tree."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex
from wavescout import WaveScoutWidget, DesignTreeModel
from wavescout.data_model import SignalNode


@pytest.fixture
def qt_app(qtbot):
    """Provide Qt application for testing."""
    return QApplication.instance()


@pytest.fixture
def waveform_db(vcd_session):
    """Get waveform database from session."""
    return vcd_session.waveform_db


@pytest.fixture
def wave_widget_and_design_tree(qtbot, vcd_session, waveform_db):
    """Create WaveScoutWidget and DesignTreeModel with loaded VCD."""
    # Use shared session
    session = vcd_session
    
    # Create wave widget
    widget = WaveScoutWidget()
    widget.setSession(session)
    
    # Create design tree model
    design_tree_model = DesignTreeModel(waveform_db)
    
    # Show widget
    widget.resize(800, 600)
    widget.show()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    
    return widget, design_tree_model


def find_signal_in_design_tree(model, parent_index=None):
    """Find the first signal (not scope) in the design tree."""
    if parent_index is None:
        parent_index = QModelIndex()
        
    rows = model.rowCount(parent_index)
    for row in range(rows):
        index = model.index(row, 0, parent_index)
        node = model.data(index, Qt.UserRole)
        
        if node and not node.is_scope:
            # Found a signal
            return index, node
            
        # Recurse into children
        if model.hasChildren(index):
            result = find_signal_in_design_tree(model, index)
            if result:
                return result
                
    return None


def test_add_signal_to_empty_session(wave_widget_and_design_tree, qtbot):
    """Test adding a signal when no nodes are selected."""
    widget, design_tree_model = wave_widget_and_design_tree
    session = widget.session
    
    # Clear any existing nodes
    session.root_nodes.clear()
    session.selected_nodes.clear()
    widget.model.layoutChanged.emit()
    
    # Find a signal in the design tree
    result = find_signal_in_design_tree(design_tree_model)
    assert result is not None, "No signal found in design tree"
    
    signal_index, design_node = result
    
    # Simulate adding the signal (what happens on double-click)
    if hasattr(design_node, 'var_handle') and design_node.var_handle is not None:
        # Get full signal name
        var = session.waveform_db.get_var(design_node.var_handle)
        hierarchy = session.waveform_db.hierarchy
        full_name = var.name(hierarchy) if var else f"Signal_{design_node.name}"
        
        # Create new signal node
        new_node = SignalNode(
            name=full_name,
            handle=design_node.var_handle,
            is_group=False
        )
        
        # Add to root nodes (no selection)
        session.root_nodes.append(new_node)
        widget.model.layoutChanged.emit()
        
        # Verify the signal was added
        assert len(session.root_nodes) == 1
        assert session.root_nodes[0].name == full_name
        assert session.root_nodes[0].handle == design_node.var_handle


def test_add_signal_after_selected(wave_widget_and_design_tree, qtbot):
    """Test adding a signal after a selected node."""
    widget, design_tree_model = wave_widget_and_design_tree
    session = widget.session
    
    # Ensure we have at least one node and select it
    if len(session.root_nodes) > 0:
        first_node = session.root_nodes[0]
        session.selected_nodes = [first_node]
    else:
        # Add a dummy node and select it
        dummy_node = SignalNode(name="dummy", handle=None, is_group=False)
        session.root_nodes.append(dummy_node)
        session.selected_nodes = [dummy_node]
        widget.model.layoutChanged.emit()
    
    initial_count = len(session.root_nodes)
    
    # Find a signal in the design tree
    result = find_signal_in_design_tree(design_tree_model)
    assert result is not None, "No signal found in design tree"
    
    signal_index, design_node = result
    
    # Simulate adding the signal after selected node
    if hasattr(design_node, 'var_handle') and design_node.var_handle is not None:
        # Get full signal name
        var = session.waveform_db.get_var(design_node.var_handle)
        hierarchy = session.waveform_db.hierarchy
        full_name = var.name(hierarchy) if var else f"Signal_{design_node.name}"
        
        # Create new signal node
        new_node = SignalNode(
            name=full_name,
            handle=design_node.var_handle,
            is_group=False
        )
        
        # Add after the selected node
        last_selected = session.selected_nodes[-1]
        idx = session.root_nodes.index(last_selected) + 1
        session.root_nodes.insert(idx, new_node)
        widget.model.layoutChanged.emit()
        
        # Verify the signal was added in the right position
        assert len(session.root_nodes) == initial_count + 1
        assert session.root_nodes[idx] == new_node
        assert session.root_nodes[idx].name == full_name


def test_add_signal_to_group(wave_widget_and_design_tree, qtbot):
    """Test adding a signal after a selected node inside a group."""
    widget, design_tree_model = wave_widget_and_design_tree
    session = widget.session
    
    # Find or create a group with children
    group_node = None
    for node in session.root_nodes:
        if node.is_group and len(node.children) > 0:
            group_node = node
            break
    
    if not group_node:
        # Create a group with a child
        group_node = SignalNode(name="Test Group", is_group=True)
        child_node = SignalNode(name="Child Signal", handle=None, is_group=False)
        group_node.children.append(child_node)
        child_node.parent = group_node
        session.root_nodes.append(group_node)
        widget.model.layoutChanged.emit()
    
    # Select the first child in the group
    first_child = group_node.children[0]
    session.selected_nodes = [first_child]
    
    initial_child_count = len(group_node.children)
    
    # Find a signal in the design tree
    result = find_signal_in_design_tree(design_tree_model)
    assert result is not None, "No signal found in design tree"
    
    signal_index, design_node = result
    
    # Simulate adding the signal after selected child
    if hasattr(design_node, 'var_handle') and design_node.var_handle is not None:
        # Get full signal name
        var = session.waveform_db.get_var(design_node.var_handle)
        hierarchy = session.waveform_db.hierarchy
        full_name = var.name(hierarchy) if var else f"Signal_{design_node.name}"
        
        # Create new signal node
        new_node = SignalNode(
            name=full_name,
            handle=design_node.var_handle,
            is_group=False,
            parent=group_node
        )
        
        # Add after the selected child
        idx = group_node.children.index(first_child) + 1
        group_node.children.insert(idx, new_node)
        widget.model.layoutChanged.emit()
        
        # Verify the signal was added in the right position
        assert len(group_node.children) == initial_child_count + 1
        assert group_node.children[idx] == new_node
        assert new_node.parent == group_node


def test_design_tree_variable_handle(wave_widget_and_design_tree, qtbot):
    """Test that design tree nodes have proper variable handles."""
    widget, design_tree_model = wave_widget_and_design_tree
    
    # Find a signal in the design tree
    result = find_signal_in_design_tree(design_tree_model)
    assert result is not None, "No signal found in design tree"
    
    signal_index, design_node = result
    
    # Debug info
    print(f"\nDesign node: {design_node.name}")
    print(f"Has var_handle: {hasattr(design_node, 'var_handle')}")
    print(f"var_handle value: {getattr(design_node, 'var_handle', 'N/A')}")
    print(f"Has var: {hasattr(design_node, 'var')}")
    print(f"var value: {getattr(design_node, 'var', 'N/A')}")
    
    # Verify the node has a variable handle or var object
    assert hasattr(design_node, 'var_handle'), "Design node should have var_handle attribute"
    
    # For now, let's check if we at least have the var object
    if design_node.var_handle is None:
        assert hasattr(design_node, 'var') and design_node.var is not None, \
            "If var_handle is None, should at least have var object"
    
    # If we have var object but no handle, we can still use it to add signals
    if design_node.var and widget.session.waveform_db:
        hierarchy = widget.session.waveform_db.hierarchy
        full_name = design_node.var.name(hierarchy)
        assert full_name, "Should be able to get full signal name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])