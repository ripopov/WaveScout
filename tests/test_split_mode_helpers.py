"""Helper functions for working with split mode in tests."""

from typing import List, Optional
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from scout import WaveScoutMainWindow
from wavescout.data_model import SignalNode


def add_signals_from_split_mode(window: WaveScoutMainWindow, count: int = 5) -> List[SignalNode]:
    """
    Helper to add signals from the design tree in split mode.
    
    In split mode:
    - The scope tree only contains scopes (no signals)
    - When a scope is selected, its variables appear in the VarsView
    - Variables are added by double-clicking in the VarsView or using the selection
    
    Args:
        window: WaveScoutMainWindow instance
        count: Number of signals to add
        
    Returns:
        List of SignalNode objects that were actually added to the session
    """
    design_view = window.design_tree_view
    scope_tree = design_view.scope_tree
    scope_model = design_view.scope_tree_model
    vars_view = design_view.vars_view
    
    if not scope_model:
        return []
    
    # Track initial count of signals in session
    initial_count = 0
    if window.wave_widget and window.wave_widget.session:
        initial_count = len(window.wave_widget.session.root_nodes)
    
    # Find scopes and add their variables
    def add_from_scope(scope_idx: QModelIndex, remaining: int) -> int:
        """Add variables from a scope, return number still needed."""
        if remaining <= 0:
            return 0
            
        # Select the scope to populate VarsView
        scope_tree.setCurrentIndex(scope_idx)
        QTest.qWait(100)  # Let the selection propagate
        
        # Check if VarsView has variables
        if vars_view and vars_view.vars_model.rowCount() > 0:
            # Add variables from this scope
            for row in range(min(remaining, vars_view.vars_model.rowCount())):
                # Double-click on the variable to add it
                var_idx = vars_view.filter_proxy.index(row, 0)
                if var_idx.isValid():
                    vars_view._on_double_click(var_idx)
                    remaining -= 1
                    QTest.qWait(50)  # Small delay between additions
                    
                    if remaining <= 0:
                        break
        
        # If we still need more, try child scopes
        if remaining > 0:
            for child_row in range(scope_model.rowCount(scope_idx)):
                child_idx = scope_model.index(child_row, 0, scope_idx)
                if child_idx.isValid():
                    # Expand the child scope
                    scope_tree.expand(child_idx)
                    QTest.qWait(30)
                    remaining = add_from_scope(child_idx, remaining)
                    if remaining <= 0:
                        break
        
        return remaining
    
    # Start from root scopes
    remaining = count
    for row in range(scope_model.rowCount(QModelIndex())):
        root_idx = scope_model.index(row, 0, QModelIndex())
        if root_idx.isValid():
            # Expand root scope
            scope_tree.expand(root_idx)
            QTest.qWait(50)
            remaining = add_from_scope(root_idx, remaining)
            if remaining <= 0:
                break
    
    # Wait for all signals to be processed
    QTest.qWait(200)
    
    # Return the actual signals that were added
    if window.wave_widget and window.wave_widget.session:
        current_count = len(window.wave_widget.session.root_nodes)
        if current_count > initial_count:
            return window.wave_widget.session.root_nodes[initial_count:]
    
    return []


def get_variables_from_selected_scope(window: WaveScoutMainWindow) -> List[dict]:
    """
    Get the list of variables from the currently selected scope.
    
    Returns:
        List of variable data dictionaries from VarsView
    """
    design_view = window.design_tree_view
    vars_view = design_view.vars_view
    
    if vars_view and vars_view.vars_model:
        return vars_view.vars_model.variables
    return []


def select_scope_by_name(window: WaveScoutMainWindow, scope_name: str) -> bool:
    """
    Select a scope by name in the scope tree.
    
    Args:
        window: WaveScoutMainWindow instance
        scope_name: Name of the scope to select
        
    Returns:
        True if scope was found and selected
    """
    design_view = window.design_tree_view
    scope_tree = design_view.scope_tree
    scope_model = design_view.scope_tree_model
    
    if not scope_model:
        return False
    
    def find_and_select(parent_idx: QModelIndex = QModelIndex()) -> bool:
        """Recursively find and select the scope."""
        for row in range(scope_model.rowCount(parent_idx)):
            idx = scope_model.index(row, 0, parent_idx)
            if idx.isValid():
                name = scope_model.data(idx, Qt.ItemDataRole.DisplayRole)
                if name == scope_name:
                    # Found it - select it
                    scope_tree.setCurrentIndex(idx)
                    QTest.qWait(50)
                    return True
                    
                # Try children
                scope_tree.expand(idx)
                if find_and_select(idx):
                    return True
        return False
    
    return find_and_select()


def add_signals_by_double_click_vars(window: WaveScoutMainWindow, count: int = 5) -> List[SignalNode]:
    """
    Add signals by simulating double-clicks in the VarsView.
    
    This more closely mimics user interaction.
    
    Args:
        window: WaveScoutMainWindow instance
        count: Number of signals to add
        
    Returns:
        List of SignalNode objects that were added
    """
    design_view = window.design_tree_view
    scope_tree = design_view.scope_tree
    scope_model = design_view.scope_tree_model
    vars_view = design_view.vars_view
    
    if not scope_model:
        return []
    
    # Keep track of initial signal count
    initial_count = len(window.wave_widget.session.root_nodes) if window.wave_widget.session else 0
    
    # Find first scope with variables
    for row in range(scope_model.rowCount(QModelIndex())):
        root_idx = scope_model.index(row, 0, QModelIndex())
        if root_idx.isValid():
            # Expand and select scope
            scope_tree.expand(root_idx)
            scope_tree.setCurrentIndex(root_idx)
            QTest.qWait(100)
            
            # Check if VarsView has variables
            if vars_view and vars_view.vars_model.rowCount() > 0:
                # Double-click on variables to add them
                for var_row in range(min(count, vars_view.vars_model.rowCount())):
                    var_idx = vars_view.filter_proxy.index(var_row, 0)
                    if var_idx.isValid():
                        # Simulate double-click
                        vars_view._on_double_click(var_idx)
                        QTest.qWait(50)
                
                break
    
    # Wait for signals to be added
    QTest.qWait(200)
    
    # Get the newly added signals
    if window.wave_widget.session:
        current_count = len(window.wave_widget.session.root_nodes)
        if current_count > initial_count:
            return window.wave_widget.session.root_nodes[initial_count:]
    
    return []