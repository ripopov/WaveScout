"""Test DesignTreeModel functionality."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from wavescout.design_tree_model import DesignTreeModel, DesignTreeNode


@pytest.fixture
def qt_app(qtbot):
    """Provide Qt application for testing."""
    return QApplication.instance()


@pytest.fixture
def waveform_db(vcd_session):
    """Get waveform database from session."""
    return vcd_session.waveform_db


def test_design_tree_node():
    """Test DesignTreeNode creation."""
    # Test scope node
    scope = DesignTreeNode("testbench", is_scope=True)
    assert scope.name == "testbench"
    assert scope.is_scope == True
    assert scope.var_type == ""
    assert scope.bit_range == ""
    assert len(scope.children) == 0
    
    # Test signal node
    signal = DesignTreeNode("clk", is_scope=False, var_type="reg", bit_range="[0]")
    assert signal.name == "clk"
    assert signal.is_scope == False
    assert signal.var_type == "reg"
    assert signal.bit_range == "[0]"
    
    # Test parent-child relationship
    scope.add_child(signal)
    assert len(scope.children) == 1
    assert signal.parent == scope


def test_design_tree_model_creation(qt_app):
    """Test DesignTreeModel creation."""
    model = DesignTreeModel()
    assert model is not None
    assert model.root_node.name == "Root"
    assert model.root_node.is_scope == True
    assert model.columnCount() == 3


def test_design_tree_model_headers(qt_app):
    """Test model headers."""
    model = DesignTreeModel()
    
    # Check headers
    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Name"
    assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Type"
    assert model.headerData(2, Qt.Horizontal, Qt.DisplayRole) == "Bit Range"
    
    # Check invalid section
    assert model.headerData(3, Qt.Horizontal, Qt.DisplayRole) is None


def test_design_tree_model_with_waveform(qt_app, waveform_db):
    """Test loading hierarchy from waveform database."""
    model = DesignTreeModel(waveform_db)
    
    # Should have loaded hierarchy
    root_count = model.rowCount()
    assert root_count > 0, "Model should have loaded hierarchy"
    
    # Check first level items
    scopes_found = []
    signals_found = []
    
    for row in range(min(root_count, 5)):
        index = model.index(row, 0)
        node = model.data(index, Qt.UserRole)
        
        if node and node.is_scope:
            scopes_found.append(node.name)
        elif node:
            signals_found.append(node.name)
    
    print(f"\nFound {len(scopes_found)} scopes: {scopes_found}")
    print(f"Found {len(signals_found)} signals: {signals_found}")
    
    # Should have at least some scopes
    assert len(scopes_found) > 0 or len(signals_found) > 0, "Should have found some items"


def test_design_tree_icons(qt_app, waveform_db):
    """Test that icons are provided for scopes and signals."""
    model = DesignTreeModel(waveform_db)
    
    # Find a scope and a signal
    scope_index = None
    signal_index = None
    
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        node = model.data(index, Qt.UserRole)
        
        if node and node.is_scope and scope_index is None:
            scope_index = index
        elif node and not node.is_scope and signal_index is None:
            signal_index = index
            
        if scope_index and signal_index:
            break
    
    # Check icons
    if scope_index:
        icon = model.data(scope_index, Qt.DecorationRole)
        assert icon is not None, "Scope should have an icon"
        
    if signal_index:
        icon = model.data(signal_index, Qt.DecorationRole)
        assert icon is not None, "Signal should have an icon"


def test_design_tree_data_display(qt_app, waveform_db):
    """Test data display in different columns."""
    model = DesignTreeModel(waveform_db)
    
    # Find a signal with bit range
    signal_with_range = None
    
    def find_signal_recursive(parent_index=None):
        nonlocal signal_with_range
        
        parent_count = model.rowCount(parent_index) if parent_index else model.rowCount()
        
        for row in range(parent_count):
            if parent_index:
                index = model.index(row, 0, parent_index)
            else:
                index = model.index(row, 0)
                
            node = model.data(index, Qt.UserRole)
            
            if node and not node.is_scope and node.bit_range:
                signal_with_range = (index, node)
                return True
                
            # Recurse into children
            if node and node.is_scope and model.rowCount(index) > 0:
                if find_signal_recursive(index):
                    return True
        
        return False
    
    find_signal_recursive()
    
    if signal_with_range:
        index, node = signal_with_range
        
        # Check all columns
        name = model.data(index, Qt.DisplayRole)
        type_col_index = model.index(index.row(), 1, index.parent())
        type_str = model.data(type_col_index, Qt.DisplayRole)
        range_col_index = model.index(index.row(), 2, index.parent())
        bit_range = model.data(range_col_index, Qt.DisplayRole)
        
        print(f"\nSignal: {name}, Type: {type_str}, Range: {bit_range}")
        
        assert name == node.name
        assert type_str == node.var_type
        assert bit_range == node.bit_range
        
        # Verify we found a proper multi-bit signal
        assert "[" in bit_range and ":" in bit_range and "]" in bit_range
    else:
        pytest.fail("No signal with bit range found in the design tree")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])