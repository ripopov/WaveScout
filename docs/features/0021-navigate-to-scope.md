# Feature Specification: Navigate to Scope Context Menu Action

## Executive Summary

This feature adds a "Navigate to scope" context menu action in SignalNamesView that enables users to quickly locate and highlight the parent scope of a selected signal in the DesignTreeView. The action provides seamless navigation between the waveform signal display and the hierarchical design tree, improving workflow efficiency when exploring signal relationships and design structure.

## Feature Overview

### Goals
- Provide quick navigation from displayed signals to their parent scopes in the design hierarchy
- Support navigation in both unified and split view modes of the DesignTreeView
- Enhance user workflow when analyzing signal relationships and design structure
- Maintain consistency with existing UI patterns and user experience

### Business Value
- **Improved User Efficiency**: Reduces time spent manually searching for signal locations in large design hierarchies
- **Enhanced Design Understanding**: Helps users quickly understand signal context and relationships
- **Better Integration**: Creates tighter coupling between signal display and hierarchy navigation
- **Professional Workflow**: Aligns with industry-standard waveform viewer behaviors

## User Stories and Acceptance Criteria

### User Story 1: Navigate to Parent Scope from Signal
**As a** hardware engineer analyzing waveforms  
**I want to** quickly navigate to the parent scope of a signal in the design tree  
**So that** I can understand the signal's context and explore related signals in the same module

**Acceptance Criteria:**
1. Right-clicking on a signal in SignalNamesView shows "Navigate to scope" in the context menu
2. Clicking the action navigates to and selects the parent scope in the design tree
3. The design tree expands as needed to make the scope visible
4. The scope is scrolled into view if necessary
5. Works for both single-bit and multi-bit signals

### User Story 2: Multiple Signal Selection Handling
**As a** user with multiple signals selected  
**I want** the navigation to use the first selected signal  
**So that** the behavior is predictable and consistent

**Acceptance Criteria:**
1. When multiple signals are selected, the first signal in the selection is used
2. The action remains available regardless of selection count
3. Clear visual feedback shows which scope was navigated to

### User Story 3: Support for Both View Modes
**As a** user of either unified or split tree view modes  
**I want** navigation to work consistently in both modes  
**So that** my workflow isn't disrupted by view mode changes

**Acceptance Criteria:**
1. In unified mode, the scope is selected in the unified_tree
2. In split mode, the scope is selected in the scope_tree (top panel)
3. View mode automatically switches if needed to show the navigation
4. Navigation state is preserved when switching between modes

## Detailed Requirements

### Functional Requirements

#### FR1: Context Menu Integration
- The "Navigate to scope" action shall appear in the SignalNamesView context menu
- The action shall be positioned after existing format and render options
- The action shall be separated from other actions with a visual separator
- The action shall be enabled only when a non-group SignalNode is selected
- For group nodes, the action shall be disabled or hidden

#### FR2: Scope Path Extraction
- The system shall extract the parent scope path from the selected signal's full hierarchical path
- For a signal "top.cpu.core.alu.result[31:0]", the scope path is "top.cpu.core.alu"
- The extraction shall handle all valid Verilog/VHDL hierarchical naming conventions
- Edge cases like single-level paths ("signal_name") shall be handled gracefully

#### FR3: Tree Navigation Logic
- The system shall find the corresponding scope node in the active tree view
- The tree shall expand all parent nodes necessary to reveal the target scope
- The target scope shall be selected and made the current item
- The view shall scroll to ensure the selected scope is visible
- If the scope doesn't exist in the tree, an appropriate message shall be shown

#### FR4: View Mode Handling
- The system shall detect the current DesignTreeView mode (unified or split)
- Navigation shall work correctly regardless of the active mode
- No automatic mode switching shall occur unless necessary for navigation

### Non-Functional Requirements

#### NFR1: Performance
- Navigation shall complete within 100ms for typical design hierarchies (< 10,000 nodes)
- Tree expansion and scrolling shall be smooth without visible lag
- Memory usage shall not increase significantly during navigation

#### NFR2: Usability
- The action label "Navigate to scope" shall be clear and self-explanatory
- Keyboard shortcuts shall be considered for future enhancement
- Visual feedback (selection highlight) shall be immediate and obvious

#### NFR3: Reliability
- Navigation shall handle malformed or missing scope paths gracefully
- The feature shall not crash or hang on edge cases
- Error conditions shall be logged appropriately

## Technical Design

### Architecture Impact Analysis

#### Affected Components
1. **SignalNamesView** (`wavescout/signal_names_view.py`)
   - Add new context menu action
   - Implement navigation trigger logic
   - Communicate with DesignTreeView

2. **DesignTreeView** (`wavescout/design_tree_view.py`)
   - Add public method for scope navigation
   - Handle both unified and split modes
   - Implement tree node finding and selection

3. **DesignTreeModel** (`wavescout/design_tree_model.py`)
   - May need helper methods for scope path lookup
   - Ensure proper index creation for navigation

4. **ScopeTreeModel** (`wavescout/scope_tree_model.py`)
   - Similar navigation support for split mode
   - Coordinate with DesignTreeView

### Design Patterns and Approach

#### Signal-Slot Communication
The feature will use Qt's signal-slot mechanism for loose coupling:
```python
# SignalNamesView emits navigation request
navigate_to_scope_requested = Signal(str)  # scope_path

# DesignTreeView handles navigation
def navigate_to_scope(self, scope_path: str) -> bool:
    """Navigate to and select the specified scope."""
```

#### Scope Path Extraction Algorithm
```python
def extract_scope_path(signal_path: str) -> str:
    """Extract parent scope from signal path.
    'top.cpu.alu.result' -> 'top.cpu.alu'
    'signal' -> '' (no scope)
    """
    parts = signal_path.split('.')
    if len(parts) <= 1:
        return ''  # Top-level signal
    return '.'.join(parts[:-1])
```

#### Tree Navigation Strategy
1. Parse scope path into hierarchical components
2. Starting from root, traverse tree matching each component
3. Expand nodes as needed during traversal
4. Select final node and ensure visibility

### API Contracts

#### SignalNamesView Extensions
```python
class SignalNamesView(BaseColumnView):
    # New signal
    navigate_to_scope_requested = Signal(str)  # Emits scope path
    
    def _navigate_to_scope(self) -> None:
        """Handle navigate to scope action."""
        # Get selected nodes
        # Extract scope path from first node
        # Emit navigation request
```

#### DesignTreeView Extensions
```python
class DesignTreeView(QWidget):
    def navigate_to_scope(self, scope_path: str) -> bool:
        """Navigate to the specified scope in the tree.
        
        Args:
            scope_path: Hierarchical path like 'top.cpu.alu'
            
        Returns:
            True if navigation successful, False otherwise
        """
        
    def _find_scope_node(self, path_parts: List[str], 
                        tree: QTreeView) -> Optional[QModelIndex]:
        """Find scope node by path components."""
```

### Error Handling Strategy

1. **Missing Scope**: If scope doesn't exist, show status message "Scope not found: {path}"
2. **Invalid Path**: Handle empty or malformed paths gracefully, no action taken
3. **No Selection**: Disable menu action when no signals selected
4. **Model Not Ready**: Check for valid model before navigation attempt

## Implementation Steps

### Phase 1: Core Navigation Logic (Priority: High)
1. Add `navigate_to_scope()` method to DesignTreeView
2. Implement scope node finding algorithm
3. Add tree expansion and selection logic
4. Test with both view modes

### Phase 2: UI Integration (Priority: High)
1. Add context menu action to SignalNamesView
2. Implement scope path extraction
3. Connect signal-slot communication
4. Add visual separators in menu

### Phase 3: Polish and Edge Cases (Priority: Medium)
1. Add status messages for feedback
2. Handle error conditions gracefully
3. Optimize performance for large trees
4. Add comprehensive logging

## Testing Requirements

### Unit Tests
1. **Test Scope Path Extraction**
   - Various signal path formats
   - Edge cases (single level, empty)
   - Special characters in names

2. **Test Navigation Logic**
   - Find nodes at different depths
   - Handle missing scopes
   - Verify tree expansion

### Integration Tests
1. **Test Menu Integration**
   - Menu appears correctly
   - Action enabled/disabled appropriately
   - Multiple selection handling

2. **Test View Mode Handling**
   - Navigation in unified mode
   - Navigation in split mode
   - Mode switching scenarios

### End-to-End Tests
1. Load sample waveform with known hierarchy
2. Add signals to display
3. Navigate to various scopes
4. Verify correct selection and visibility

### Performance Tests
1. Measure navigation time with large hierarchies (10K+ nodes)
2. Check memory usage during navigation
3. Verify UI responsiveness

## Risk Assessment

### Technical Risks
1. **Performance with Large Trees**: Mitigation - Implement efficient search algorithms
2. **Qt Model Complexity**: Mitigation - Thorough testing of index handling
3. **Cross-mode Consistency**: Mitigation - Shared navigation logic

### User Experience Risks
1. **Unclear Navigation Result**: Mitigation - Clear visual feedback
2. **Slow Response**: Mitigation - Performance optimization
3. **Lost Context**: Mitigation - Maintain selection state

## Success Metrics

1. **Functional Completeness**
   - All acceptance criteria met
   - No critical bugs in navigation
   - Works in all supported view modes

2. **Performance Targets**
   - Navigation completes < 100ms for typical designs
   - No UI freezing during navigation
   - Memory usage increase < 1MB

3. **User Satisfaction**
   - Intuitive menu placement
   - Clear visual feedback
   - Consistent behavior

## Migration and Rollback Plan

This feature is additive and requires no migration. If issues arise:
1. The context menu action can be disabled via configuration
2. The navigation method can return early without side effects
3. No persistent state changes that would require rollback

## Future Enhancements

1. **Keyboard Shortcut**: Add configurable shortcut (e.g., Ctrl+G for "Go to scope")
2. **Navigation History**: Track navigation history with back/forward buttons
3. **Scope Highlighting**: Highlight the scope in a different color temporarily
4. **Bidirectional Navigation**: Add "Show signals" action in design tree context menu
5. **Search Integration**: Combine with search to find and navigate to scopes
6. **Multi-Signal Navigation**: Show menu of scopes when multiple signals from different scopes selected

## Appendix: Code Examples

### Example: Context Menu Addition
```python
def _show_context_menu(self, position: QPoint) -> None:
    # ... existing code ...
    
    # Add separator before navigation actions
    menu.addSeparator()
    
    # Add navigate to scope action (only for signals, not groups)
    if not node.is_group:
        navigate_action = QAction("Navigate to scope", self)
        navigate_action.triggered.connect(self._navigate_to_scope)
        menu.addAction(navigate_action)
```

### Example: Scope Navigation Implementation
```python
def navigate_to_scope(self, scope_path: str) -> bool:
    """Navigate to the specified scope in the design tree."""
    if not scope_path:
        return False
        
    path_parts = scope_path.split('.')
    
    if self.current_mode == DesignTreeViewMode.UNIFIED:
        tree = self.unified_tree
        model = self.design_tree_model
    else:
        tree = self.scope_tree
        model = self.scope_tree_model
        
    if not model:
        return False
        
    # Find the scope node
    index = self._find_scope_by_path(path_parts, model, QModelIndex())
    if not index.isValid():
        self.status_message.emit(f"Scope not found: {scope_path}")
        return False
        
    # Expand parents and select
    tree.setCurrentIndex(index)
    tree.scrollTo(index)
    self.status_message.emit(f"Navigated to: {scope_path}")
    return True
```